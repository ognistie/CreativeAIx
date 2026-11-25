"""Falhas achadas nas conversas reais de 2026-11-25 (API real) e nos prints dos usuarios, cada uma com seu teste.

F1 "qual modelo estou usando?" sem resposta; F4 "abra o relatorio" recusado pelo escopo; F6 planilha com
categoria acentuada recusada; F7 motivo da falha escondido; F9 "abre o projeto no VS Code" sem projeto;
Claude Code/Codex do app MSIX nao encontrados; pergunta virando sugestao no Cerebro; voz sem a conversa.
"""

import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

APP = Path(__file__).resolve().parent.parent
SCRATCH = APP / "memory"


class Tmp(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)


class OpenAndScopeTests(Tmp):
    def test_chat_opens_the_exact_file_but_never_a_program(self):
        from agents.chat_agent import open_plan
        from core.chat_tools import ReadScope, ToolError
        (self.root / "relatorio.md").write_text("# r", encoding="utf-8")
        (self.root / "setup.exe").write_bytes(b"MZ")
        (self.root / "script.py").write_text("print(1)", encoding="utf-8")
        scope = ReadScope([self.root.resolve()])
        plan = open_plan(str(self.root / "relatorio.md"), False, scope)
        existing = plan["subtasks"][0]["params"]["existing"]
        self.assertEqual(existing, {"action": "open_path", "path": str((self.root / "relatorio.md").resolve())})
        self.assertEqual(open_plan(str(self.root / "script.py"), True, scope)["subtasks"][0]["params"]["existing"]["action"],
                         "open_in_editor")                         # script abre no editor, nunca pelo sistema
        for bad, editor in ((self.root / "setup.exe", False), (self.root / "script.py", False), (self.root / "setup.exe", True)):
            with self.subTest(bad=bad.name, editor=editor), self.assertRaises(ToolError):
                open_plan(str(bad), editor, scope)

    def test_file_agent_scope_includes_what_the_conversation_already_released(self):
        # F4: "abra o relatorio para mim" nao cita caminho; a pasta veio duas falas antes ou foi criada pelo app
        from core.file_contracts import CONVERSATION_ROOTS, conversation_roots, request_roots, validate
        from core.session import Session
        s = Session()
        s.add_turn(f"analise o projeto em {self.root}", "", "question")
        s.remember_files([str(self.root / "out" / "x.xlsx")])
        (self.root / "out").mkdir()
        roots = conversation_roots(s)
        self.assertIn(os.path.realpath(self.root), roots)
        step = [{"action": "open_path", "params": {"path": str(self.root / "README.md")}}]
        self.assertIn("Informe a pasta", validate(step, request_roots("abra o relatorio para mim")))
        token = CONVERSATION_ROOTS.set(tuple(roots))
        try:
            self.assertEqual(validate(step, request_roots("abra o relatorio para mim")), "")
            out = []                              # outra thread (outra execucao) nao herda o escopo
            other = threading.Thread(target=lambda: out.append(CONVERSATION_ROOTS.get()))
            other.start()
            other.join()
            self.assertEqual(out, [()])
        finally:
            CONVERSATION_ROOTS.reset(token)
        self.assertEqual(CONVERSATION_ROOTS.get(), ())

    def test_project_comes_from_the_folder_the_person_cited(self):
        # F9: "abre o projeto no vs code" logo depois de conversar sobre o repositorio
        from core.existing_targets import existing_plan
        from core.session import Session
        (self.root / ".git").mkdir()
        (self.root / "docs").mkdir()
        s = Session()
        s.add_turn(f"quais documentos tem em {self.root / 'docs'}?", "", "question")
        plan = existing_plan("abre o projeto no vs code", s)
        self.assertEqual(plan["subtasks"][0]["params"]["existing"],
                         {"action": "open_in_editor", "path": str(self.root)})


