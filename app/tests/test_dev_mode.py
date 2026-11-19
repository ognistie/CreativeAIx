"""Modo Desenvolvedor (E3): niveis 1 e 2 validados por esquema; nivel 3 em worktree com lista fixa de
pastas, gate antes de aplicar, merge local e revert. Repositorio git de brinquedo, agente de codigo falso."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from core import dev_mode
from core.dev_mode import DevMode, path_violation


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                          encoding="utf-8").stdout


class DevSchemaTests(unittest.TestCase):
    def test_levels_1_and_2_are_validated(self):
        from core.harness import validate, DEFAULT
        self.assertFalse(DEFAULT["dev"]["enabled"])
        out = validate({"dev": {"enabled": True, "code_changes": "sim", "greeting": " Oi ", "hint": "x" * 500,
                                "shortcuts": [{"label": "Backup", "icon": "Bad Icon!", "request": "faca backup"},
                                              {"label": "", "request": "sem rotulo"}, "lixo"] + [{"label": f"a{i}", "request": "r"} for i in range(10)],
                                "cards": [{"title": "Relatório", "text": "Semanal", "request": "gere o relatorio", "icon": "chart"}]}})["dev"]
        self.assertTrue(out["enabled"])
        self.assertFalse(out["code_changes"])
        self.assertEqual(out["greeting"], "Oi")
        self.assertEqual(len(out["hint"]), 160)
        self.assertEqual(out["shortcuts"][0], {"label": "Backup", "icon": "", "request": "faca backup"})
        self.assertLessEqual(len(out["shortcuts"]), 8)
        self.assertEqual(out["cards"][0]["icon"], "chart")
        self.assertEqual(validate({"dev": "nada"})["dev"], DEFAULT["dev"])

    def test_path_rules(self):
        for path in ("../ui/src/views/Test.tsx", "ui/src/views/../../../outside.tsx", "/ui/src/views/Test.tsx", "C:/ui/src/views/Test.tsx"):
            self.assertIn("fora", path_violation(path))
        self.assertEqual(path_violation("ui/src/views/AboutView.tsx"), "")
        self.assertEqual(path_violation("ui/src/dev/Novo.tsx"), "")
        self.assertEqual(path_violation("ui/src/components/ui/Button.tsx"), "")
        self.assertIn("proibido", path_violation("app/core/action_risk.py"))
        self.assertIn("proibido", path_violation("config.yaml"))
        self.assertIn("proibido", path_violation("ui/src/views/.env"))
        self.assertIn("proibido", path_violation("ui/src/lib/host.ts"))
        self.assertIn("proibido", path_violation("ui/src/lib/core.ts"))
        self.assertIn("fora", path_violation("app/core/automation.py"))
        self.assertIn("fora", path_violation("ui/src/App.tsx"))
        self.assertIn("fora", path_violation("ui/dist/index.html"))
        self.assertIn("tipo", path_violation("ui/src/views/x.py"))


class DevWorktreeTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.mkdtemp(prefix="devmode-"))
        self.addCleanup(shutil.rmtree, base, True)
        self.repo = base / "repo"
        (self.repo / "ui" / "src" / "views").mkdir(parents=True)
        (self.repo / "app" / "core").mkdir(parents=True)
        (self.repo / "ui" / "src" / "views" / "AboutView.tsx").write_text("export const A = 1;\n")
        (self.repo / "app" / "core" / "action_risk.py").write_text("MODE = 'enforce'\n")
        (self.repo / "config.yaml").write_text("a: 1\n")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost", "commit", "-q", "--allow-empty", "-m", "init")
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost", "commit", "-q", "-m", "base")
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "config", "user.email", "t@localhost")
        self.calls = []
        self.gate_ok = True

        def runner(tool, prompt, folder, on_progress=None, **kw):
            self.calls.append((tool, folder))
            folder = Path(folder)
            self.assertTrue(prompt.startswith(dev_mode.PROMPT))
            prompt = prompt.split("PEDIDO: ", 1)[1]        # so o pedido decide o comportamento do falso
            self.assertNotIn(str(self.repo), str(folder))        # nunca na pasta do app
            self.assertEqual(folder.name, "ui")                  # a CLI trabalha na interface
            if "proibido" in prompt:
                (folder.parent / "app" / "core" / "action_risk.py").write_text("MODE = 'off'\n")
            if "fora" in prompt:
                (folder.parent / "config.yaml").write_text("a: 2\n")
            if "nada" not in prompt:
                (folder / "src" / "views" / "AboutView.tsx").write_text("export const A = 'v2';\n")
                (folder / "src" / "dev").mkdir(exist_ok=True)
                (folder / "src" / "dev" / "Novo.tsx").write_text("export const N = 1;\n")
            if "rede" in prompt:
                (folder / "src" / "views" / "AboutView.tsx").write_text(
                    "export const A = () => fetch('http://x.invalid');\n")
            if "falha" in prompt:
                return {"success": False, "result": "sem sessao"}
            return {"success": True, "result": "Mudei a tela Sobre."}

        self.gates = []
        def gate(worktree, say):
            self.gates.append(str(worktree))
            return {"ok": self.gate_ok, "detail": "CODE_READY True" if self.gate_ok else "FAIL: x"}

        self.rebuilds = []
        self.dev = DevMode(repo=self.repo, root=base / "dev", state=base / "state.json", runner=runner, gate=gate,
                           rebuild=lambda repo: self.rebuilds.append(str(repo)) or "")

    def worktrees(self):
        return [l for l in git(self.repo, "worktree", "list").splitlines()[1:]]

    def test_forbidden_or_outside_files_reject_the_whole_proposal(self):
        for word in ("proibido", "fora"):
            with self.subTest(word=word):
                p = self.dev.propose(f"mude algo {word} na tela", "claude")
                self.assertEqual(p["status"], "rejected", p)
                self.assertTrue(p["violations"])
                self.assertEqual(self.worktrees(), [], "worktree recusada nao foi removida")
                with self.assertRaises(ValueError):
                    self.dev.apply(p["id"])
        self.assertEqual((self.repo / "app" / "core" / "action_risk.py").read_text(), "MODE = 'enforce'\n")

    def test_full_cycle_propose_check_apply_undo(self):
        p = self.dev.propose("mude a tela Sobre para mostrar a versao", "codex")
        self.assertEqual(p["status"], "proposed", p)
        self.assertIn("AboutView.tsx", p["diff"])
        self.assertIn("dev/Novo.tsx", p["diff"])
        self.assertEqual(self.calls[0][0], "codex")
        with self.assertRaises(ValueError):          # sem gate nao aplica
            self.dev.apply(p["id"])
        self.gate_ok = False
        self.assertEqual(self.dev.check(p["id"])["status"], "gate_failed")
        with self.assertRaises(ValueError):
            self.dev.apply(p["id"])
        self.gate_ok = True
        self.assertEqual(self.dev.check(p["id"])["status"], "checked")
        self.assertEqual(len(self.gates), 2)
        before = git(self.repo, "rev-parse", "HEAD").strip()
        p = self.dev.apply(p["id"])
        self.assertEqual(p["status"], "applied")
        about = self.repo / "ui" / "src" / "views" / "AboutView.tsx"
        self.assertIn("v2", about.read_text())
        self.assertTrue((self.repo / "ui" / "src" / "dev" / "Novo.tsx").exists())
        self.assertEqual(len(self.rebuilds), 1, "aplicar gera a interface de novo")
        self.assertNotEqual(git(self.repo, "rev-parse", "HEAD").strip(), before)
        self.assertEqual(self.worktrees(), [])
        self.assertEqual(len(git(self.repo, "rev-list", "--parents", "-n", "1", "HEAD").split()), 3, "merge sem fast-forward")
        p = self.dev.undo(p["id"])
        self.assertEqual(p["status"], "reverted")
        self.assertEqual(about.read_text(), "export const A = 1;\n")
        self.assertFalse((self.repo / "ui" / "src" / "dev" / "Novo.tsx").exists())
        self.assertEqual(len(self.rebuilds), 2, "desfazer gera a interface de novo")
        self.assertEqual(self.dev.list()[0]["status"], "reverted")
        self.assertNotIn("diff", self.dev.list()[0])

    def test_proposal_adding_network_or_external_open_fails_before_the_gate(self):
        p = self.dev.propose("mude a tela Sobre e use a rede", "codex")
        self.assertEqual(p["status"], "proposed", p)
        p = self.dev.check(p["id"])
        self.assertEqual(p["status"], "gate_failed")
        self.assertIn("fetch(", p["gate"]["detail"])
        self.assertEqual(self.gates, [], "a proposta arriscada nao chega a rodar o gate")
        with self.assertRaises(ValueError):
            self.dev.apply(p["id"])

    def test_modified_worktree_cannot_apply_a_previous_gate_result(self):
        p = self.dev.propose("mude a tela Sobre para mostrar a versao", "codex")
        self.assertEqual(self.dev.check(p["id"])["status"], "checked")
        worktree = Path(p["worktree"])
        original_head = git(self.repo, "rev-parse", "HEAD")
        changed = worktree / "ui/src/views/AfterCheck.tsx"
        changed.write_text("export const B = 1;\n")
        with self.assertRaisesRegex(ValueError, "mudou"):
            self.dev.apply(p["id"])
        git(worktree, "add", "-A")
        with self.assertRaisesRegex(ValueError, "mudou"):
            self.dev.apply(p["id"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), original_head)
        self.assertFalse((self.repo / changed.relative_to(worktree)).exists())
        self.dev.discard(p["id"])

    def test_failed_run_and_discard_clean_up(self):
        p = self.dev.propose("isto vai dar falha na tela", "claude")
        self.assertEqual(p["status"], "failed")
        self.assertEqual(self.worktrees(), [])
        p = self.dev.propose("isto nao muda nada na tela", "claude")
        self.assertEqual(p["status"], "failed")
        p = self.dev.propose("mude a tela Sobre de novo", "claude")
        self.assertEqual(self.dev.discard(p["id"])["status"], "discarded")
        self.assertEqual(self.worktrees(), [])
        with self.assertRaises(ValueError):
            self.dev.propose("x", "claude")
        with self.assertRaises(ValueError):
            self.dev.propose("mude a tela Sobre", "gemini")


if __name__ == "__main__":
    unittest.main()
