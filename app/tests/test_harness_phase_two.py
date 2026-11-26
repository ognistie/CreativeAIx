"""Verificações locais do cursor, das dependências e da saída de dados."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.egress import EgressDenied
from core.task_ledger import TaskLedger
from core.task_schedule import Availability, TaskSchedule


class PhaseTwo(unittest.TestCase):
    def test_dependency_failure_and_skip_leave_independent_work_ready(self):
        graph = [{}, {"depends_on": 1}, {"depends_on": 2}, {}]
        for skip in (set(), {1}):
            schedule = TaskSchedule(graph, skip)
            first, second, third, independent = schedule.nodes
            if not skip:
                self.assertIs(schedule.availability(first), Availability.READY)
                schedule.finish(first, False)
            expected = Availability.SKIPPED if skip else Availability.BLOCKED
            self.assertIs(schedule.availability(second), expected)
            self.assertIs(schedule.availability(third), expected)
            self.assertIs(schedule.availability(independent), Availability.READY)

    def test_checkpoint_replay_preserves_unknown_action(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = TaskLedger(Path(root))
            ledger.begin("fixture", "tarefa sintética")
            ledger.checkpoint("fixture", 2, 1, "ready")
            ledger.step_started("fixture", 3, "DESKTOP", "app_task", {})
            self.assertEqual(len(ledger.recover()), 1)
            state = ledger.load("fixture")
            self.assertEqual(state["checkpoint"]["subtask"], 2)
            self.assertEqual(state["state"], "interrupted")
            self.assertEqual([s["step"] for s in state["steps_uncertain"]], [3])
            self.assertEqual(ledger.recover(), [])

    def test_offline_blocks_llm_stream_and_live_voice_before_transport(self):
        from core.ai_client import AIClient
        from core.voice.live import _connect

        model = AIClient.__new__(AIClient)
        model._client = Mock()
        with patch("core.egress.offline", return_value=True), patch("websocket.create_connection") as connect:
            with self.assertRaises(EgressDenied):
                model.message_with_meta("modelo", "", "fixture")
            with self.assertRaises(EgressDenied):
                model.converse("modelo", "", [])
            with self.assertRaises(EgressDenied):
                _connect("fixture", 1)
        self.assertEqual(model._client.mock_calls, [])
        connect.assert_not_called()
