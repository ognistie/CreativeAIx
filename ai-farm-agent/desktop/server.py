"""
Servidor local da interface Tauri: o mesmo contrato do Bridge (QML), por WebSocket + JSON-RPC 2.0.

    desktop-tauri (React)  <──ws://127.0.0.1:<porta>──>  HeadlessBridge(BridgeCore)  ──>  Controller / core

Contrato
- Metodos: os mesmos nomes e argumentos dos @Slots do Bridge (RPC_METHODS). Chamada:
      {"jsonrpc": "2.0", "id": 7, "method": "brainRead", "params": ["Notas/x.md"]}
  Resposta: {"jsonrpc": "2.0", "id": 7, "result": <valor>}. Slots que devolvem JSON em string
  chegam ja decodificados (objeto), para o cliente nao fazer JSON.parse duas vezes.
- Eventos: os mesmos nomes dos Signals do Bridge, como notificacao:
      {"jsonrpc": "2.0", "method": "event", "params": {"name": "planReady", "payload": {...}}}
  Mais um so da interface Tauri: "windowRequest" ({"action": "restore_main" | "close_mini" | ...}).

Seguranca (a interface tem o mesmo poder do QML; nada alem disso)
- Escuta so em 127.0.0.1, porta escolhida pelo sistema.
- Token aleatorio de 32 bytes por execucao, exigido no primeiro frame ({"token": "..."}) e comparado em
  tempo constante. Sem token valido em AUTH_TIMEOUT_S, a conexao fecha.
- Origin: pagina de navegador so entra se vier da propria casca Tauri (ALLOWED_ORIGINS). Cliente sem
  Origin (processo local, testes) ainda precisa do token.
- So os nomes de RPC_METHODS sao chamaveis, com aridade e tipos conferidos contra a assinatura.
  As politicas do nucleo (core/action_policy.py, plan_validator.py) continuam decidindo o que executa.
"""

from __future__ import annotations

import asyncio
import hmac
import inspect
import json
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Set

from desktop.bridge_core import BridgeCore

PROTOCOL_VERSION = 1
AUTH_TIMEOUT_S = 5.0
MAX_MESSAGE_BYTES = 8 * 1024 * 1024          # anexos e notas longas cabem; nada de arquivo inteiro por aqui
VOICE_LEVEL_MIN_INTERVAL_S = 1 / 30          # o nivel do microfone chega muito mais rapido que a tela precisa
READY_PREFIX = "CREATIVE_AIX_READY "

# Origens da casca Tauri 2 no Windows (producao) e do servidor de desenvolvimento do Vite.
ALLOWED_ORIGINS = ("http://tauri.localhost", "https://tauri.localhost", "tauri://localhost")
DEV_ORIGINS = ("http://localhost:1420", "http://127.0.0.1:1420")

# Os @Slots publicos do Bridge (desktop/bridge.py), menos os que so existem com janela Qt.
# tests/test_bridge_contract.py garante que esta lista e a do Bridge andam juntas.
QT_WINDOW_ONLY = frozenset({"cursorPos"})
RPC_METHODS = frozenset({
    "activitySummary", "agentProfile", "appearance", "approvePlan", "approvePlanSteps", "attachFiles",
    "brainCreate", "brainCreateFolder", "brainDelete", "brainGraph", "brainOverview", "brainRead",
    "brainRename", "brainRestore", "brainSave", "brainSearch", "closeMini", "codingAgentsCheck",
    "creatorApply", "creatorDiscard", "creatorPropose", "deleteConversation", "devAct", "devCheck",
    "devDiff", "devList", "devPropose", "executeTask", "forceStop", "getSettings", "harnessGet",
    "harnessRestore", "harnessSave", "historyDetail", "introSeen", "journalDates", "journalDelete",
    "journalFolders", "journalGet", "journalList", "journalListIn", "journalSave", "journalSetPrivate",
    "journalSummarize", "journalUseInBrain", "labCancel", "labCreateVariant", "labDiff", "labEvalSets",
    "labFeedback", "labObserve", "labPromote", "labPromotionCheck", "labPublish", "labResearch",
    "labRun", "labRunDetail", "labRuns", "labSkills", "labToolTest", "labTraining", "labVersions",
    "librarySearch", "loadConversations", "loadHistory", "mainActivated", "newSession",
    "openBrainFolder", "openConversation", "providerStatus", "renameConversation", "restoreMain",
    "saveSettings", "setIntroSeen", "setLiveConversation", "setTitleBarColor", "suggestionApprove",
    "suggestionDismiss", "suggestionsList", "uiSettings", "voiceRecordCancel", "voiceRecordToggle",
    "wallpaperImport", "wallpaperInfo", "wallpaperRemove", "wallpapersList", "youProfile", "youSave",
})

