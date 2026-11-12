"""Fluxos reais da interface (scripts/ui_flows.py) num processo separado: papel de parede persiste ao
trocar de tela e o mapa do Cerebro abre no primeiro clique. Cerebro temporario, sem rede."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


class UiFlowTests(unittest.TestCase):
    def test_flows(self):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        out = subprocess.run([sys.executable, str(APP / "scripts" / "ui_flows.py")], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=240, cwd=str(APP), env=env)
        flows = [line for line in out.stdout.splitlines() if line.startswith("FLOW ")]
        self.assertEqual(len(flows), 14, out.stdout + out.stderr[-2000:])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr[-2000:])
        self.assertTrue(all(" ok " in f for f in flows), flows)


if __name__ == "__main__":
    unittest.main()
