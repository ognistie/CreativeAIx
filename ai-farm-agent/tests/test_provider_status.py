"""Configuracoes > Provedores: a tela diz se a chave esta configurada, nunca o valor (nem um pedaco)."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ProviderStatusNeverShowsTheKey(unittest.TestCase):
    def test_only_booleans_leave_the_bridge(self):
        from PySide6.QtCore import QObject
        from desktop.bridge import Bridge
        b = Bridge.__new__(Bridge)
        QObject.__init__(b)
        fake = "sk-ant-fake-0123456789abcdefghijklmnop"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": fake, "OPENAI_API_KEY": ""}):
            out = b.providerStatus()
        self.assertNotIn(fake, out)
        self.assertNotIn(fake[:12], out)
        rows = {p["name"]: p for p in json.loads(out)["providers"]}
        self.assertTrue(rows["Anthropic"]["configured"])
        self.assertFalse(rows["OpenAI"]["configured"])
        self.assertIn(".env", rows["OpenAI"]["next"])            # a proxima acao fica junto do diagnostico

    def test_status_is_readable_in_the_sandbox(self):
        from desktop.qml_sandbox import READ_SLOTS
        self.assertIn("providerStatus", READ_SLOTS)


if __name__ == "__main__":
    unittest.main()
