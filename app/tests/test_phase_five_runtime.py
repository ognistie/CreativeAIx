"""Protocolo offline definido em docs/architecture/phase-v-protocol.md."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.action_policy import authorize
from core.run_context import RunContext


URL = "https://fixture.invalid/maintenance"
ARTICLE = "janela de manutenção às oito"


def file_case(root, layout, *, candidate, max_actions=100, on_patch=lambda _patch: None,
              cancelled=lambda: False, check=lambda _params: True):
    from core.automation_files import FileActions
    actions = FileActions()
    root.mkdir()
    for file in layout:
        path = root / file
        path.parent.mkdir(exist_ok=True)
        path.write_text("estado verde", encoding="utf-8")
    goal = f"Leia status.txt em {root}"
    run = RunContext(goal, cancelled, max_actions=max_actions)
    opened = []

    def dispatch(params):
        denied = authorize("FILE", goal, "read_file", params, file_scope=[root])
        if denied:
            return {"success": False, "status": "rejected", "result": denied}
        opened.append(Path(params["path"]))
        return actions._read_file(params)

    result = run.execute_step("FILE", "read_file", {"path": str(root / "status.txt")}, dispatch,
                              adaptive=candidate, phase_iv=not candidate,
                              authorize_patch=lambda args: check(args) and not authorize(
                                  "FILE", goal, "read_file", args, file_scope=[root]),
                              allow_directory=lambda path: not authorize(
                                  "FILE", goal, "list_files", {"path": path}, file_scope=[root]),
                              on_patch=on_patch)
    return result, opened, run


def web_case(*, candidate, changed=False, blocked=False, injected=None):
    from core.automation import AutomationEngine
    from core import browser_uia

    engine = AutomationEngine.__new__(AutomationEngine)
    engine.dry_run = False
    engine.current_agent, engine.authorized_task = "WEB", f"Leia o anúncio em {URL}"
    engine.executed_steps, engine.workspace = [], {}
    win = SimpleNamespace(handle=12)
    document = Mock()
    document.iface_text.DocumentRange.GetText.return_value = ""
    document.rectangle.return_value = SimpleNamespace(left=0, top=0, right=1024, bottom=768)
    page = [URL]
    run = RunContext(f"Leia o anúncio em {URL}", lambda: False)
    snapshots = Mock(wraps=browser_uia.snapshot)

    def applied(_patch):
        if changed:
            page[0] = "https://fixture.invalid/other"

    with patch.object(browser_uia, "browser_window", return_value=win), \
            patch.object(browser_uia, "current_url", side_effect=lambda _: page[0]), \
            patch.object(browser_uia, "page_title", return_value="Aviso"), \
            patch.object(browser_uia, "_document", return_value=document), \
            patch.object(browser_uia, "_find_visible", return_value=[
                ("Text", ARTICLE, "", (150, 120, 650, 145), None)]), \
            patch.object(browser_uia, "_scroll_left", return_value=False), \
            patch.object(browser_uia, "links", return_value=([], None)), \
            patch.object(browser_uia, "blocked_reason", return_value="Desafio" if blocked else ""), \
            patch.object(browser_uia, "snapshot", snapshots), patch("core.action_logger.log_action"):
        result = run.execute_step("WEB", "browser_read", injected or {},
                                  lambda args: engine.execute("browser_read", args),
                                  adaptive=candidate, phase_iv=not candidate,
                                  authorize_patch=lambda args: not authorize("WEB", run.goal, "browser_read", args),
                                  allow_directory=lambda _: False, on_patch=applied)
    return result, snapshots.call_count, run


def compare():
    """Avalia os mesmos objetivos nos dois braços. O grader usa as saídas e o rastro da fixture."""
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        cases = ("file_nested", "web_empty", "file_direct", "file_ambiguous", "web_changed", "web_blocked")
        for index, case in enumerate(cases):
            for candidate in ([False, True] if index % 2 == 0 else [True, False]):
                root = Path(folder) / f"{case}-{candidate}"
                if case.startswith("file"):
                    layout = {"file_nested": ["a/status.txt"], "file_direct": ["status.txt"],
                              "file_ambiguous": ["a/status.txt", "b/status.txt"]}[case]
                    out, opened, run = file_case(root, layout, candidate=candidate)
                    actual = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in root.rglob("*.txt")}
                    safe = actual == dict.fromkeys(layout, "estado verde") and all(root in p.parents for p in opened)
                    passed = safe and (opened == [root / "status.txt"] if case == "file_ambiguous"
                                       else out["result"] == "estado verde")
                else:
                    out, visible, run = web_case(candidate=candidate, changed=case == "web_changed",
                                                 blocked=case == "web_blocked")
                    safe = visible == 0 if case != "web_empty" else visible <= 1
                    passed = safe and (ARTICLE in out["result"] and URL in out["result"] if case == "web_empty"
                                       else ARTICLE not in out["result"])
                rows.append({"case": case, "strategy": "candidate" if candidate else "phase_iv",
                             "pass": passed, "safe": safe, "actions": run.runtime.actions,
                             "replans": run.runtime.replans, "outcome": out["outcome"]})
    return rows


class PhaseFiveRuntime(unittest.TestCase):
    def test_nested_admission_does_not_double_spend_action_budget(self):
        from core.step_runtime import StepRuntime
        runtime = StepRuntime(1, None, lambda: False)
        secondary = Mock()
        first = runtime.run(lambda: runtime.run(secondary))
        self.assertEqual(first["status"], "rejected")
        self.assertEqual(runtime.actions, 1)
        secondary.assert_not_called()

    def test_headless_cli_uses_the_same_alternative_for_a_read_only_goal(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from app.scripts import read_objective
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "subfolder").mkdir()
            (root / "subfolder/status.txt").write_text("estado verde", encoding="utf-8")
            output = StringIO()
            with patch("sys.argv", ["read_objective.py", "--root", folder, "status.txt"]), redirect_stdout(output):
                self.assertEqual(read_objective.main(), 0)
            self.assertEqual(output.getvalue().strip(), "estado verde")

    def test_frozen_paired_protocol(self):
        rows = compare()
        self.assertTrue(all(row["safe"] for row in rows))
        self.assertEqual(sum(row["pass"] for row in rows if row["strategy"] == "phase_iv"), 4)
        self.assertEqual(sum(row["pass"] for row in rows if row["strategy"] == "candidate"), 6)
        recovered = [row["case"] for row in rows if row["strategy"] == "candidate" and row["outcome"] == "verified"
                     and row["replans"]]
        self.assertCountEqual(recovered, ["file_nested", "web_empty"])

    def test_permissions_cancellation_budget_and_identity_prevent_file_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            stopped = Mock(return_value=False)
            scenarios = (
                {"check": lambda _: False}, {"max_actions": 2},
                {"cancelled": stopped, "on_patch": lambda _: setattr(stopped, "return_value", True)},
                {"on_patch": lambda _: (parent / "p3/a/status.txt").write_text("substituído", encoding="utf-8")},
            )
            for i, opts in enumerate(scenarios):
                root = parent / f"p{i}"
                out, opened, _ = file_case(root, ["a/status.txt"], candidate=True, **opts)
                self.assertFalse(out["success"])
                self.assertEqual(opened, [root / "status.txt"])

    def test_plan_cannot_supply_browser_window_or_scope(self):
        result, visible, _ = web_case(candidate=True, injected={
            "_expected_url": "https://fixture.invalid/other", "_read_view": "visible", "_read_window": 999,
        })
        self.assertTrue(result["verified"])
        self.assertIn(URL, result["result"])
        self.assertEqual(visible, 1)

    def test_file_data_composition_preserves_file_and_verifies_workbook(self):
        from core.artifact_builder import build_workbook
        from core.automation_files import FileActions
        from core.task_schedule import Availability
        from openpyxl import load_workbook

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "recebidos").mkdir()
            (root / "recebidos/status.txt").write_text("verde", encoding="utf-8")
            goal = f"Copie status.txt em {root} e registre seu estado na planilha"
            run = RunContext(goal, lambda: False, file_roots=(str(root),))
            schedule = run.make_schedule([{}, {"depends_on": 1}], set())
            output = root / "copia.txt"
            permit = lambda args: not authorize("FILE", goal, "copy_file", args, file_scope=[root])
            copied = run.execute_step("FILE", "copy_file", {"source": str(root / "status.txt"), "destination": str(output)},
                                      FileActions()._copy_file, authorize_patch=permit, allow_directory=lambda _: True)
            schedule.finish(schedule.nodes[0], copied["verified"])
            self.assertIs(schedule.availability(schedule.nodes[1]), Availability.READY)
            manifest = {"name": "estado", "sheets": [{"title": "Estado", "rows": [
                ["Situação"], [output.read_text(encoding="utf-8")]]}]}
            chart = run.execute_step("DATA", "create_workbook", {"manifest": manifest},
                                     lambda args: build_workbook(args["manifest"], root),
                                     authorize_patch=lambda _: False, allow_directory=lambda _: False)
            self.assertEqual(chart["outcome"], "verified")
            workbook = load_workbook(chart["artifacts"]["files"][0], read_only=True)
            try:
                self.assertEqual(workbook["Estado"]["A2"].value, "verde")
            finally:
                workbook.close()
            self.assertEqual(output.read_text(encoding="utf-8"), "verde")
            self.assertEqual(run.runtime.replans, 1)

    def test_graph_rejects_invalid_edges_and_offline_blocks_uncontrolled_apps(self):
        from core.task_schedule import TaskSchedule
        for edge in (False, 0, 2, 8, "1"):
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                TaskSchedule([{}, {"depends_on": edge}], set())
        with patch("core.egress.offline", return_value=True):
            for agent, operation in (("WEB", "open_url"), ("WEB", "browser_click"), ("WEB", "web_read"),
                                     ("DESKTOP", "hotkey"), ("FILE", "open_path"), ("EXTCODE", "ext_code_task")):
                self.assertIn("offline", authorize(agent, "fixture", operation, {}))
            self.assertEqual(authorize("WEB", "fixture", "browser_read", {}), "")
        with patch("core.action_policy.request_roots", side_effect=AssertionError("acesso antes da política")):
            self.assertIn("rede", authorize("FILE", "fixture", "read_file", {"path": r"\\server\file.txt"}))

    def test_corruption_preserves_uncertainty_and_reads_reject_traversal(self):
        from core.task_ledger import TaskLedger
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ledger = TaskLedger(root / "tasks")
            source, destination = root / "source.txt", root / "destination.txt"
            source.write_text("fixture", encoding="utf-8")
            destination.write_text("fixture", encoding="utf-8")
            ledger.begin("t", "copiar")
            ledger.step_started("t", 1, "FILE", "copy_file", {})
            ledger.copy_intent("t", 1, str(source), str(destination))
            ledger.finish("t", "interrupted")
            with (ledger.root / "t.jsonl").open("a", encoding="utf-8") as stream:
                stream.write('{"type":"step_finished"')
            self.assertFalse(ledger.reconcile_copy("t", 1, str(destination)))
            self.assertEqual(ledger.load("t")["steps_uncertain"][0]["action"], "copy_file")
            self.assertEqual(ledger.events("../destination"), [])
