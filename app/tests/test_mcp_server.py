"""Servidor MCP de leitura (mcp_server.py): protocolo, ferramentas so de leitura, caminhos recusados,
e o processo real conversando por stdio como uma CLI faria."""
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import mcp_server


def call(method, params=None, mid=1):
    msg = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        msg["params"] = params
    return mcp_server.handle(msg)


class McpProtocolTests(unittest.TestCase):
    def test_handshake_list_and_notifications(self):
        r = call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", r["result"]["capabilities"])
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        tools = call("tools/list")["result"]["tools"]
        self.assertEqual({t["name"] for t in tools},
                         {"brain_search", "brain_read", "task_status", "recent_tasks", "list_projects"})
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
        self.assertEqual(call("nada/disso")["error"]["code"], -32601)
        self.assertEqual(call("tools/call", {"name": "run_command", "arguments": {}})["error"]["code"], -32602)

    def test_tools_are_read_only_and_refuse_paths_outside_the_brain(self):
        for bad in ("../config.yaml", "..\\x.md", ".cerebro/harness.json", "/etc/passwd", "notas.txt", ""):
            with self.subTest(path=bad):
                r = call("tools/call", {"name": "brain_read", "arguments": {"path": bad}})["result"]
                self.assertTrue(r["isError"], r)
        r = call("tools/call", {"name": "brain_search", "arguments": {"query": ""}})["result"]
        self.assertTrue(r["isError"])

    def test_search_and_read_use_the_brain_and_mask_secrets(self):
        class Store:
            def search(self, q, limit=30):
                return [{"rel": "a/Nota.md", "title": "Nota", "snippet": "api_key = sk-abcdefghijklmnopqrstuvwx"}]
            def read(self, rel):
                return "token: abcdefghijklmnop\ncorpo" if rel == "a/Nota.md" else ""
        brain = type("B", (), {"store": Store()})()
        with patch.object(mcp_server, "_brain", return_value=brain):
            text = call("tools/call", {"name": "brain_search", "arguments": {"query": "nota"}})["result"]["content"][0]["text"]
            self.assertIn("a/Nota.md", text)
            self.assertNotIn("sk-abcdefghij", text)
            body = call("tools/call", {"name": "brain_read", "arguments": {"path": "a/Nota.md"}})["result"]
            self.assertFalse(body["isError"])
            self.assertNotIn("abcdefghijklmnop", body["content"][0]["text"])
            self.assertIn("corpo", body["content"][0]["text"])
            self.assertTrue(call("tools/call", {"name": "brain_read", "arguments": {"path": "a/Outra.md"}})["result"]["isError"])

    def test_real_process_over_stdio(self):
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        p = subprocess.run([sys.executable, str(APP / "mcp_server.py")], input="\n".join(json.dumps(m) for m in lines) + "\nnao-json\n",
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        replies = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
        self.assertEqual([r.get("id") for r in replies], [1, 2, None])   # a notificacao nao responde
        self.assertEqual(replies[2]["error"]["code"], -32700)
        self.assertEqual(len(replies[1]["result"]["tools"]), 5)

    def test_status_reads_a_live_foreign_pid_and_distinguishes_exit_from_completion(self):
        from core.task_ledger import TaskLedger
        with tempfile.TemporaryDirectory() as root, \
                subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                                 stdin=subprocess.PIPE) as owner:
            ledger = TaskLedger(Path(root))
            with patch("core.task_ledger.os.getpid", return_value=owner.pid):
                ledger.begin("finished", "gerar relatório")
                ledger.begin("interrupted", "gerar planilha")

            def status():
                return call("tools/call", {"name": "task_status"})["result"]["content"][0]["text"]

            with patch("core.task_ledger.get_ledger", return_value=ledger):
                self.assertIn("Estou fazendo agora: gerar planilha", status())
                owner.communicate(timeout=15)
                self.assertIn("Foi interrompido: gerar planilha", status())
                self.assertEqual(ledger.load("interrupted")["state"], "running")
                ledger.finish("interrupted", "failed")
                # A tarefa mais recente vem da data do arquivo: o relogio de arquivos do Windows anda de
                # ~15 ms em ~15 ms, e duas escritas no mesmo tique empatam (a ordem vira alfabetica).
                time.sleep(0.05)
                ledger.finish("finished", "completed")
                self.assertIn("Terminei: gerar relatório", status())


class McpWiringTests(unittest.TestCase):
    def test_cli_commands_carry_the_server_only_when_enabled(self):
        from core.coding_agents import build_command, MCP_NAME
        claude = build_command("claude", ["claude.exe"], "C:/p", mcp=True)
        cfg = json.loads(claude[claude.index("--mcp-config") + 1])
        self.assertTrue(cfg["mcpServers"][MCP_NAME]["args"][0].endswith("mcp_server.py"))
        self.assertEqual(claude[claude.index("--allowedTools") + 1], f"mcp__{MCP_NAME}")
        self.assertIn("--restricted", claude)
        codex = build_command("codex", ["codex.exe"], "C:/p", mcp=True)
        self.assertIn(f"mcp_servers.{MCP_NAME}.command=", " ".join(codex))
        self.assertNotIn("--mcp-config", build_command("claude", ["claude.exe"], "C:/p"))
        self.assertNotIn("-c", build_command("codex", ["codex.exe"], "C:/p"))

    def test_settings_toggle_wins_over_config(self):
        from core import coding_agents
        with patch("core.user_settings.load", return_value={"coding_mcp": False}):
            self.assertFalse(coding_agents.use_mcp({"mcp": True}))
        with patch("core.user_settings.load", return_value={}):
            self.assertTrue(coding_agents.use_mcp({}))
            self.assertFalse(coding_agents.use_mcp({"mcp": False}))

    def test_cli_job_allows_more_processes_than_the_code_worker(self):
        from core import process_runner
        self.assertGreaterEqual(process_runner.STREAM_MAX_PROCESSES, 32)
        seen = {}
        real = process_runner._attach_job
        def spy(proc, max_processes=8, max_memory=1 << 30):
            seen["n"] = max_processes
            return real(proc, max_processes, max_memory)
        with patch.object(process_runner, "_attach_job", spy):
            # 12 processos filhos ao mesmo tempo: com o limite antigo (8) o Windows negava a criacao
            code = ("import subprocess,sys;ps=[subprocess.Popen([sys.executable,'-c','import time;time.sleep(1)']) for _ in range(12)];"
                    "[p.wait() for p in ps];print('ok')")
            out = []
            r = process_runner.stream_process([sys.executable, "-c", code], cwd=str(APP), on_line=out.append, timeout=60)
        self.assertEqual(seen["n"], process_runner.STREAM_MAX_PROCESSES)
        self.assertEqual(r["status"], "succeeded", r)
        self.assertIn("ok", out)


if __name__ == "__main__":
    unittest.main()