_PY_TYPES = {"str": str, "bool": bool}

# JSON-RPC 2.0
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603


def _decode_payload(payload: Any) -> Any:
    """Signals carregam string JSON; pela rede vai o objeto."""
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except ValueError:
            return payload
    return payload


def _matches(value: Any, kind: type) -> bool:
    """bool so aceita bool; str so aceita str (True nao passa por texto, 1 nao passa por bool)."""
    if kind is object:
        return True
    return type(value) is kind


def _param_types(cls: type, name: str) -> list:
    sig = inspect.signature(getattr(cls, name))
    params = list(sig.parameters.values())[1:]          # sem self
    def kind(annotation: Any) -> type:
        if isinstance(annotation, type):
            return annotation if annotation in (str, bool) else object
        return _PY_TYPES.get(str(annotation), object)     # `from __future__ import annotations`: vem como texto
    return [kind(p.annotation) for p in params]


class Dispatcher:
    """Valida e chama um metodo do contrato. Separado do socket para testar sem rede."""

    def __init__(self, target: Any, methods: frozenset = RPC_METHODS) -> None:
        self.target = target
        self.methods = methods
        self._types = {name: _param_types(type(target), name) for name in methods if hasattr(type(target), name)}

    def handle(self, message: Any) -> Optional[dict]:
        """Um pedido JSON-RPC (ja decodificado) -> resposta (ou None se era notificacao)."""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return self._error(None, INVALID_REQUEST, "pedido invalido")
        rid = message.get("id")
        notify = "id" not in message
        name = message["method"]
        if name not in self.methods or name not in self._types:
            return None if notify else self._error(rid, METHOD_NOT_FOUND, f"metodo desconhecido: {name}")
        params = message.get("params", [])
        if not isinstance(params, list):
            return None if notify else self._error(rid, INVALID_PARAMS, "params deve ser uma lista")
        types = self._types[name]
        if len(params) != len(types):
            return None if notify else self._error(rid, INVALID_PARAMS, f"{name} espera {len(types)} argumento(s)")
        if not all(_matches(value, kind) for value, kind in zip(params, types)):
            return None if notify else self._error(rid, INVALID_PARAMS, f"{name}: tipo de argumento invalido")
        try:
            result = getattr(self.target, name)(*params)
        except Exception as exc:                       # nunca derruba o servidor
            print(f"  [server] {name} falhou: {type(exc).__name__}: {exc}")
            return None if notify else self._error(rid, INTERNAL_ERROR, f"{name} falhou: {type(exc).__name__}")
        if notify:
            return None
        return {"jsonrpc": "2.0", "id": rid, "result": _decode_payload(result)}

    @staticmethod
    def _error(rid: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


class EventServer:
    """WebSocket em thread propria. Thread-safe: `publish` pode ser chamado de qualquer thread."""

    def __init__(self, *, dev: bool = False, token: Optional[str] = None) -> None:
        self._dispatcher: Optional[Dispatcher] = None
        self.token = token or secrets.token_urlsafe(32)
        self.origins = ALLOWED_ORIGINS + (DEV_ORIGINS if dev else ())
        self.port = 0
        self._clients: Set[Any] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._error: Optional[BaseException] = None
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="rpc")
        self._last_level = 0.0
        self._tasks: Set[asyncio.Task] = set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="event-server")

    # ── Ciclo de vida ────────────────────────────────────────────────
    def start(self, timeout: float = 10.0) -> "EventServer":
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("servidor da interface nao subiu")
        if self._error is not None:
            raise self._error
        return self

    def stop(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._stop_in_loop)
        self._stopped.wait(5.0)
        self._pool.shutdown(wait=False, cancel_futures=True)

    def wait(self) -> None:
        self._stopped.wait()

    def attach(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher

    def _stop_in_loop(self) -> None:
        if self._server is not None:
            self._server.close()

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except BaseException as exc:            # erro ao subir: start() repassa
            self._error = exc
            self._ready.set()
        finally:
            self._stopped.set()

    async def _main(self) -> None:
        from websockets.asyncio.server import serve
        self._loop = asyncio.get_running_loop()
        async with serve(self._session, "127.0.0.1", 0, origins=[*self.origins, None],
                         max_size=MAX_MESSAGE_BYTES, ping_interval=20, ping_timeout=20) as server:
            self._server = server
            self.port = next(iter(server.sockets)).getsockname()[1]
            self._ready.set()
            await server.wait_closed()

    # ── Eventos ──────────────────────────────────────────────────────
    def publish(self, name: str, payload: Any = None) -> None:
        if name == "voiceLevel":
            now = time.monotonic()
            if now - self._last_level < VOICE_LEVEL_MIN_INTERVAL_S:
                return
            self._last_level = now
        loop = self._loop
        if loop is None or not self._clients:
            return
        frame = json.dumps({"jsonrpc": "2.0", "method": "event",
                            "params": {"name": name, "payload": _decode_payload(payload)}},
                           ensure_ascii=False, default=str)
        try:
            loop.call_soon_threadsafe(self._broadcast, frame)
        except RuntimeError:
            pass                                  # loop ja encerrado

    def _broadcast(self, frame: str) -> None:
        from websockets.asyncio.server import broadcast
        broadcast(set(self._clients), frame)

    # ── Sessao ───────────────────────────────────────────────────────
    async def _session(self, ws) -> None:
        try:
            if not await self._authenticate(ws):
                return
            async for raw in ws:
                task = asyncio.create_task(self._answer(ws, raw))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            self._clients.discard(ws)

    async def _authenticate(self, ws) -> bool:
        try:
            raw = await asyncio.wait_for(ws.recv(), AUTH_TIMEOUT_S)
            data = json.loads(raw)
            given = data.get("token") if isinstance(data, dict) else None
        except Exception:                         # timeout, JSON ruim, conexao caiu
            given = None
        if not isinstance(given, str) or not hmac.compare_digest(given.encode(), self.token.encode()):
            await ws.close(4401, "nao autorizado")
            return False
        # Registrado antes do hello: o cliente pode reagir ao hello e nenhum evento depois dele se perde.
        self._clients.add(ws)
        await ws.send(json.dumps({"jsonrpc": "2.0", "method": "hello",
                                  "params": {"protocol": PROTOCOL_VERSION}}))
        return True

    async def _answer(self, ws, raw: Any) -> None:
        try:
            message = json.loads(raw)
        except (ValueError, TypeError):
            await ws.send(json.dumps(Dispatcher._error(None, PARSE_ERROR, "JSON invalido")))
            return
        dispatcher = self._dispatcher
        if dispatcher is None:
            await ws.send(json.dumps(Dispatcher._error(message.get("id") if isinstance(message, dict) else None,
                                                       INTERNAL_ERROR, "nucleo ainda carregando")))
            return
        # Slots podem bloquear (disco, Segundo Cerebro): fora do loop do socket.
        reply = await asyncio.get_running_loop().run_in_executor(self._pool, dispatcher.handle, message)
        if reply is not None:
            try:
                await ws.send(json.dumps(reply, ensure_ascii=False, default=str))
            except Exception:
                pass                              # cliente saiu antes da resposta


class HeadlessBridge(BridgeCore):
    """BridgeCore sem Qt: cada evento vai para o servidor."""

    def __init__(self, server: EventServer) -> None:
        self._server = server
        self._setup_core()

    def _emit(self, name: str, payload: Any = None) -> None:
        self._server.publish(name, payload)


def serve_headless(*, dev: bool = False, ready_stream=None, stop_on_stdin_eof: bool = True) -> int:
    """`main.py --ui tauri --headless`: sobe o servidor, anuncia porta e token e espera.

    A linha `CREATIVE_AIX_READY {"port": .., "token": .., "protocol": ..}` vai so para `ready_stream`
    (o pipe da casca Tauri), nunca para o log. Quando a casca fecha o stdin, o nucleo encerra junto.
    """
    import sys

    server = EventServer(dev=dev).start()
    bridge = HeadlessBridge(server)
    server.attach(Dispatcher(bridge))
    stream = ready_stream or sys.__stdout__
    if stream is None:
        raise RuntimeError("modo headless precisa de stdout (pipe da casca Tauri)")
    stream.write(READY_PREFIX + json.dumps({"port": server.port, "token": server.token,
                                            "protocol": PROTOCOL_VERSION}) + "\n")
    stream.flush()

    if stop_on_stdin_eof and sys.stdin is not None:
        def watch_stdin() -> None:
            try:
                while sys.stdin.readline():
                    pass
            except (OSError, ValueError):
                pass
            server.stop()
        threading.Thread(target=watch_stdin, daemon=True, name="stdin-watch").start()

    try:
        server.wait()
    except KeyboardInterrupt:
        server.stop()
    finally:
        bridge.shutdown()
    return 0
