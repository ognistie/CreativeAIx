"""Empacotamento da interface Tauri: o comando do Nuitka e o instalador apontam para os mesmos lugares.

Nao compila nada (leva dezenas de minutos e roda no workflow de release): confere o que o build monta.
"""
import json
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP / "scripts"))

import build_core  # noqa: E402


class BuildCoreCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = build_core.command()

    def test_only_the_headless_core_goes_in(self):
        for qt in ("PySide6", "desktop.main", "desktop.bridge", "desktop.window_mode"):
            self.assertIn(f"--nofollow-import-to={qt}", self.cmd)
        for needed in ("desktop.server", "desktop.bridge_core", "mcp_server"):
            self.assertIn(f"--include-module={needed}", self.cmd)
        self.assertEqual(self.cmd[-1], str(APP / "main.py"))

    def test_config_and_runtime_data_keep_their_relative_paths(self):
        self.assertIn(f"--include-data-files={ROOT / 'config.yaml'}=config.yaml", self.cmd)
        for rel in ("state_maps", "memory"):
            self.assertIn(f"--include-data-dir={APP / rel}={rel}", self.cmd)

    def test_exe_name_matches_the_shell(self):
        self.assertIn(f"--output-filename={build_core.EXE}", self.cmd)
        sidecar = (ROOT / "desktop-tauri" / "src-tauri" / "src" / "sidecar.rs").read_text(encoding="utf-8")
        self.assertIn(f'const PACKAGED_CORE: &str = "{build_core.EXE}";', sidecar)

    def test_installer_resources_are_the_build_output(self):
        conf = json.loads((ROOT / "desktop-tauri" / "src-tauri" / "tauri.release.conf.json").read_text(encoding="utf-8"))
        res = conf["bundle"]["resources"]
        src_tauri = ROOT / "desktop-tauri" / "src-tauri"
        targets = {(src_tauri / k).resolve(): v for k, v in res.items()}
        self.assertEqual(targets[(build_core.OUT / "core").resolve()], "core/")
        self.assertEqual(targets[(build_core.OUT / "AI-Farm-agents").resolve()], "AI-Farm-agents/")
        # Instalador por usuario: o nucleo grava historico e logs na propria pasta
        self.assertEqual(conf["bundle"]["targets"], ["nsis"])
        self.assertEqual(conf["bundle"]["windows"]["nsis"]["installMode"], "currentUser")

    def test_vault_path_still_resolves_from_the_core_folder(self):
        cfg = (ROOT / "config.yaml").read_text(encoding="utf-8")
        brain = (APP / "core" / "brain.py").read_text(encoding="utf-8")
        self.assertIn('"../AI-Farm-agents"', brain + cfg)


if __name__ == "__main__":
    unittest.main()
