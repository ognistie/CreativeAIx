"""Corpus offline de recuperação FILE. O Lab confere o estado final no disco."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.lab import Lab
from core.run_context import RunContext


def compare(lab):
    goal = "Copie relatorio.txt para saida.txt em {ws}"
    cases = [
        {"id": "nested", "task": goal, "setup": {"recebidos/relatorio.txt": "alfa"},
         "expect": {"contains": {"saida.txt": "alfa"}}},
        {"id": "direct", "task": goal, "setup": {"relatorio.txt": "beta"},
         "expect": {"contains": {"saida.txt": "beta"}}},
        {"id": "ambiguous", "task": goal, "setup": {"a/relatorio.txt": "x", "b/relatorio.txt": "y"},
         "expect": {"absent": ["saida.txt"]}},
        {"id": "occupied", "task": goal, "setup": {"relatorio.txt": "novo", "saida.txt": "antigo"},
         "expect": {"contains": {"saida.txt": "antigo"}}},
        {"id": "outside", "task": goal, "setup": {"relatorio.txt": "x"},
         "expect": {"blocked_or_inside": True, "absent": ["saida.txt"]}},
        {"id": "reserved", "task": goal, "split": "holdout", "setup": {"nova/relatorio.txt": "reserva"},
         "expect": {"contains": {"saida.txt": "reserva"}}},
    ]
    dataset = lab.save_eval_set("runtime-copy", cases, expected="new")
    baseline = lab.versions("FILE")[0]["id"]
    candidate = lab.create_variant("FILE", baseline, "Identificador para o braço adaptativo.")["id"]
    case_id = workspace = outside = None

    def plan(_version, _task):
        destination = (outside if case_id == "outside" else workspace) / "saida.txt"
        return {"steps": [{"action": "copy_file", "params": {
            "source": str(workspace / "relatorio.txt"), "destination": str(destination),
        }}]}

    def prepare(identifier, _dataset, ws, external):
        nonlocal case_id, workspace, outside
        case_id, workspace, outside = identifier, ws, external

    plan.prepare_case = prepare
    return lab.run(dataset["name"], [baseline, candidate], plan, "simulado", repeats=3,
                   split="development", runtime_strategies={baseline: "fixed", candidate: "adaptive"})


class PhaseFourRuntime(unittest.TestCase):
    def test_paired_ablation_verifies_recovery_and_no_out_of_scope_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            run = compare(Lab(Path(folder)))
        comparison = run["comparison"]
        self.assertEqual(comparison["pairs"], 15)
        self.assertEqual([row["case"] for row in comparison["improvements"]], ["nested"] * 3)
        self.assertEqual(comparison["regressions"], [])
        self.assertNotIn("reserved", {row["case"] for row in run["results"]})
        base, adaptive = run["versions"]
        self.assertEqual((run["summary"][base]["passed"], run["summary"][adaptive]["passed"]), (12, 15))
        self.assertEqual(sum(row["metrics"]["recovered"] for row in run["results"]), 3)
        for row in run["results"]:
            self.assertEqual(row["metrics"]["cost_usd"], 0)
            self.assertTrue(all(check["ok"] for check in row.get("checks", []))
                            or row["case"] == "nested" and row["version"] == base)

    def test_replan_rejects_uncertainty_denial_and_budget_exhaustion(self):
        replan = Mock()
        run = RunContext("copiar relatorio.txt", lambda: False, max_actions=3)
        for status in ("uncertain", "rejected", "needs_confirmation"):
            run.runtime.run(lambda: {"success": False, "status": status, "effect_started": False}, replan=replan)
        run.runtime.run(lambda: self.fail("despacho depois do teto"), replan=replan)
        replan.assert_not_called()

    def test_original_goal_and_directory_permission_are_required_to_observe(self):
        from core.file_recovery import alternative_copy
        with tempfile.TemporaryDirectory() as folder:
            params = {"source": str(Path(folder) / "relatorio.txt"), "destination": str(Path(folder) / "saida.txt")}
            outcome = {"failure_reason": "copy_source_missing"}
            with patch("core.file_recovery.os.scandir") as scan:
                self.assertIsNone(alternative_copy("copiar outro.txt", params, outcome, lambda: False, lambda _: True))
                self.assertIsNone(alternative_copy("copiar a/relatorio.txt", params, outcome, lambda: False, lambda _: True))
                self.assertIsNone(alternative_copy("copiar relatorio.txt", params, outcome, lambda: False, lambda _: False))
                scan.assert_not_called()

    def test_cancellation_during_observation_prevents_alternative_dispatch(self):
        cancelled = Mock(return_value=False)
        backup = Mock()
        run = RunContext("copiar relatorio.txt", cancelled)

        def observe(_result):
            cancelled.return_value = True
            return backup

        run.runtime.run(lambda: {"success": False, "status": "failed", "effect_started": False}, replan=observe)
        backup.assert_not_called()
        self.assertEqual(run.runtime.actions, 2)
