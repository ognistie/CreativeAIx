"""Verificação independente (Phase VI.2): segunda conferência do estado final, fora do handler que executou.

Arquivos temporários; nada de desktop. Um executor que declara sucesso falso perde o "verificado" e o falso sucesso
é contado. Ações sem verificador ficam como estavam (não inventa verificação).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.verification import apply_independent_check, independent_check


class IndependentVerification(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def ok(self, **extra):
        return {"success": True, "verified": True, **extra}

    def test_folder_move_copy_and_write(self):
        folder = self.dir / "relatorios"
        self.assertFalse(independent_check("create_folder", {"path": str(folder)}, self.ok())["ok"])
        folder.mkdir()
        self.assertTrue(independent_check("create_folder", {"path": str(folder)}, self.ok())["ok"])

        src, dst = self.dir / "a.txt", self.dir / "b.txt"
        src.write_text("igual", encoding="utf-8")
        dst.write_text("diferente", encoding="utf-8")
        self.assertFalse(independent_check("copy_file", {"source": str(src), "destination": str(dst)}, self.ok())["ok"])
        dst.write_text("igual", encoding="utf-8")
        check = independent_check("copy_file", {"source": str(src), "destination": str(dst)}, self.ok())
        self.assertEqual((check["ok"], check["method"]), (True, "sha256_equal"))

        moved = self.dir / "c.txt"
        self.assertFalse(independent_check("move_file", {"source": str(src), "destination": str(moved)}, self.ok())["ok"])
        src.rename(moved)
        self.assertTrue(independent_check("move_file", {"source": str(src), "destination": str(moved)}, self.ok())["ok"])

        target = self.dir / "nota.txt"
        target.write_text("outro texto", encoding="utf-8")
        self.assertFalse(independent_check("write_file", {"path": str(target), "content": "pedido"}, self.ok())["ok"])

    def test_workbook_is_reopened(self):
        from openpyxl import Workbook
        path = self.dir / "gastos.xlsx"
        wb = Workbook()
        wb.active.title = "Resumo"
        wb.save(path)
        result = self.ok(artifacts={"files": [str(path)]})
        good = independent_check("create_workbook", {"manifest": {"sheets": [{"title": "Resumo"}]}}, result)
        bad = independent_check("create_workbook", {"manifest": {"sheets": [{"title": "Gastos"}]}}, result)
        self.assertTrue(good["ok"])
        self.assertFalse(bad["ok"])
        self.assertFalse(independent_check("create_workbook", {}, self.ok())["ok"])

    def test_false_success_loses_verified_and_unknown_actions_pass_through(self):
        folder = self.dir / "nunca-criada"
        out = apply_independent_check("create_folder", {"path": str(folder)}, self.ok())
        self.assertFalse(out["verified"])
        self.assertTrue(out["false_success"])
        self.assertEqual(out["independent_check"]["version"], "independent-v2")
        untouched = self.ok(result="cliquei")
        self.assertIs(apply_independent_check("vision_click", {}, untouched), untouched)
        unverified = {"success": True, "verified": False}
        self.assertIs(apply_independent_check("create_folder", {"path": str(folder)}, unverified), unverified)

    def test_learning_never_sees_a_false_success(self):
        from core.step_runtime import verified_success
        out = apply_independent_check("create_folder", {"path": str(self.dir / "x")}, self.ok())
        self.assertFalse(verified_success([out]))

    def test_workbook_correct_tabs_with_wrong_cells_cannot_teach(self):
        from openpyxl import Workbook
        from core.step_runtime import verified_success
        path = self.dir / "conteudo.xlsx"
        wb = Workbook()
        wb.active.title = "Resumo"
        wb.active["A1"] = 99
        wb.save(path)
        wb.close()
        out = apply_independent_check("create_workbook", {"manifest": {"sheets": [
            {"title": "Resumo", "rows": [[17]]}]}}, self.ok(artifacts={"files": [str(path)]}))
        self.assertTrue(out["false_success"])
        self.assertFalse(verified_success([out]))

    def test_metrics_count_false_successes(self):
        from core.quality_metrics import compute
        m = compute([{"success": True, "duration_ms": 10, "runtime": {"false_successes": 2}}], [])
        self.assertEqual(m["falsos_sucessos"], 2)


if __name__ == "__main__":
    unittest.main()
