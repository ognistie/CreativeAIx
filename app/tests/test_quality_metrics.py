"""Métricas contínuas (core/quality_metrics.py): números certos a partir dos registros, sem texto dos pedidos."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.quality_metrics import STALL, compute, snapshot


def run(ok=True, seconds=2.0, cost=0.01, **extra):
    return {"started_at": "2026-11-25T10:00:00", "success": ok, "duration_ms": int(seconds * 1000),
            "metrics": {"cost_usd": cost}, **extra}


class QualityMetrics(unittest.TestCase):
    def test_rates_per_hundred_and_latency(self):
        history = [run(), run(), run(ok=False, error=STALL, status="cancelled", seconds=90),
                   run(ok=False, status="cancelled", error="cancelado pelo usuario", seconds=4),
                   run(ok=False, effects_done=["enviar"], seconds=60),
                   {"error": "clarification_required"}]                      # pergunta não conta como pedido
        authz = [{"at": "2026-11-25T10:00:05", "requested": False, "decision": "blocked"},
                 {"at": "2026-11-25T10:00:06", "requested": True, "decision": "approved_once"},
                 {"at": "2026-11-20T10:00:00", "requested": False, "decision": "allowed"}]  # antes da janela
        m = compute(history, authz)
        self.assertEqual(m["pedidos"], 5)
        self.assertEqual(m["taxa_sucesso"], 0.4)
        self.assertEqual(m["travas_por_100"], 20.0)
        self.assertEqual(m["cancelados_por_100"], 20.0)
        self.assertEqual(m["acoes_nao_pedidas_por_100"], 20.0)
        self.assertEqual(m["acoes_nao_pedidas_executadas"], 0)
        self.assertEqual(m["efeito_antes_de_falhar_por_100"], 20.0)
        self.assertEqual(m["custo_por_pedido_usd"], 0.01)
        self.assertEqual(m["latencia_p50_s"], 4.0)
        self.assertGreater(m["latencia_p95_s"], 60)

    def test_empty_and_unreadable_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "h.jsonl"
            bad.write_text("nao e json\n" + json.dumps(run()) + "\n", encoding="utf-8")
            m = snapshot(history_path=bad, authz_path=Path(tmp) / "faltando.jsonl")
        self.assertEqual(m["pedidos"], 1)
        self.assertIsNone(compute([], [])["taxa_sucesso"])

    def test_output_never_carries_request_text(self):
        m = compute([run(task="manda a senha pro joão")], [])
        self.assertNotIn("joão", json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
