"""Servidor local da interface Tauri (desktop/server.py): token, origem, contrato e eventos.

Sobe o servidor de verdade em 127.0.0.1 com um alvo falso: nenhum modelo, microfone ou atalho global.
"""
import asyncio
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop import server as S  # noqa: E402

METHODS = frozenset({"echo", "toggle", "boom", "notes"})


class Fake:
    def __init__(self):
        self.calls = []

    def echo(self, text: str) -> str:
        self.calls.append(("echo", text))
        return json.dumps({"ok": True, "text": text})

    def toggle(self, on: bool) -> None:
        self.calls.append(("toggle", on))

    def boom(self) -> str:
        raise RuntimeError("segredo interno")

    def notes(self) -> bool:
        return True


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.d = S.Dispatcher(self.fake, METHODS)

    def call(self, method, params, rid=1):
        return self.d.handle({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})

    def test_result_json_strings_arrive_decoded(self):
        self.assertEqual(self.call("echo", ["oi"])["result"], {"ok": True, "text": "oi"})
        self.assertIs(self.call("notes", [])["result"], True)

    def test_unknown_and_private_methods_are_refused(self):
        for name in ("executeTask", "_emit", "__init__", "calls"):
            self.assertEqual(self.call(name, [])["error"]["code"], S.METHOD_NOT_FOUND, name)

    def test_arity_and_types_are_checked(self):
        for method, params in (("echo", []), ("echo", [1]), ("echo", [True]), ("toggle", [1]),
                               ("toggle", ["true"]), ("echo", {"text": "x"})):
            self.assertEqual(self.call(method, params)["error"]["code"], S.INVALID_PARAMS, (method, params))
        self.assertEqual(self.fake.calls, [])

    def test_notification_runs_without_reply(self):
        self.assertIsNone(self.d.handle({"jsonrpc": "2.0", "method": "toggle", "params": [True]}))
        self.assertEqual(self.fake.calls, [("toggle", True)])

    def test_exception_does_not_leak_message(self):
        err = self.call("boom", [])["error"]
        self.assertEqual(err["code"], S.INTERNAL_ERROR)
        self.assertNotIn("segredo", err["message"])

    def test_malformed_request(self):
        self.assertEqual(self.d.handle(["x"])["error"]["code"], S.INVALID_REQUEST)
        self.assertEqual(self.d.handle({"method": "echo"})["error"]["code"], S.INVALID_REQUEST)

    def test_real_contract_types_resolve(self):
        from desktop.bridge_core import BridgeCore

        class Core(BridgeCore):
            def _emit(self, name, payload=None):
                pass
        d = S.Dispatcher(Core())
        self.assertEqual(sorted(S.RPC_METHODS - set(d._types)), [], "metodo do contrato sem implementacao no BridgeCore")
        self.assertEqual(d._types["executeTask"], [str, bool, bool])
        self.assertEqual(d._types["approvePlan"], [bool, str])


