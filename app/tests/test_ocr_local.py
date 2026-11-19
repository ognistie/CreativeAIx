import unittest
from unittest.mock import patch

from core.ocr_local import find_text_on_screen


class WindowsOcrMatching(unittest.TestCase):
    def test_match_uses_word_bounds_and_adds_window_origin(self):
        lines = [{"text": "Salvar como agora", "words": [
            {"text": "Salvar", "bbox": [10, 20, 52, 42]},
            {"text": "como", "bbox": [60, 20, 90, 42]},
            {"text": "agora", "bbox": [100, 20, 150, 42]},
        ]}]
        with patch("core.ocr_local.read_screen_text", return_value=lines):
            self.assertEqual(find_text_on_screen("Salvar como", (100, 200, 300, 400))["center"], (150, 231))
            self.assertFalse(find_text_on_screen("alvar como")["found"])

    def test_duplicate_label_cannot_propose_coordinates(self):
        line = {"text": "Enviar", "words": [{"text": "Enviar", "bbox": [10, 20, 60, 40]}]}
        with patch("core.ocr_local.read_screen_text", return_value=[line, line]):
            self.assertEqual(find_text_on_screen("Enviar"), {"found": False})
