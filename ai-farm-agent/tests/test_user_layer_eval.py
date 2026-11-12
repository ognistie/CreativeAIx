"""Regressao: o que o usuario escreve (Harness, Voce) chega ao prompt do Maestro, de cada agente
e da resposta final; sem camada pessoal, nada aparece. Ver scripts/eval_user_layer.py."""
import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "eval_user_layer", Path(__file__).resolve().parents[1] / "scripts" / "eval_user_layer.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
run = _mod.run


class UserLayerReachesPrompts(unittest.TestCase):
    def test_every_role_receives_only_its_own_user_layer(self):
        failed = [r["case"] for r in run() if not r["ok"]]
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