class LiveServerTests(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.server = S.EventServer().start()
        self.server.attach(S.Dispatcher(self.fake, METHODS))
        self.url = f"ws://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()

    def run_async(self, coro):
        return asyncio.run(asyncio.wait_for(coro, 15))

    async def _open(self, token=None, origin=None):
        from websockets.asyncio.client import connect
        ws = await connect(self.url, origin=origin)
        await ws.send(json.dumps({"token": self.server.token if token is None else token}))
        return ws

    def test_random_port_and_long_token(self):
        self.assertGreater(self.server.port, 0)
        self.assertGreaterEqual(len(self.server.token), 40)

    def test_wrong_token_is_closed(self):
        from websockets.exceptions import ConnectionClosed

        async def go():
            ws = await self._open(token="errado")
            with self.assertRaises(ConnectionClosed) as cm:
                await ws.recv()
            return cm.exception.rcvd.code
        self.assertEqual(self.run_async(go()), 4401)
        self.assertEqual(self.fake.calls, [])

    def test_silence_is_closed(self):
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed

        async def go():
            async with connect(self.url) as ws:
                with self.assertRaises(ConnectionClosed) as cm:
                    await ws.recv()
                return cm.exception.rcvd.code
        with patch.object(S, "AUTH_TIMEOUT_S", 0.3):
            self.assertEqual(self.run_async(go()), 4401)

    def test_foreign_web_origin_is_rejected(self):
        from websockets.asyncio.client import connect
        from websockets.exceptions import InvalidStatus

        async def go():
            with self.assertRaises(InvalidStatus) as cm:
                await connect(self.url, origin="https://example.com")
            return cm.exception.response.status_code
        self.assertEqual(self.run_async(go()), 403)

    def test_tauri_origin_calls_and_receives_events(self):
        async def go():
            ws = await self._open(origin="http://tauri.localhost")
            hello = json.loads(await ws.recv())
            await ws.send(json.dumps({"jsonrpc": "2.0", "id": 9, "method": "echo", "params": ["olá"]}))
            reply = json.loads(await ws.recv())
            self.server.publish("planReady", json.dumps({"steps": 2}))
            event = json.loads(await ws.recv())
            await ws.close()
            return hello, reply, event
        hello, reply, event = self.run_async(go())
        self.assertEqual(hello["params"]["protocol"], S.PROTOCOL_VERSION)
        self.assertEqual(reply, {"jsonrpc": "2.0", "id": 9, "result": {"ok": True, "text": "olá"}})
        self.assertEqual(event["params"], {"name": "planReady", "payload": {"steps": 2}})

    def test_voice_level_is_throttled(self):
        async def go():
            ws = await self._open()
            await ws.recv()                                    # hello
            for i in range(50):
                self.server.publish("voiceLevel", json.dumps({"level": i}))
            self.server.publish("taskDone", "{}")
            names = []
            while not names or names[-1] != "taskDone":
                names.append(json.loads(await ws.recv())["params"]["name"])
            await ws.close()
            return names
        self.assertLess(self.run_async(go()).count("voiceLevel"), 5)


class ReadyLineTests(unittest.TestCase):
    def test_ready_line_goes_only_to_the_given_stream(self):
        class Quiet(S.HeadlessBridge):
            def _setup_core(self):           # sem Controller, voz nem atalhos no teste
                self._controller = None

            def shutdown(self):
                pass

        out = io.StringIO()
        with patch.object(S, "HeadlessBridge", Quiet), patch.object(S.EventServer, "wait", lambda self: None):
            S.serve_headless(ready_stream=out, stop_on_stdin_eof=False)
        line = out.getvalue()
        self.assertTrue(line.startswith(S.READY_PREFIX))
        self.assertEqual(set(json.loads(line[len(S.READY_PREFIX):])), {"port", "token", "protocol"})


if __name__ == "__main__":
    unittest.main()


class ForegroundWatchTests(unittest.TestCase):
    def _bridge(self, mini=True):
        published = []

        class Srv:
            def publish(self, name, payload=None):
                published.append((name, payload))

        class B(S.HeadlessBridge):
            def _setup_core(self):
                pass

            def _ui_cfg(self):
                return {"mini_chat": mini}

        return B(Srv()), published

    def test_asks_for_mini_once_when_another_app_takes_the_front(self):
        import time
        b, published = self._bridge()
        with patch.object(S, "FOREGROUND_POLL_S", 0.01), patch("desktop.foreground.foreign_foreground", return_value=True):
            b._emit("runningChanged", True)
            time.sleep(0.2)
        requests = [p for n, p in published if n == "windowRequest"]
        self.assertEqual(requests, [json.dumps({"action": "enter_mini"})])
        self.assertIn(("runningChanged", True), published)

    def test_no_request_when_disabled_or_stopped(self):
        import time
        b, published = self._bridge(mini=False)
        with patch.object(S, "FOREGROUND_POLL_S", 0.01), patch("desktop.foreground.foreign_foreground", return_value=True):
            b._emit("runningChanged", True)
            time.sleep(0.1)
        self.assertFalse([n for n, _ in published if n == "windowRequest"])

    def test_shell_pid_counts_as_ours(self):
        from desktop import foreground
        with patch.dict("os.environ", {"CREATIVE_AIX_SHELL_PID": "4242"}):
            self.assertIn(4242, foreground.shell_pids())
        with patch.dict("os.environ", {"CREATIVE_AIX_SHELL_PID": "abc"}):
            self.assertEqual(foreground.shell_pids(), {__import__("os").getpid()})
