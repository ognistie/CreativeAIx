"""Integração offline de replanejamento restrito e retomada depois de queda."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.lab_budget import Budget, RequestLimit, current
from core.objective_replanner import choose_read_strategy
from core.run_context import RunContext
from core.task_ledger import TaskLedger


class ModelRecovery(unittest.TestCase):
    def run_goal(self, answer, *, budgeted=True):
        from core.automation import AutomationEngine
        from core import browser_uia
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.dry_run = False
        bound = "https://fixture.invalid/original"
        budget = Budget(1, 10, 1, 1024, lambda: False) if budgeted else None
        client = Mock()

        def inference(*args, **kwargs):
            self.assertIs(current.get(), budget)
            return answer

        client.message.side_effect = inference
        run = RunContext(f'Confira "total confirmado" em {bound}', lambda: False, budget=budget,
                         read_replanner=lambda reason, options: choose_read_strategy(client, "mock", reason, options))
        snapshots = []

        def read(**kwargs):
            snapshots.append(kwargs)
            return {"ok": True, "title": "Fixture", "url": bound, "window": 42, "links": [],
                    "text": "O total confirmado é 17." if kwargs["max_chars"] == 12000 else "Cabeçalho."}

        with patch.object(browser_uia, "read", side_effect=read):
            def dispatch(args):
                out = engine._browser_read(args)
                return out if isinstance(out, dict) else {"success": True, "result": out}
            result = run.execute_step("WEB", "browser_read", {}, dispatch,
                                      authorize_patch=lambda _: True, allow_directory=lambda _: False)
        return result, client, snapshots

    def test_mock_model_recovers_literal_in_same_window(self):
        result, client, snapshots = self.run_goal('{"strategy":"expanded"}')
        self.assertEqual(result["outcome"], "verified")
        self.assertIn("total confirmado", result["result"])
        self.assertEqual(snapshots[1]["expected_window"], 42)
        self.assertEqual(snapshots[0]["expected_url"], snapshots[1]["expected_url"])
        client.message.assert_called_once()
        self.assertNotIn("fixture.invalid", client.message.call_args.args[2])
        self.assertNotIn("total confirmado", client.message.call_args.args[2])

    def test_injected_parameters_and_missing_budget_do_not_admit_replan(self):
        for answer in ('{"strategy":"expanded","url":"https://outside.invalid"}',
                       '{"strategy":"open_url"}', '["expanded"]', '{bad'):
            out, _, reads = self.run_goal(answer)
            self.assertFalse(out["success"])
            self.assertEqual(len(reads), 1)
        out, client, reads = self.run_goal('{"strategy":"expanded"}', budgeted=False)
        self.assertFalse(out["success"])
        self.assertEqual(out["failure_reason"], "web_marker_missing")
        client.message.assert_not_called()
        self.assertEqual(len(reads), 1)


class DurableReadRecovery(unittest.TestCase):
    def test_crash_between_reads_and_resume_never_dispatches_completed_step(self):
        from app.scripts import read_objective
        from core.automation_files import FileActions
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("first.txt", "second.txt"):
                (root / name).write_text(name, encoding="utf-8")
            ledger = TaskLedger(root / "journal")
            args = ["read_objective.py", "--root", folder, "--task-id", "r1", "first.txt", "second.txt"]
            child = """
import os, sys
from app.scripts import read_objective as cli
from core.task_ledger import TaskLedger
journal = sys.argv.pop(1)
cli.get_ledger = lambda: TaskLedger(journal)
start = cli.read_started
cli.read_started = lambda ledger, task, index: os._exit(73) if index == 2 else start(ledger, task, index)
raise SystemExit(cli.main())
"""
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
            result = subprocess.run([sys.executable, "-c", child, str(ledger.root), *args[1:]],
                                    env=env, capture_output=True, check=False, timeout=20)
            self.assertEqual(result.returncode, 73, result.stderr.decode(errors="replace"))
            self.assertEqual(ledger.load("r1")["steps_done"][0]["step"], 1)
            self.assertEqual(ledger.load("r1")["steps_uncertain"], [])
            reader = FileActions()._read_file
            capture = StringIO()
            with patch.object(read_objective, "get_ledger", return_value=ledger), \
                    patch.object(FileActions, "_read_file", wraps=reader) as dispatch, redirect_stdout(capture):
                with patch("sys.argv", [*args, "--resume"]):
                    self.assertEqual(read_objective.main(), 0)
                    self.assertEqual(read_objective.main(), 1)
                dispatch.assert_called_once_with({"path": str(root / "second.txt")})
            self.assertEqual(capture.getvalue().splitlines()[0], "second.txt")
            self.assertEqual(ledger.load("r1")["state"], "completed")

    def test_uncertain_read_and_swapped_inputs_are_not_resumed(self):
        from core.read_checkpoint import open_read_checkpoint, read_started
        from core.task_ledger import LedgerUnavailable
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ledger = TaskLedger(root / "journal")
            names = ["a.txt", "b.txt"]
            with open_read_checkpoint(ledger, "new", root, names, lambda _: True, resume=False):
                read_started(ledger, "new", 1)
            for ordered in (names, list(reversed(names))):
                with self.assertRaises(LedgerUnavailable), open_read_checkpoint(
                        ledger, "new", root, ordered, lambda _: True, resume=True):
                    self.fail("retomada de etapa incerta")

    def test_shared_budget_reserves_only_one_call_across_threads(self):
        from concurrent.futures import ThreadPoolExecutor
        budget = Budget(1, 20, 1, 2048, lambda: False)
        sdk = Mock()
        sdk.messages.count_tokens.return_value = SimpleNamespace(input_tokens=10)
        params = {"model": "claude-sonnet-5", "messages": [], "max_tokens": 100}

        def attempt():
            try:
                budget.start(sdk, params)
                return True
            except RequestLimit:
                return False

        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(pool.map(lambda _: attempt(), range(2)), [True, False])
        sdk.messages.count_tokens.assert_called_once()

    def test_exhausted_model_budget_stops_subsequent_tool_dispatch(self):
        budget = Budget(1, 20, 1, 2048, lambda: False)
        budget.stop = "limite confirmado"
        run = RunContext("ler", lambda: False, budget=budget)
        tool = Mock()
        result = run.execute_step("FILE", "read_file", {}, tool, authorize_patch=lambda _: True,
                                  allow_directory=lambda _: True)
        self.assertEqual(result["outcome"], "budget_limit")
        tool.assert_not_called()