class BuilderAndSuggestionTests(unittest.TestCase):
    def test_formula_with_accented_text_is_accepted_but_dde_is_not(self):
        # F6: toda planilha pt-BR com total por categoria falhava duas vezes
        from core.artifact_builder import _cell
        _cell('=SUMIF(B:B,"Alimentação",D:D)')
        _cell('=IF(D2>100,"Atenção!","ok")&" R$"')
        for bad in ("=cmd|' /C calc'!A0", '=HYPERLINK("http://x")', "='Outra aba'!A1", '=SUM(A1:A2', '="abc'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _cell(bad)

    def test_conversation_turns_never_become_brain_suggestions(self):
        from core.suggestions import from_execution
        for subtasks in ([{"agent": "CHAT"}], [], [{"agent": "READER"}]):
            entry = {"task": "qual modelo estou usando?", "success": False, "error": "Sem subtasks", "subtasks": subtasks}
            self.assertIsNone(from_execution(entry, [], False))
        real = {"task": "abrir planilha", "success": False, "error": "janela errada", "subtasks": [{"agent": "DESKTOP"}]}
        self.assertEqual(from_execution(real, [], False)["kind"], "licao")


class ChatContextTests(unittest.TestCase):
    def test_model_is_in_the_context_and_voice_gets_a_spoken_answer(self):
        from agents.chat_agent import ChatAgent
        seen = {}

        def converse(model, system, messages, tools, **kw):
            seen["content"] = messages[-1]["content"]
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")], stop_reason="end_turn")

        data = {"chat.max_tool_rounds": 2}
        cfg = Mock(get=lambda k, d=None: data.get(k, d), get_model=lambda n: "claude-sonnet-5", get_effort=lambda n: "medium")
        agent = ChatAgent(client=Mock(converse=converse), config=cfg)
        agent.system_prompt = lambda: "S"
        agent.respond("qual modelo estou usando?", None, spoken=True)
        self.assertIn("Modelo desta conversa: claude-sonnet-5", seen["content"])
        self.assertIn("FALADO", seen["content"])


class ChatPowerTests(unittest.TestCase):
    """Respostas ricas: busca na web com fontes; e a garantia da main de que comentario nunca vira tarefa."""

    def agent(self, *responses, **cfg_values):
        from agents.chat_agent import ChatAgent
        data = {"chat.max_tool_rounds": 4, **cfg_values}
        calls = []
        replies = list(responses)

        def converse(model, system, messages, tools, **kw):
            calls.append({"tools": [t["name"] for t in tools], "messages": list(messages)})
            return replies.pop(0)

        cfg = Mock(get=lambda k, d=None: data.get(k, d), get_model=lambda n: "claude-sonnet-5", get_effort=lambda n: "medium")
        agent = ChatAgent(client=Mock(converse=converse), config=cfg)
        agent.system_prompt = lambda: "S"
        return agent, calls

    def test_web_search_is_offered_and_pause_turn_continues(self):
        text = lambda t: SimpleNamespace(type="text", text=t)
        agent, calls = self.agent(SimpleNamespace(content=[text("Buscando...")], stop_reason="pause_turn"),
                                  SimpleNamespace(content=[text(" A versão atual é X. Fontes: ...")], stop_reason="end_turn"))
        result = agent.respond("qual a versão mais recente do Python?", None)
        self.assertIn("web_search", calls[0]["tools"])
        self.assertEqual(len(calls), 2)                            # pause_turn: o servidor continua a mesma volta
        self.assertEqual(calls[1]["messages"][-1]["role"], "assistant")
        self.assertEqual(result.text, "Buscando... A versão atual é X. Fontes: ...")
        off, calls = self.agent(SimpleNamespace(content=[text("ok")], stop_reason="end_turn"), **{"chat.web_search": False})
        off.respond("oi", None)
        self.assertNotIn("web_search", calls[0]["tools"])

    def test_without_actions_a_comment_never_becomes_a_task(self):
        use = SimpleNamespace(type="tool_use", id="t1", name="executar_no_computador", input={"pedido": "editar o site"})
        agent, calls = self.agent(SimpleNamespace(content=[use], stop_reason="tool_use"),
                                  SimpleNamespace(content=[SimpleNamespace(type="text", text="Que bom que gostou!")],
                                                  stop_reason="end_turn"))
        result = agent.respond("legal, ficou bom", None, allow_actions=False)
        self.assertNotIn("executar_no_computador", calls[0]["tools"])
        self.assertNotIn("abrir_no_computador", calls[0]["tools"])
        self.assertEqual(result.kind, "answer")                    # mesmo se o modelo tentasse, nao executa
        self.assertTrue(calls[1]["messages"][-1]["content"][0]["is_error"])


class ControllerFindingsTests(unittest.TestCase):
    def controller(self):
        from desktop.controller import Controller
        from core.session import Session
        c = Controller.__new__(Controller)
        c.state, c._lock, c._run_id, c._tls = {"running": True}, threading.Lock(), 1, threading.local()
        c._cancel_event, c._plan_gate = threading.Event(), threading.Event()
        c._plan_ok, c._plan_token, c._voice_hints = False, "", {}
        data = {"chat.enabled": True}
        c._ai_client = Mock(metrics={})
        c._config = Mock(get=lambda k, d=None: data.get(k, d))
        c._brain = Mock(last_skills={}, write_plan=Mock(return_value=None))
        c.session = Session()
        c.session.save = lambda *a, **k: None
        c.engine, c.capture, c.memory = Mock(workspace={}), Mock(), Mock()
        c._ContextManager = __import__("core.context_manager", fromlist=["ContextManager"]).ContextManager
        c.maestro = Mock(analyze=Mock(return_value={"subtasks": [{"agent": "DATA", "task": "planilha"}], "skills": []}))
        c.agents = {"DATA": Mock(plan=Mock(return_value={"error": "Formula contem recurso nao permitido."}))}
        c._emit = lambda *a, **k: None
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

    def test_agent_plan_failure_reason_reaches_the_reply(self):
        # F7: a resposta dizia "algo deu errado" sem o motivo
        from agents.chat_agent import ChatResult
        c = self.controller()
        c.chat = Mock(respond=Mock(return_value=ChatResult("act", "", task="criar planilha de gastos")))
        entry = self.run_task(c, "crie uma planilha de gastos")
        self.assertIn("Formula contem recurso nao permitido", entry["error"])

    def test_voice_requests_use_the_chat_and_open_app_skips_it(self):
        from agents.chat_agent import ChatResult
        c = self.controller()
        c.chat = Mock(respond=Mock(return_value=ChatResult("answer", "Posso abrir apps e ler seus arquivos.")))
        c._voice_hints["o que você faz?"] = {"kind": "new", "target": None}
        c._tls.voice = True                       # origem real da fala (execute_task(voice=True) marca a thread)
        self.run_task(c, "o que você faz?")
        self.assertTrue(c.chat.respond.call_args.kwargs["spoken"])
        c._tls.voice = False
        c.chat.respond.reset_mock()
        with patch("agents.maestro.shortcut_open_plan", return_value={"subtasks": [], "skills": []}):
            self.run_task(c, "abre o bloco de notas")
        c.chat.respond.assert_not_called()

    def test_typed_small_talk_gets_a_real_answer_without_actions(self):
        # "valeu" digitado: antes frase pronta; agora a conversa responde, mas sem ferramentas de acao
        from agents.chat_agent import ChatResult
        c = self.controller()
        c.chat = Mock(respond=Mock(return_value=ChatResult("answer", "De nada! A planilha ficou salva em Documentos.")))
        entry = self.run_task(c, "valeu!")
        self.assertFalse(c.chat.respond.call_args.kwargs["allow_actions"])
        self.assertEqual(entry["subtasks"][0]["agent"], "CHAT")
        c.chat.respond.reset_mock()
        c._tls.voice = True                       # na voz o papo fica na resposta rapida do entendimento
        self.run_task(c, "valeu!")
        c._tls.voice = False
        c.chat.respond.assert_not_called()


class CodingAgentDiscoveryTests(Tmp):
    def test_finds_claude_code_bundled_with_the_msix_claude_app(self):
        from core import coding_agents
        exe = self.root / "Claude-Data" / "claude_abc" / "claude-code" / "2.1.330" / "hash" / "claude.exe"
        old = self.root / "Claude-Data" / "claude_abc" / "claude-code" / "2.1.9" / "hash" / "claude.exe"
        for p in (exe, old):
            p.parent.mkdir(parents=True)
            p.write_bytes(b"MZ")
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root), "APPDATA": str(self.root / "roaming")}), \
                patch("core.coding_agents.shutil.which", return_value=None):
            self.assertEqual(coding_agents.executable("claude", {}), [str(exe)])
        cmd = coding_agents.login_command("claude", [str(exe)])
        self.assertTrue(cmd.startswith('& "') and cmd.endswith('claude.exe" auth login'))
        self.assertIn(coding_agents.login_command("codex", [r"C:\Program Files\x\codex.exe"]),
                      coding_agents.login_help("codex", [r"C:\Program Files\x\codex.exe"]))

    def test_finds_codex_inside_the_msix_package_through_the_registry(self):
        from core import coding_agents
        cli = self.root / "OpenAI.Codex_26.1117.4957.0_x64__2p2" / "app" / "resources" / "codex.exe"
        cli.parent.mkdir(parents=True)
        cli.write_bytes(b"MZ")
        with patch("core.coding_agents._msix_roots", return_value=[str(cli.parents[2])]), \
                patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "none")}), \
                patch("core.coding_agents.shutil.which", return_value=None):
            self.assertEqual(coding_agents.executable("codex", {}), [str(cli)])


class ClaudeDesktopConnectorTests(Tmp):
    def test_bundle_has_a_valid_manifest_and_launcher(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("connector", APP / "scripts" / "claude_desktop_connector.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        path = mod.build_bundle(self.root)
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            m = json.loads(z.read("manifest.json"))
            launcher = z.read("server/launch.py").decode("utf-8")
        self.assertTrue({"manifest.json", "server/launch.py"} <= names)
        for key in ("manifest_version", "name", "version", "description", "author", "server"):
            self.assertIn(key, m)
        self.assertEqual(m["server"]["entry_point"], "server/launch.py")
        self.assertEqual(m["server"]["mcp_config"]["args"], ["${__dirname}/server/launch.py"])
        self.assertEqual({t["name"] for t in m["tools"]},
                         {"brain_search", "brain_read", "task_status", "recent_tasks", "list_projects"})
        compile(launcher, "launch.py", "exec")
        self.assertIn("mcp_server.py", launcher)


if __name__ == "__main__":
    unittest.main()
