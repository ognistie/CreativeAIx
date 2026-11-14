"""App oficial: interface React (ui/dist) em janelas Qt (desktop/web_host.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))


class WebHost(unittest.TestCase):
    def test_only_files_inside_dist_are_served(self):
        from desktop.web_host import resolve_ui_file
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_text("ok", encoding="utf-8")
            (dist / "assets" / "a.js").write_text("x", encoding="utf-8")
            (Path(tmp) / "segredo.txt").write_text("nao", encoding="utf-8")
            self.assertEqual(resolve_ui_file(dist, ""), (dist / "index.html").resolve())
            self.assertEqual(resolve_ui_file(dist, "assets/a.js"), (dist / "assets" / "a.js").resolve())
            for bad in ("../segredo.txt", "assets/../../segredo.txt", "nada.js", "assets"):
                self.assertIsNone(resolve_ui_file(dist, bad), bad)

    def test_host_methods_are_typed_for_the_dispatcher(self):
        from desktop.server import HOST_METHODS, RPC_METHODS, Dispatcher
        from desktop.web_host import WebBridge
        d = Dispatcher(WebBridge.__new__(WebBridge), RPC_METHODS | HOST_METHODS)
        self.assertEqual(d._types["pickFiles"], [])
        self.assertEqual(d._types["openExternal"], [str])
        self.assertEqual(sorted(HOST_METHODS - set(d._types)), [])

    def test_external_links_are_https_only(self):
        from desktop.web_host import WebBridge
        b = WebBridge.__new__(WebBridge)
        for url in ("http://exemplo.com", "file:///C:/Windows", "javascript:alert(1)", "ms-settings:"):
            self.assertFalse(b.openExternal(url), url)

    def test_built_ui_is_in_the_repository(self):
        from desktop.web_host import UI_DIST, ui_available
        self.assertTrue(ui_available(), f"interface nao gerada em {UI_DIST}: cd ui; npm run build")


if __name__ == "__main__":
    unittest.main()
