"""Depois que o Claude Code / Codex criam um projeto, "abre pra mim" sabe qual e (incidente 2026-11-15:
o Codex criou o site e o pedido seguinte respondeu "Ainda nao criei nenhum projeto nesta conversa")."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.extcode_agent import extcode_plan
from core.existing_targets import existing_plan
from core.observer import observe
from core.session import Session


class ExtCodeFollowupTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.folder = os.path.join(self.root, "Nova pasta")
        os.makedirs(self.folder)
        Path(self.folder, "index.html").write_text("<html></html>", encoding="utf-8")

        # O gate (check_release) poe TEMP dentro do repositorio, e a pasta do proprio app e recusada de proposito
        guard = patch("core.coding_agents.is_app_repo", return_value=False)
        guard.start()
        self.addCleanup(guard.stop)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_extcode_run_becomes_the_conversation_project(self):
        s = Session()
        seen = observe("EXTCODE", {"tool": "codex", "folder": self.folder}, {}, s)
        self.assertIn("code", seen)
        self.assertEqual(s.code["folder"], self.folder)
        plan = existing_plan("abre a pasta do projeto", s)
        self.assertEqual(plan["subtasks"][0]["params"]["existing"], {"action": "open_path", "path": self.folder})

    def test_cited_folder_is_used_without_a_recorded_project(self):
        plan = existing_plan(f"Abrir a pasta do projeto {self.folder} com o Codex", Session())
        self.assertFalse(plan.get("needs_clarification"), plan)
        self.assertEqual(plan["subtasks"][0]["params"]["existing"]["path"], self.folder)

    def test_vs_code_in_the_conversation_opens_in_the_editor(self):
        s = Session()
        s.add_turn("crie um site no meu vs code com o Codex", "crie um site", "new", ["EXTCODE"], True,
                   "Site pronto. Quer que eu abra no VS Code?")
        plan = existing_plan(f"Abrir a pasta do projeto {self.folder}", s)
        self.assertEqual(plan["subtasks"][0]["params"]["existing"]["action"], "open_in_editor")

    def test_vs_code_request_adds_the_open_step_after_the_cli(self):
        plan = extcode_plan(f"crie um site no meu vs code com o Codex em {self.folder}")
        self.assertEqual([x["agent"] for x in plan["subtasks"]], ["EXTCODE", "DESKTOP"], plan)
        self.assertEqual(plan["subtasks"][1]["params"]["existing"], {"action": "open_in_editor", "path": self.folder})
        plain = extcode_plan(f"crie um site com o Codex em {self.folder}")
        self.assertEqual([x["agent"] for x in plain["subtasks"]], ["EXTCODE"])


if __name__ == "__main__":
    unittest.main()
