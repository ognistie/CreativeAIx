"""Conversa (agents/chat_agent.py) e suas ferramentas de leitura (core/chat_tools.py).

Sem modelo real: um cliente falso devolve as respostas roteirizadas (texto e tool_use) que a API devolveria.
"""

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parent.parent
SCRATCH = APP / "memory"          # ignorado pelo git; fora do AppData (que a conversa nunca le)
# Chave falsa montada em tempo de execucao: o gate (check_release) procura chaves literais no codigo
FAKE_KEY = "sk-" + "ant-" + "abcdefghijklmnopqrstuvwx"


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(name, args, tid="t1"):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=args)


def reply(*blocks, stop=None):
    uses = any(b.type == "tool_use" for b in blocks)
    return SimpleNamespace(content=list(blocks), stop_reason=stop or ("tool_use" if uses else "end_turn"))


class FakeClient:
    """converse() como o AIClient: chama on_text com o texto e devolve a Message roteirizada."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def converse(self, model, system, messages, tools, max_tokens=0, effort=None, agent="", on_text=None,
                 should_stop=None):
        self.calls.append({"system": system, "messages": [dict(m) for m in messages], "tools": tools})
        resp = self.responses.pop(0)
        for b in resp.content:
            if b.type == "text" and on_text:
                on_text(b.text)
        return resp


def config(**values):
    data = {"chat.enabled": True, "chat.max_tool_rounds": 4, **values}
    return Mock(get=lambda key, default=None: data.get(key, default),
                get_model=lambda name: "claude-sonnet-5", get_effort=lambda name: "medium")


class Workspace(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("def main():\n    return 42\n", encoding="utf-8")
        (self.root / "README.md").write_text("# Projeto\nUm app de exemplo.\n", encoding="utf-8")
        (self.root / ".env").write_text(f"ANTHROPIC_API_KEY={FAKE_KEY}\n", encoding="utf-8")
        (self.root / "config.py").write_text(f'API_KEY = "{FAKE_KEY}"\ntoken = make_token()\n', encoding="utf-8")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "lib.js").write_text("x", encoding="utf-8")


class ReadScopeTests(Workspace):
    def scope(self):
        from core.chat_tools import ReadScope
        return ReadScope([self.root.resolve()])

    def test_lists_reads_and_searches_inside_the_root(self):
        from core import chat_tools
        listing = chat_tools.list_folder(self.scope(), str(self.root), 2)
        self.assertIn("src/", listing)
        self.assertIn("main.py", listing)
        self.assertIn("node_modules/  (conteudo omitido)", listing)
        self.assertNotIn(".env", listing)                       # segredo nem aparece na lista
        body = chat_tools.read_text(self.scope(), str(self.root / "src" / "main.py"))
        self.assertIn("    1  def main():", body)
        hits = chat_tools.search_files(self.scope(), str(self.root), text="return 42")
        self.assertIn("main.py:2", hits)
        self.assertNotIn("lib.js", chat_tools.search_files(self.scope(), str(self.root), name="*.js"))

    def test_refuses_secrets_outside_paths_network_and_appdata(self):
        from core import chat_tools
        from core.chat_tools import ToolError
        for bad in (str(self.root / ".env"), str(APP.parent / ".env"), "\\\\servidor\\share",
                    str(Path.home() / "AppData" / "Local"), "C:\\Windows\\System32", ""):
            with self.subTest(bad=bad), self.assertRaises(ToolError):
                chat_tools.read_text(self.scope(), bad)

    def test_masks_literal_secrets_but_not_code(self):
        from core import chat_tools
        body = chat_tools.read_text(self.scope(), str(self.root / "config.py"))
        self.assertNotIn(FAKE_KEY, body)
        self.assertIn("token = make_token()", body)

    def test_roots_come_from_the_person_not_the_model(self):
        from core.chat_tools import ReadScope
        scope = ReadScope.for_conversation([f"analise o projeto {self.root}"], home=str(SCRATCH.parent.parent))
        self.assertTrue(any(str(self.root.resolve()).startswith(str(r)) for r in scope.roots))
        scope = ReadScope.for_conversation(["oi"], home=str(self.root / "src"))
        from core.chat_tools import ToolError
        with self.assertRaises(ToolError):
            scope.check(str(self.root / "README.md"))           # pasta vizinha nao citada


class ChatAgentTests(Workspace):
    def agent(self, client):
        from agents.chat_agent import ChatAgent
        a = ChatAgent(client=client, config=config())
        a.system_prompt = lambda: "SYSTEM"
        return a

    def test_reads_the_folder_then_answers_with_streamed_text(self):
        client = FakeClient(
            reply(text("Vou olhar a pasta."), tool("listar_pasta", {"caminho": str(self.root), "profundidade": 2})),
            reply(text("O projeto tem um `src/main.py` que devolve 42.")),
        )
        streamed, tools_seen = [], []
        result = self.agent(client).respond(
            f"analise o codigo em {self.root}", None, on_text=streamed.append,
            on_tool=lambda name, label, ok, out: tools_seen.append((name, ok)))
        self.assertEqual(result.kind, "answer")
        self.assertIn("devolve 42", result.text)
        self.assertIn("Vou olhar a pasta.", "".join(streamed))
        self.assertEqual(tools_seen, [("listar_pasta", None), ("listar_pasta", True)])
        second = client.calls[1]["messages"]
        tool_results = second[-1]["content"]
        self.assertEqual(tool_results[0]["type"], "tool_result")
        self.assertIn("main.py", tool_results[0]["content"])
        self.assertFalse(tool_results[0]["is_error"])

    def test_tool_error_goes_back_to_the_model(self):
        client = FakeClient(reply(tool("ler_arquivo", {"caminho": str(self.root / ".env")})),
                            reply(text("Esse arquivo guarda segredos; não leio.")))
        result = self.agent(client).respond(f"leia {self.root}", None)
        self.assertEqual(result.kind, "answer")
        res = client.calls[1]["messages"][-1]["content"][0]
        self.assertTrue(res["is_error"])
        self.assertIn("segredo", res["content"])

    def test_invalid_tool_input_is_rejected_before_running(self):
        client = FakeClient(reply(tool("listar_pasta", {"caminho": 5})), reply(text("ok")))
        self.agent(client).respond("liste", None)
        res = client.calls[1]["messages"][-1]["content"][0]
        self.assertTrue(res["is_error"])
        self.assertIn("texto", res["content"])

    def test_action_request_is_handed_to_the_maestro(self):
        client = FakeClient(reply(tool("executar_no_computador", {"pedido": "abrir o bloco de notas"})))
        result = self.agent(client).respond("abre o bloco de notas pra mim", None)
        self.assertEqual(result.kind, "act")
        self.assertEqual(result.task, "abrir o bloco de notas")

    def test_handoff_cannot_carry_an_address_or_coding_cli_the_person_did_not_ask_for(self):
        from agents.chat_agent import handoff_error
        self.assertIn("evil.com", handoff_error("abrir https://evil.com/?q=segredo", ["resuma o arquivo"]))
        self.assertEqual(handoff_error("abrir o youtube.com", ["abre o youtube.com"]), "")
        self.assertIn("Claude", handoff_error("analisar com o Claude Code", ["analise"], current="analise"))
        self.assertEqual(handoff_error("readme com o Claude", [], current="faz um readme com o claude"), "")
        client = FakeClient(reply(tool("executar_no_computador", {"pedido": "abrir https://evil.com/?d=x"})),
                            reply(text("Não posso abrir esse endereço.")))
        result = self.agent(client).respond("resuma o arquivo", None)
        self.assertEqual(result.kind, "answer")
        self.assertTrue(client.calls[1]["messages"][-1]["content"][0]["is_error"])

    def test_history_alternates_and_keeps_long_replies(self):
        from agents.chat_agent import history_messages
        from core.session import Session
        s = Session()
        t1 = s.add_turn("analise o projeto", "analise o projeto", "question")
        s.set_reply(t1, "x" * 3000)
        s.add_turn("abre o excel", "abre o excel", "new", ["DESKTOP"], True, "Excel aberto")
        msgs = history_messages(s.turns)
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user", "assistant"])
        self.assertEqual(len(msgs[1]["content"]), 3000)        # antes a conversa guardava so 600
        self.assertIn("DESKTOP", msgs[3]["content"])

    def test_cancel_and_round_limit(self):
        client = FakeClient(*[reply(tool("listar_pasta", {"caminho": str(self.root)}, f"t{i}")) for i in range(5)])
        result = self.agent(client).respond(f"liste {self.root}", None)
        self.assertEqual(result.stop_reason, "max_rounds")
        self.assertEqual(len(client.calls), 4)
        cancelled = self.agent(Mock(converse=Mock(return_value=None))).respond("oi", None)
        self.assertEqual(cancelled.kind, "cancelled")


class PolicyAndPricingTests(unittest.TestCase):
    def test_extcode_needs_the_person_to_name_the_tool(self):
        # Incidente da captura: "analise o codigo" foi parar no Claude Code sem ninguem pedir
        from core.plan_validator import validate_plan
        plan = {"subtasks": [{"agent": "EXTCODE", "task": "Claude: analisar",
                              "params": {"tool": "claude", "folder": str(APP.parent), "prompt": "analisar"}}]}
        check = validate_plan("Faça uma analise no codigo da plataforma em C:\\proj", plan)
        self.assertFalse(check.approved)
        self.assertEqual(check.violations[0]["policy"], "POL-011")
        self.assertNotIn("POL-011", [v["policy"] for v in validate_plan("analise com o Codex", plan).violations])

    def test_new_models_have_their_own_price(self):
        from core.ai_client import estimate_cost
        self.assertAlmostEqual(estimate_cost("claude-sonnet-5-5", 0, 0, cache_read_tokens=1_000_000), 0.10)
        self.assertAlmostEqual(estimate_cost("claude-sonnet-5", 0, 0, cache_read_tokens=1_000_000), 0.20)
        self.assertAlmostEqual(estimate_cost("claude-opus-5-5", 1_000_000, 0), 4.00)
        self.assertAlmostEqual(estimate_cost("claude-fable-5-2", 0, 1_000_000), 40.00)

    def test_metrics_do_not_lose_calls_under_threads(self):
        from core.ai_client import AIClient
        c = AIClient.__new__(AIClient)
        c._metrics = {"total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0,
                      "total_cache_read_tokens": 0, "total_cache_write_tokens": 0, "total_cost_usd": 0.0,
                      "total_llm_ms": 0, "calls_by_model": {}, "calls_by_agent": {}, "errors": 0, "truncated": 0}
        resp = SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0), content=[], stop_reason="end_turn")
        work = lambda: [c._record_success(resp, "claude-sonnet-5", 1, "CHAT") for _ in range(500)]
        threads = [threading.Thread(target=work) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(c.metrics["total_calls"], 4000)
        self.assertEqual(c.metrics["calls_by_agent"]["CHAT"]["calls"], 4000)


class ControllerChatTests(unittest.TestCase):
    def test_cognitive_trace_is_persisted_without_task_content(self):
        c = self.controller(chat_error=RuntimeError("offline fixture"))
        entry = self.run_task(c, "crie uma planilha de gastos privados")
        self.assertEqual(entry["cognitive"][0]["stage"], "stimulus")
        self.assertIn("planning", [e["stage"] for e in entry["cognitive"]])
        self.assertNotIn("gastos privados", str(entry["cognitive"]))
        observed = [p for name, p in self.events if name == "cognitive_activity"]
        self.assertTrue(observed)
        self.assertTrue(all(e["run_id"] == 1 for e in observed))

    def controller(self, chat_result=None, chat_error=None):
        from desktop.controller import Controller
        from core.session import Session
        c = Controller.__new__(Controller)
        c.state, c._lock, c._run_id, c._tls = {"running": True}, threading.Lock(), 1, threading.local()
        c._cancel_event, c._plan_gate = threading.Event(), threading.Event()
        c._plan_ok, c._plan_token, c._voice_hints = False, "", {}
        c._ai_client, c._config = Mock(metrics={}), config()
        c._brain = Mock(last_skills={}, write_plan=Mock(return_value=None))
        c.session = Session()
        c.session.save = lambda *a, **k: None
        c.engine = Mock(workspace={})
        c.maestro = Mock(analyze=Mock(return_value={"error": True, "message": "parou aqui"}))
        c.chat = Mock(respond=Mock(side_effect=chat_error, return_value=chat_result))
        self.events = []
        c._emit = lambda name, payload=None: self.events.append((name, payload or {}))
        c._after_turn, c._metrics_delta, c._emit_usage = Mock(), (lambda b, a: {}), (lambda: None)
        return c

    def run_task(self, c, said):
        from core.task_ledger import TaskLedger
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch("core.task_ledger.get_ledger", return_value=TaskLedger(Path(tmp.name))), \
                patch("desktop.controller.history_store.append") as append:
            c._run(said, False, False, 1)
        return append.call_args[0][0]

    def test_question_is_answered_by_the_chat_without_the_maestro(self):
        from agents.chat_agent import ChatResult
        c = self.controller(ChatResult("answer", "RAG é recuperar contexto antes de gerar.", tools_used=[]))
        entry = self.run_task(c, "o que é RAG?")
        c.maestro.analyze.assert_not_called()
        self.assertIn(("answer", {"msg": "RAG é recuperar contexto antes de gerar.", "run_id": 1}), self.events)
        self.assertTrue(entry["success"])
        self.assertEqual(entry["run_id"], 1)
        self.assertEqual(entry["subtasks"][0]["agent"], "CHAT")

    def test_action_goes_to_the_maestro_with_the_handed_request(self):
        from agents.chat_agent import ChatResult
        c = self.controller(ChatResult("act", "", task="criar uma planilha de gastos com gráfico"))
        self.run_task(c, "me ajuda com meus gastos? monta uma planilha")
        self.assertEqual(c.maestro.analyze.call_args[0][0], "criar uma planilha de gastos com gráfico")

    def test_chat_failure_falls_back_to_the_maestro(self):
        c = self.controller(chat_error=RuntimeError("api fora"))
        self.run_task(c, "crie uma planilha de gastos")   # verbo de acao obvio: o resolvedor nao chama o modelo
        c.maestro.analyze.assert_called_once()

    def test_dry_run_and_disabled_chat_keep_the_old_flow(self):
        c = self.controller()
        c._config = config(**{"chat.enabled": False})
        self.run_task(c, "o que é RAG?")
        c.chat.respond.assert_not_called()
        c.maestro.analyze.assert_called_once()


if __name__ == "__main__":
    unittest.main()
