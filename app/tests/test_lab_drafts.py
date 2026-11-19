import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.brain_store import BrainStore
from core.lab_drafts import draft_route


class LabDraftRoutes(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.store = BrainStore(root / "base", root / "personal")
        self.note = "10 Agentes/Rascunhos/conferencia.md"
        self.store.create(self.note, "---\ntipo: agente-rascunho\nbase: FILE\n---\n# Conferência\n")

    def call(self, action, **values):
        return draft_route(self.store, {"note": self.note, "action": action, **values})

    def test_preview_save_apply_and_original_route(self):
        route = {"agent": "DATA", "prefix": "conferir planilha"}
        case = {"request": "Conferir planilha de teste"}
        before = self.store.read(self.note)
        preview = self.call("test", route=route, **case)["trial"]
        self.assertEqual(preview["agent"], "DATA")
        self.assertEqual(self.store.read(self.note), before)
        self.assertNotIn("rota_aplicada", self.call("save", route=route))
        self.call("apply", confirmed=True)
        self.assertEqual(self.call("test", applied=True, **case)["trial"], preview)
        with patch("core.lab.fixture_planner", return_value={"routing": {"subtasks": [{"agent": "FILE"}]}}):
            original = self.call("test", applied=True, request="Abra a pasta de teste")["trial"]
        self.assertFalse(original["matched"])
        self.assertEqual(original["original"], ["FILE"])

    def test_invalid_agent_and_unconfirmed_apply_leave_note_intact(self):
        before = self.store.read(self.note)
        with self.assertRaises(ValueError):
            self.call("save", route={"agent": "MAESTRO", "prefix": "rodar código"})
        with self.assertRaises(ValueError):
            self.call("apply")
        with self.assertRaises(FileNotFoundError):
            draft_route(self.store, {"note": "../conferencia.md", "action": "load"})
        self.assertEqual(self.store.read(self.note), before)
