"""Bateria de cenários dos agentes (scripts/bench_agents_offline.py) como regressão: sem API e sem desktop.
Trava o que já sai sem IA, o agente certo para cada pedido e o ganho do auto-aperfeiçoamento."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class AgentScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bench_agents_offline as bench
        with redirect_stdout(io.StringIO()):
            cls.report = bench.run(json_out=False)

    def category(self, name):
        return self.report["por_categoria"][name]

    def test_deterministic_categories_never_call_the_model(self):
        for name in ("abrir", "sistema", "conversa", "tela", "ambiguo", "codigo"):
            c = self.category(name)
            self.assertEqual(c["sem_ia"], c["total"], name)
            self.assertEqual(c["agente_ok"], c["total"], name)

    def test_explicit_site_searches_skip_the_maestro(self):
        self.assertGreaterEqual(self.category("pesquisa")["sem_ia"], 2)

    def test_no_real_errors_in_any_category(self):
        broken = {name: c["erros"] for name, c in self.report["por_categoria"].items()
                  if name in ("abrir", "sistema", "conversa", "tela", "ambiguo", "codigo") and c["erros"]}
        self.assertEqual(broken, {})
        self.assertFalse([d for d in self.report["divergencias"] if d["categoria"] in
                          ("abrir", "sistema", "conversa", "tela", "ambiguo", "codigo")])

    def test_self_improvement_stops_calling_the_model(self):
        learning = self.report["aprendizado"]
        self.assertTrue(all(x["chamou_modelo"] for x in learning[:3]))
        self.assertFalse(any(x["chamou_modelo"] for x in learning[3:]))
        self.assertEqual(learning[-1]["status"], "promoted")


if __name__ == "__main__":
    unittest.main()
