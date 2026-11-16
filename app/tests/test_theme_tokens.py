"""Tema escuro/claro (E2): contraste AA medido nos tokens e esquema do Harness para tema e desfoque."""
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))


class ThemeTokenTests(unittest.TestCase):
    def test_every_text_token_meets_aa_on_every_palette_and_theme(self):
        import check_contrast
        tokens, palettes = check_contrast.parse(check_contrast.THEME.read_text(encoding="utf-8"))
        self.assertEqual(set(palettes["palettes"]), set(palettes["darkPalettes"]))
        rows = check_contrast.measure(tokens, palettes)
        self.assertGreater(len(rows), 200)
        failed = [r for r in rows if r[4] < r[5]]
        self.assertEqual(failed, [], failed[:10])
        # O medidor discrimina: um texto cinza medio reprova
        tokens["dark"]["textPrimary"] = (0.5, 0.5, 0.5, 1.0)
        self.assertTrue([r for r in check_contrast.measure(tokens, palettes) if r[4] < r[5]])

    def test_harness_schema_accepts_mode_and_blur_only_when_valid(self):
        from core.harness import validate, DEFAULT
        self.assertEqual(DEFAULT["appearance"]["mode"], "escuro")
        out = validate({"appearance": {"mode": "claro", "blur": False}})
        self.assertEqual((out["appearance"]["mode"], out["appearance"]["blur"]), ("claro", False))
        out = validate({"appearance": {"mode": "neon", "blur": "sim"}})
        self.assertEqual((out["appearance"]["mode"], out["appearance"]["blur"]), ("escuro", True))

    def test_title_bar_dark_detection(self):
        from desktop.titlebar import is_dark
        self.assertTrue(is_dark("#120F17"))
        self.assertFalse(is_dark("#FBF7F4"))
        self.assertFalse(is_dark("xyz"))

    def test_generated_css_matches_the_token_source(self):
        """ui/src/styles/tokens.css e icons.gen.ts saem de app/design: nunca editados a mao."""
        import export_theme_tokens as ex
        self.assertEqual(ex.OUT_CSS.read_text(encoding="utf-8"), ex.render_css())
        self.assertEqual(ex.OUT_ICONS.read_text(encoding="utf-8"), ex.render_icons())

if __name__ == "__main__":
    unittest.main()
