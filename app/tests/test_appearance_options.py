"""Aparencia: fundos gerativos (dithering, halftone) e paletas novas passam pela validacao do Harness;
qualquer outro valor continua recusado (volta ao padrao)."""

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path

from core import harness


class AppearanceOptions(unittest.TestCase):
    def test_concurrent_sections_are_preserved_and_versions_remain_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = harness.Harness(Path(directory))
            settings.save({})
            updates = [{"agents": {"FILE": {"instructions": "Confirme o destino."}}},
                       {"appearance": {"palette": "oceano"}},
                       {"response": {"extra": "Responda de forma direta."}}]
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(settings.patch, updates))
            saved = settings.load()
            self.assertEqual(saved["agents"]["FILE"]["instructions"], "Confirme o destino.")
            self.assertEqual(saved["appearance"]["palette"], "oceano")
            self.assertEqual(saved["response"]["extra"], "Responda de forma direta.")
            for version in settings.versions():
                path = settings.folder / "harness_versoes" / (version["id"] + ".json")
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)
            self.assertEqual(list(settings.folder.glob("*.tmp")), [])

    def test_generative_wallpapers_are_accepted(self):
        for wp in ("gen:dither", "gen:halftone", "gen:halftone:aquario", "gen:dither:rio"):
            self.assertEqual(harness.validate({"appearance": {"wallpaper": wp}})["appearance"]["wallpaper"], wp)

    def test_legacy_wallpaper_keeps_scene_and_discards_ascii_options(self):
        for previous, current in [("gen:ascii", "gen:dither"), ("gen:ascii:praia", "gen:dither:praia")]:
            look = harness.validate({"appearance": {"wallpaper": previous, "art": {"ascii": "braille", "quality": "eco"}}})["appearance"]
            self.assertEqual(look["wallpaper"], current)
            self.assertEqual(look["art"], {"dither": "auto", "quality": "eco", "motion": "auto"})

    def test_unknown_wallpapers_are_refused(self):
        for wp in ("gen:matrix", "gen:", "gen:ascii;rm", "gen:ascii:marte", "gen:ascii:rio:x", "http://x/y.png",
                   "C:\\x.png", "personal:../x"):
            self.assertEqual(harness.validate({"appearance": {"wallpaper": wp}})["appearance"]["wallpaper"], "", wp)

    def test_new_palettes_exist_in_the_theme_and_validate(self):
        theme = json.loads((Path(harness.__file__).resolve().parents[1] / "design" / "theme.json").read_text(encoding="utf-8"))
        for name in harness.PALETTES:
            self.assertIn(name, theme["palettes"]["dark"], name)
            self.assertIn(name, theme["palettes"]["light"], name)
            self.assertEqual(harness.validate({"appearance": {"palette": name}})["appearance"]["palette"], name)
        self.assertGreaterEqual(len(harness.PALETTES), 20)

    def test_ui_lists_match_the_core(self):
        ui = (Path(harness.__file__).resolve().parents[2] / "ui" / "src" / "views" / "AppearancePanel.tsx").read_text(encoding="utf-8")
        for name in harness.PALETTES:
            self.assertIn(f'["{name}", ', ui, name)
        scenes = (Path(harness.__file__).resolve().parents[2] / "ui" / "src" / "lib" / "scenes.ts").read_text(encoding="utf-8")
        for scene in harness.GEN_SCENES:                      # a lista do nucleo e a mesma da interface
            self.assertIn(f'{{ id: "{scene}", label:', scenes, scene)
        self.assertEqual(scenes.count('{ id: "'), len(harness.GEN_SCENES))

    def test_wallpaper_art_options_validate_and_match_the_ui(self):
        ok = {"dither": "atkinson", "quality": "eco", "motion": "parado"}
        self.assertEqual(harness.validate({"appearance": {"art": ok}})["appearance"]["art"], ok)
        bad = harness.validate({"appearance": {"art": {"dither": "x", "quality": 3, "extra": "y"}}})["appearance"]["art"]
        self.assertEqual(bad, {k: "auto" for k in harness.GEN_ART})
        self.assertEqual(harness.validate({})["appearance"]["art"], {k: "auto" for k in harness.GEN_ART})
        art = (Path(harness.__file__).resolve().parents[2] / "ui" / "src" / "lib" / "wallpaper" / "art.ts").read_text(encoding="utf-8")
        for key, values in harness.GEN_ART.items():
            for value in values:
                self.assertIn(f'"{value}"', art, f"{key}={value}")


if __name__ == "__main__":
    unittest.main()
