"""Suporte da interface: cor da barra de titulo, paletas, perfil dos agentes e introducoes."""
import tempfile
import unittest
from pathlib import Path

from core.harness import AGENT_INFO, AGENTS, PALETTES, validate
from desktop.titlebar import _colorref


class TitleBarColor(unittest.TestCase):
    def test_hex_becomes_bgr_colorref(self):
        self.assertEqual(_colorref("#FBF7F4", 0), 0xF4F7FB)
        self.assertEqual(_colorref("#ff112233", 0), 0x332211)      # #AARRGGBB do Qt: alfa ignorado
        self.assertEqual(_colorref("azul", 7), 7)


class Palettes(unittest.TestCase):
    def test_every_palette_in_the_screen_is_accepted(self):
        qml = (Path(__file__).resolve().parents[1] / "desktop/qml/components/Theme.qml").read_text(encoding="utf-8")
        for name in PALETTES:
            self.assertIn(f'"{name}":', qml)
            self.assertEqual(validate({"appearance": {"palette": name}})["appearance"]["palette"], name)
        self.assertEqual(validate({"appearance": {"palette": "neon"}})["appearance"]["palette"], "abismo")


class AgentProfiles(unittest.TestCase):
    def test_every_agent_has_a_card_without_overpromising(self):
        self.assertEqual(set(AGENT_INFO), set(AGENTS))
        for a, info in AGENT_INFO.items():
            self.assertTrue(info["role"] and info["does"] and info["uses"] and info["quick"], a)
            # "O que faz" nunca promete confirmacao; os limites que falam dela so aparecem com a trava em enforce
            self.assertNotIn("confirmação", " ".join(info["does"]).lower(), a)
            self.assertTrue(info["inputs"] and info["limits"] and info["examples"], a)

    def test_card_only_promises_confirmation_when_enforce_is_on(self):
        import json
        from unittest.mock import patch
        from PySide6.QtCore import QObject
        from desktop.bridge import Bridge
        b = Bridge.__new__(Bridge)
        QObject.__init__(b)
        with patch("core.action_risk.mode", lambda: "observe"):
            card = json.loads(b.agentProfile("WEB"))
        self.assertTrue(card["ok"])
        self.assertFalse(any("confirma" in l.lower() for l in card["limits"]))
        self.assertIn("open_url", card["tools"])
        with patch("core.action_risk.mode", lambda: "enforce"):
            card = json.loads(b.agentProfile("WEB"))
        self.assertTrue(any("confirma" in l.lower() for l in card["limits"]))


class IntroState(unittest.TestCase):
    def test_intro_flag_is_kept_in_the_personal_folder(self):
        from types import SimpleNamespace
        from desktop.bridge import Bridge
        with tempfile.TemporaryDirectory() as tmp:
            fake = SimpleNamespace(store=SimpleNamespace(personal=Path(tmp)))
            b = Bridge.__new__(Bridge)
            b._brain = lambda: fake
            Bridge.setIntroSeen(b, "brain", True)
            Bridge.setIntroSeen(b, "../../fora", True)                 # chave desconhecida: ignorada
            self.assertEqual(Bridge.introSeen(b), '{"brain": true}')


if __name__ == "__main__":
    unittest.main()
