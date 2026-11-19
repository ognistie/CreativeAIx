"""Regressões encontradas na preparação da versão para testes internos."""
import json
import tempfile
import unittest
from pathlib import Path

from core.session import Session
from core import user_settings


class ValidationHardening(unittest.TestCase):
    def test_invalid_settings_cannot_silently_enable_microphone(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            user_settings.save({"live_conversation": False}, path)
            for value in ("false", 1, None, []):
                with self.assertRaises(ValueError):
                    user_settings.save({"live_conversation": value}, path)
                self.assertFalse(user_settings.load(path)["live_conversation"])

    def test_damaged_history_does_not_break_conversation_list(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for sid, value in {"broken": [], "legacy": {"turns": [], "title": {}, "updated_at": "ontem"},
                               "valid": {"id": "valid", "turns": [], "updated_at": 3},
                               "mismatch": {"id": "other", "turns": []}}.items():
                (base / f"{sid}.json").write_text(json.dumps(value), encoding="utf-8")
            rows = Session.list_saved(base=base)
            self.assertEqual({row["id"] for row in rows}, {"legacy", "valid"})
            self.assertEqual(rows[0]["title"], "Conversa")
            self.assertIsNone(Session.read_saved("broken", base))
            self.assertIsNone(Session.read_saved("mismatch", base))
            (base / "valid.json").write_text(json.dumps({"id": "valid", "turns": [42]}), encoding="utf-8")
            self.assertIsNone(Session.read_saved("valid", base))
