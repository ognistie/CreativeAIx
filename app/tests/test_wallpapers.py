"""Catalogo de papeis de parede (E4): credito obrigatorio, paleta deterministica com AA garantido,
importacao validada na camada pessoal (nunca no repositorio)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from core import wallpapers


def _image(size=(800, 500), colors=((250, 250, 240), (30, 60, 120), (200, 80, 40))):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, colors[0])
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, size[0] // 2, size[1]), fill=colors[1])
    d.ellipse((size[0] // 2, 0, size[0], size[1] // 2), fill=colors[2])
    return img


class CatalogTests(unittest.TestCase):
    def test_every_bundled_image_has_full_credit_and_license(self):
        self.assertEqual(wallpapers.uncredited(), [])
        items = wallpapers.catalog()
        self.assertTrue(items)
        for item in items:
            for field in ("title", "author", "year", "license", "source"):
                self.assertTrue(item[field], (item["id"], field))
            self.assertTrue(Path(item["path"]).is_file())
            self.assertLess(Path(item["path"]).stat().st_size, 5_000_000, "catalogo enxuto")
        self.assertTrue(any("mínio público" in i["license"] or "omínio público" in i["license"] for i in items))

    def test_image_without_credit_is_left_out(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        _image().save(tmp / "sem-ficha.webp", "WEBP")
        (tmp / "CREDITS.md").write_text("## sem-ficha\n- title: X\n- author: Y\n", encoding="utf-8")
        self.assertEqual(wallpapers.catalog(tmp), [])
        self.assertEqual(wallpapers.uncredited(tmp), ["sem-ficha.webp"])
        (tmp / "CREDITS.md").write_text("## sem-ficha\n- title: X\n- author: Y\n- year: 1800\n- source: S\n- license: CC0\n", encoding="utf-8")
        self.assertEqual(len(wallpapers.catalog(tmp)), 1)


class PaletteTests(unittest.TestCase):
    def test_palette_is_deterministic_and_meets_contrast(self):
        a, b = wallpapers.palette_of(_image()), wallpapers.palette_of(_image())
        self.assertEqual(a, b)
        self.assertEqual(len(a["tones"]), 3)
        glass = (18, 18, 26)
        self.assertGreaterEqual(wallpapers.contrast(wallpapers._over(glass, 1, glass), tuple(int(a["accent"][i:i + 2], 16) for i in (1, 3, 5))), 3.0)
        bright = tuple(int(a["bright"][i:i + 2], 16) for i in (1, 3, 5))
        face = wallpapers._over(glass, 0.66 + a["glass_boost"], bright)
        self.assertGreaterEqual(wallpapers.contrast((244, 244, 247), face), 4.5)
        # Em qualquer foto (branca, escura) o texto claro le sobre o vidro reforcado na parte mais clara
        for colors in (((255, 255, 255), (250, 250, 250), (245, 245, 245)), ((10, 10, 12), (20, 25, 30), (30, 20, 20))):
            pal = wallpapers.palette_of(_image(colors=colors))
            bright = tuple(int(pal["bright"][i:i + 2], 16) for i in (1, 3, 5))
            self.assertGreaterEqual(wallpapers.contrast((244, 244, 247), wallpapers._over(glass, 0.66 + pal["glass_boost"], bright)), 4.5)
        self.assertEqual(wallpapers.palette_of(_image(colors=((10, 10, 12), (20, 25, 30), (30, 20, 20))))["glass_boost"], 0)
        # O reforco e necessario de verdade quando o vidro e mais transparente: o mesmo calculo a 0.30 reprova
        self.assertLess(wallpapers.contrast((244, 244, 247), wallpapers._over(glass, 0.30, (255, 255, 255))), 4.5)
        # Texto solto sobre a foto: o escurecimento minimo garante AA para o texto secundario (escuro) e o veu
        # minimo garante AA para o texto escuro (claro), ate numa imagem toda branca ou toda preta
        for colors in (((255, 255, 255),) * 3, ((5, 5, 5),) * 3, ((250, 250, 240), (30, 60, 120), (200, 80, 40))):
            pal = wallpapers.palette_of(_image(colors=colors))
            self.assertGreaterEqual(wallpapers.contrast((198, 198, 207), wallpapers._over((0, 0, 0), pal["min_dim"], colors[0])), 4.5 - 1e-6)
            self.assertGreaterEqual(wallpapers.contrast((29, 29, 31), wallpapers._over((255, 255, 255), pal["min_veil"], colors[0])), 4.5 - 1e-6)
        for item in wallpapers.catalog():
            pal = wallpapers.palette_for(item)
            self.assertIn("min_dim", pal)
            self.assertEqual(pal, wallpapers.palette_of(__import__("PIL.Image", fromlist=["Image"]).open(item["path"])))


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wp-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.personal = self.tmp / "pessoal"

    def test_valid_image_lands_in_personal_layer_resized(self):
        src = self.tmp / "Minha foto.png"
        _image(size=(4000, 2500)).save(src, "PNG")
        item = wallpapers.import_image(src, self.personal)
        self.assertTrue(item["id"].startswith("personal:"))
        self.assertTrue(Path(item["path"]).is_file() and Path(item["thumb"]).is_file())
        self.assertIn(str(self.personal), item["path"])          # so na camada pessoal
        self.assertNotIn(str(wallpapers.CATALOG), item["path"])  # nunca no catalogo empacotado (git)
        from PIL import Image
        with Image.open(item["path"]) as img:
            self.assertEqual(img.width, 2880)          # versao de tela: 1920 x 1.5 (escala do Windows)
        self.assertEqual(wallpapers.personal(self.personal)[0]["id"], item["id"])
        found = wallpapers.resolve(item["id"], self.personal)
        self.assertEqual(found["palette"], item["palette"])
        self.assertTrue(wallpapers.remove_personal(item["id"].split(":")[1], self.personal))
        self.assertEqual(wallpapers.personal(self.personal), [])

    def test_invalid_too_large_and_wrong_format_are_refused(self):
        bad = self.tmp / "nota.png"
        bad.write_text("isto nao e imagem", encoding="utf-8")
        with self.assertRaises(ValueError):
            wallpapers.import_image(bad, self.personal)
        big = self.tmp / "grande.png"
        with big.open("wb") as f:
            f.truncate(wallpapers.MAX_IMPORT_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "grande"):
            wallpapers.import_image(big, self.personal)
        gif = self.tmp / "anim.gif"
        _image(size=(400, 300)).save(gif, "GIF")
        with self.assertRaisesRegex(ValueError, "formato"):
            wallpapers.import_image(gif, self.personal)
        with self.assertRaises(PermissionError):
            wallpapers.import_image(gif, None)
        self.assertFalse(self.personal.exists(), "nada e gravado antes de validar")
        self.assertIsNone(wallpapers.resolve("catalog:../x", self.personal))
        self.assertIsNone(wallpapers.resolve("personal:nao-existe", self.personal))


class UpscaleTests(unittest.TestCase):
    def test_tiles_are_stitched_without_seams(self):
        """Modelo falso (vizinho mais proximo 4x): a costura dos blocos precisa reproduzir exatamente a ampliacao."""
        import numpy as np
        from unittest.mock import patch
        from PIL import Image
        from core import ai_upscale

        class FakeSession:
            def get_inputs(self):
                return [type("I", (), {"name": "image"})()]
            def run(self, _out, feed):
                x = feed["image"]
                return [x.repeat(4, axis=2).repeat(4, axis=3)]
        rng = np.random.default_rng(3)
        src = Image.fromarray(rng.integers(0, 255, (203, 341, 3), dtype=np.uint8))
        with patch.object(ai_upscale, "_get_session", return_value=FakeSession()):
            out = ai_upscale.upscale4(src)
        self.assertEqual(out.size, (341 * 4, 203 * 4))
        expected = np.asarray(src).repeat(4, axis=0).repeat(4, axis=1).astype(int)
        self.assertLessEqual(int(np.abs(np.asarray(out).astype(int) - expected).max()), 1)

    def test_large_source_is_only_reduced(self):
        from PIL import Image
        from core.painterly import finish, TARGET_WIDTH
        out, method = finish(_image(size=(3600, 2000)), ai=True)
        self.assertEqual((out.width, method), (TARGET_WIDTH, "original"))
        out, method = finish(_image(size=(600, 400)), ai=False)
        self.assertEqual((out.width, method), (TARGET_WIDTH, "pictorico"))


if __name__ == "__main__":
    unittest.main()
