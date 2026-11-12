"""Claude Code e Codex como agentes do app (E1): CLI falsa, sem rede, sem sessao real.

Aceite: tarefa roda na pasta certa, progresso chega, cancelar mata o processo, arquivo fora da
pasta = falha, sem sessao = mensagem clara e nenhuma credencial lida."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from core import coding_agents, process_runner
from core.coding_agents import build_command, parse_event, run


def project_tmp(prefix: str) -> Path:
    """Pasta de projeto FORA do repositorio: o gate aponta TMP para dentro do app, e a politica
    recusa (de proposito) a pasta do proprio AI Farm Agent."""
    base = APP.parent.parent / ".ai-farm-agent-tests"
    base.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=base))

# CLI falsa: fala os dois dialetos (stream-json do Claude Code, JSONL do Codex) e obedece ao prompt.
FAKE_CLI = r'''
import json, os, sys, time
from pathlib import Path
argv = sys.argv[1:]
cwd = Path.cwd()
def emit(obj): print(json.dumps(obj), flush=True)
if argv[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": not (cwd / ".logged_out").exists(), "authMethod": "oauth"})); sys.exit(0)
if argv[:2] == ["login", "status"]:
    if (cwd / ".logged_out").exists():
        print("Not logged in", file=sys.stderr); sys.exit(1)
    print("Logged in using ChatGPT"); sys.exit(0)
mode = "codex" if argv[:1] == ["exec"] else "claude"
prompt = sys.stdin.read()
(cwd / ".fake-argv.json").write_text(json.dumps(argv), encoding="utf-8")
(cwd / ".fake-env.json").write_text(json.dumps(sorted(os.environ)), encoding="utf-8")
if "demorado" in prompt:
    beat = cwd / "heartbeat"
    for i in range(600):
        beat.write_text(str(i)); time.sleep(0.05)
    sys.exit(0)
target = cwd.parent / "escapou.txt" if "fora" in prompt else cwd / "ola.txt"
if "fantasma" not in prompt:
    target.write_text(prompt, encoding="utf-8")
if mode == "claude":
    emit({"type": "system", "subtype": "init"})
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": "Vou criar o arquivo."},
          {"type": "tool_use", "name": "Write", "input": {"file_path": str(target)}}]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": "Criei o arquivo.", "total_cost_usd": 0.01})
else:
    emit({"type": "thread.started", "thread_id": "t"})
    emit({"type": "item.started", "item": {"type": "command_execution", "command": "ls"}})
    emit({"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": str(target), "kind": "add"}]}})
    emit({"type": "item.completed", "item": {"type": "agent_message", "text": "Criei o arquivo."}})
    emit({"type": "turn.completed", "usage": {}})
sys.exit(0)
'''


class CodingAgentsTests(unittest.TestCase):
    def setUp(self):
        self.root = project_tmp("extcode-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.fake = self.root / "fake_cli.py"
        self.fake.write_text(FAKE_CLI, encoding="utf-8")
        self.folder = self.root / "projeto"
        self.folder.mkdir()
        exe = [sys.executable, "-I", str(self.fake)]
        self.cfg = {"claude": {"exe": exe}, "codex": {"exe": exe}, "timeout_s": 30, "check_session": True}
        self.progress = []

    def _run(self, tool, prompt, **kw):
        return run(tool, prompt, str(self.folder), on_progress=self.progress.append, config=self.cfg, **kw)

    def _argv(self):
        return json.loads((self.folder / ".fake-argv.json").read_text(encoding="utf-8"))

    def test_claude_runs_in_the_chosen_folder_with_progress(self):
        out = self._run("claude", "crie um arquivo ola")
        self.assertTrue(out["success"], out)
        self.assertTrue(out["verified"], out)
        self.assertEqual((self.folder / "ola.txt").read_text(encoding="utf-8"), "crie um arquivo ola")
        argv = self._argv()
        for flag in ("-p", "stream-json", "--restricted", "acceptEdits", "--max-budget-usd"):
            self.assertIn(flag, argv, argv)
        self.assertIn("ola.txt", out["changed"]["added"])
        self.assertTrue(any("Vou criar o arquivo." in m for m in self.progress), self.progress)
        self.assertTrue(any("comecou" in m for m in self.progress), self.progress)
        self.assertIn("Claude Code concluiu", out["result"])

    def test_codex_runs_in_the_chosen_folder(self):
        out = self._run("codex", "crie um arquivo ola")
        self.assertTrue(out["success"], out)
        argv = self._argv()
        self.assertEqual(argv[0], "exec")
        self.assertIn("--json", argv)
        self.assertEqual(argv[argv.index("--cd") + 1], str(self.folder))
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
        self.assertTrue(any("comando: ls" in m for m in self.progress), self.progress)
        self.assertTrue((self.folder / "ola.txt").exists())

    def test_file_outside_the_folder_is_a_failure(self):
        for tool in ("claude", "codex"):
            with self.subTest(tool=tool):
                out = self._run(tool, "escreva fora")
                self.assertFalse(out["success"], out)
                self.assertEqual(out["status"], "failed")
                self.assertIn("fora da pasta", out["result"])
                self.assertIn("escapou.txt", out["result"])
                self.assertTrue(out["outside"])

    def test_reported_file_that_was_not_written_is_a_failure(self):
        for tool in ("claude", "codex"):
            with self.subTest(tool=tool):
                out = self._run(tool, "arquivo fantasma")
                self.assertFalse(out["success"], out)
                self.assertEqual(out["status"], "failed")
                self.assertIn("nao conseguiu gravar", out["result"])

    def test_stop_kills_the_process(self):
        beat = self.folder / "heartbeat"
        out = self._run("claude", "trabalho demorado", should_stop=beat.exists)
        self.assertEqual(out["status"], "cancelled", out)
        self.assertFalse(out["success"])
        self.assertIn("cancelado", out["result"])
        last = beat.read_text()
        time.sleep(0.6)
        self.assertEqual(beat.read_text(), last, "o processo continuou escrevendo depois de cancelado")

    def test_without_session_explains_how_to_login_and_does_nothing(self):
        (self.folder / ".logged_out").write_text("1")
        for tool, hint in (("claude", "/login"), ("codex", "codex login")):
            with self.subTest(tool=tool):
                out = self._run(tool, "crie um arquivo ola")
                self.assertEqual(out["status"], "needs_login", out)
                self.assertFalse(out["success"])
                self.assertIn(hint, out["result"])
                self.assertFalse((self.folder / "ola.txt").exists())
                self.assertFalse((self.folder / ".fake-argv.json").exists(), "a CLI rodou sem sessao")

    def test_child_never_receives_secrets(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x", "OPENAI_API_KEY": "y", "MY_TOKEN": "z",
                                     "CLAUDECODE": "1", "USERPROFILE": os.environ.get("USERPROFILE", "C:\\u")}):
            env = process_runner.child_environment()
            self._run("claude", "crie um arquivo ola")
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MY_TOKEN", "CLAUDECODE"):
            self.assertNotIn(key, env)
        self.assertIn("USERPROFILE", env)       # a CLI acha a propria sessao por aqui
        seen = json.loads((self.folder / ".fake-env.json").read_text(encoding="utf-8"))
        self.assertFalse([k for k in seen if "KEY" in k.upper() or "TOKEN" in k.upper()], seen)
        source = (APP / "core" / "coding_agents.py").read_text(encoding="utf-8")
        for needle in ("credentials.json", "auth.json", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            self.assertNotIn(needle, source)

    def test_missing_cli_and_bad_folder_are_clear(self):
        out = run("claude", "x", str(self.folder), config={"claude": {"exe": ["C:/nao/existe.exe"]}})
        self.assertEqual(out["status"], "failed")
        self.assertIn("nao foi encontrado", out["result"])
        out = run("claude", "x", str(APP), config=self.cfg)
        self.assertEqual(out["status"], "rejected")
        self.assertIn("proprio AI Farm Agent", out["result"])
        out = run("gemini", "x", str(self.folder), config=self.cfg)
        self.assertEqual(out["status"], "rejected")
        self.assertEqual(run("claude", "x", str(self.root / "nada"), config=self.cfg)["status"], "rejected")

    def test_commands_and_events(self):
        cmd = build_command("claude", ["claude.exe"], "C:/p", full_access=True)
        self.assertNotIn("--restricted", cmd)
        self.assertIn("--restricted", build_command("claude", ["claude.exe"], "C:/p"))
        self.assertIn("danger-full-access", build_command("codex", ["codex.exe"], "C:/p", full_access=True))
        self.assertIsNone(parse_event("claude", "not json"))
        self.assertIsNone(parse_event("claude", '{"type":"system"}'))
        ev = parse_event("codex", json.dumps({"type": "turn.failed", "error": {"message": "quota"}}))
        self.assertEqual((ev["kind"], ev["ok"], ev["text"]), ("result", False, "quota"))
        ev = parse_event("claude", json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True}))
        self.assertEqual(ev["ok"], False)
        self.assertEqual(coding_agents.tool_in("faz isso com o Claude Code"), "claude")
        self.assertEqual(coding_agents.tool_in("pede ao codex"), "codex")
        self.assertIsNone(coding_agents.tool_in("abre o paint"))


class ExtCodePolicyTests(unittest.TestCase):
    def setUp(self):
        self.folder = str(project_tmp("extcode-pol-"))
        self.addCleanup(shutil.rmtree, self.folder, True)

    def test_policy_rejects_other_agents_tools_and_the_app_folder(self):
        from core.action_policy import authorize
        self.assertEqual(authorize("EXTCODE", "x", "ext_code_task", {"folder": self.folder}), "")
        self.assertIn("proprio AI Farm Agent", authorize("EXTCODE", "x", "ext_code_task", {"folder": str(APP)}))
        self.assertIn("nao autorizada", authorize("CODE", "x", "ext_code_task", {"folder": self.folder}))
        self.assertIn("nao autorizada", authorize("EXTCODE", "x", "run_command", {"command": "dir"}))
        self.assertIn("nao autorizada", authorize("EXTCODE", "x", "open_in_editor", {"path": self.folder}))

    def test_validator_pol_010(self):
        from core.plan_validator import validate_plan, validate_steps
        good = [{"action": "ext_code_task", "params": {"tool": "claude", "folder": self.folder, "prompt": "x"}}]
        self.assertTrue(validate_steps("EXTCODE", {}, good, "x").approved)
        bad = [{"action": "ext_code_task", "params": {"tool": "claude", "folder": str(APP), "prompt": "x"}}]
        check = validate_steps("EXTCODE", {}, bad, "x")
        self.assertFalse(check.approved)
        self.assertEqual(check.violations[0]["policy"], "POL-010")
        two = good + [{"action": "wait", "params": {}}]
        self.assertFalse(validate_steps("EXTCODE", {}, two, "x").approved)
        plan = {"subtasks": [{"agent": "EXTCODE", "task": "Claude: x", "params": {"tool": "claude", "folder": self.folder}}]}
        self.assertTrue(validate_plan("faz x com o claude", plan).approved)

    def test_fast_path_plan(self):
        from agents.extcode_agent import extcode_plan
        from types import SimpleNamespace
        plan = extcode_plan(f"cria um readme no projeto {self.folder} com o claude", None)
        sub = plan["subtasks"][0]
        self.assertEqual(sub["agent"], "EXTCODE")
        self.assertEqual(sub["params"]["tool"], "claude")
        self.assertEqual(os.path.normcase(sub["params"]["folder"]), os.path.normcase(self.folder))
        self.assertNotIn("claude", sub["params"]["prompt"].lower())
        self.assertIn("readme", sub["params"]["prompt"])
        ask = extcode_plan("cria um readme com o codex", SimpleNamespace(code=None, folder=None))
        self.assertTrue(ask["needs_clarification"])
        self.assertIn("pasta", ask["question"])
        session = SimpleNamespace(code={"folder": self.folder, "files": []}, folder=None)
        plan = extcode_plan("pede ao codex para corrigir os testes", session)
        self.assertEqual(plan["subtasks"][0]["params"]["folder"], self.folder)
        self.assertEqual(plan["subtasks"][0]["params"]["tool"], "codex")
        self.assertIsNone(extcode_plan("abre o claude", session))
        self.assertIsNone(extcode_plan("abre o paint e desenha", session))
        self.assertTrue(extcode_plan(f"faz x em {APP} com o claude", None)["needs_clarification"])
        # Acao no computador "com o Claude Code / Codex" (ou pelo seletor do topo) nao pede pasta:
        # segue pelos agentes do computador, sem o nome da ferramenta
        empty = SimpleNamespace(code=None, folder=None)
        for said, rest in (("Abra o bloco de notas com o Claude Code", "Abra o bloco de notas"),
                           ("Abra o google com o Codex", "Abra o google"),
                           ("pesquise no google sobre IA com o Claude Code", "pesquise no google sobre IA")):
            plan = extcode_plan(said, empty)
            self.assertEqual(plan.get("reroute"), rest, said)
            self.assertNotIn("needs_clarification", plan)
        for code_task in ("abre o projeto loja no vs code com o claude", "abra o arquivo main.py com o codex e corrija o bug"):
            self.assertTrue(extcode_plan(code_task, empty)["needs_clarification"], code_task)

    def test_agent_plan_and_engine_dispatch(self):
        from agents.extcode_agent import ExtCodeAgent
        from core.automation import AutomationEngine
        from unittest.mock import Mock
        with patch("agents.base_agent.get_client", return_value=Mock()):
            agent = ExtCodeAgent()
        plan = agent.plan({"task": "Claude: x", "params": {"tool": "claude", "folder": self.folder, "prompt": "x"}})
        self.assertEqual(plan["steps"][0]["action"], "ext_code_task")
        self.assertTrue(agent.plan({"task": "x", "params": {"tool": "claude", "folder": str(APP)}}).get("error"))
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.executed_steps, engine.workspace, engine.should_stop = [], {}, None
        engine.current_agent, engine.authorized_task = "EXTCODE", "x"
        seen = []
        engine.on_progress = progress = seen.append
        fake = {"success": True, "status": "succeeded", "verified": True, "result": "ok"}
        with patch("core.coding_agents.run", return_value=fake) as mocked, \
             patch("core.automation._fg_state", return_value=(0, "")), patch("core.action_logger.log_action"):
            out = engine.execute("ext_code_task", {"tool": "claude", "folder": self.folder, "prompt": "x"})
            self.assertTrue(out["success"], out)
            self.assertIs(mocked.call_args.kwargs["on_progress"], progress)
            self.assertEqual(engine.execute("ext_code_task", {"tool": "claude", "folder": self.folder, "prompt": "x"},
                                            dry_run=True)["status"], "simulated")
            engine.current_agent = "CODE"
            self.assertEqual(engine.execute("ext_code_task", {"tool": "claude", "folder": self.folder, "prompt": "x"})["status"],
                             "rejected")
            self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
