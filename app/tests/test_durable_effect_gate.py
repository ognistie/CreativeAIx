"""Efeitos sintéticos: o handler só roda depois de intenção e decisão duráveis."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.task_ledger import TaskLedger, LedgerUnavailable


class DurableEffects(unittest.TestCase):
    def setUp(self):
        from core.automation import AutomationEngine
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.ledger = TaskLedger(Path(temporary.name))
        self.engine = AutomationEngine.__new__(AutomationEngine)
        self.engine.effect_scope = "synthetic-run"
        self.engine.effect_session = "synthetic-session"
        self.engine.authorized_task = "enviar mensagem sintética"
        self.engine.current_agent = "DESKTOP"
        self.engine.confirm_effect = Mock(return_value=True)
        self.engine.should_stop = Mock(return_value=False)
        for target, kwargs in (
            ("core.task_ledger.get_ledger", {"return_value": self.ledger}),
            ("core.action_risk._record", {}),
            ("core.action_risk.mode", {"return_value": "enforce"}),
        ):
            p = patch(target, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    def authorize(self):
        return self.engine._authorize_ui("enviar", "click", "conteúdo privado sintético")

    def test_intent_is_durable_before_asking_and_decision_before_release(self):
        def confirm(question):
            self.assertEqual([e["phase"] for e in self.ledger.events("synthetic-run")], ["intent"])
            return True
        self.engine.confirm_effect.side_effect = confirm
        self.assertEqual(self.authorize(), "")
        rows = self.ledger.events("synthetic-run")
        self.assertEqual([e["phase"] for e in rows], ["intent", "approved"])
        self.assertEqual(rows[0]["action_id"], rows[1]["action_id"])
        self.assertEqual(rows[1]["session_id"], "synthetic-session")
        self.assertNotIn("conteúdo privado", str(rows))

    def test_failed_intent_does_not_even_request_approval(self):
        with patch("core.task_ledger.os.fsync", side_effect=OSError("fixture")):
            self.assertIn("bloqueado", self.authorize())
        self.engine.confirm_effect.assert_not_called()
        self.assertEqual(self.engine.effects_done_in("synthetic-run"), [])

    def test_failed_decision_does_not_release_effect(self):
        with patch("core.task_ledger.os.fsync", side_effect=[None, OSError("fixture")]):
            self.assertIn("bloqueado", self.authorize())
        self.assertEqual(self.engine.effects_done_in("synthetic-run"), [])

    def test_disabled_task_telemetry_keeps_effect_decisions(self):
        self.ledger.enabled = False
        self.ledger.begin("synthetic-run", "conteúdo da tarefa")
        self.assertEqual(self.authorize(), "")
        self.assertEqual([row["phase"] for row in self.ledger.events("synthetic-run")], ["intent", "approved"])

    def test_missing_journal_scope_blocks(self):
        self.engine.effect_scope = ""
        self.assertIn("bloqueado", self.authorize())

    def test_cancel_during_approval_never_releases_effect(self):
        self.engine.confirm_effect.side_effect = lambda q: setattr(self.engine, "should_stop", lambda: True) or True
        self.assertIn("não autorizada", self.authorize())
        self.assertEqual(self.ledger.events("synthetic-run")[-1]["phase"], "declined")

    def test_repeated_effect_gets_a_fresh_intent_and_approval(self):
        self.assertEqual(self.authorize(), "")
        self.assertEqual(self.authorize(), "")
        rows = self.ledger.events("synthetic-run")
        self.assertEqual(len(rows), 4)
        self.assertNotEqual(rows[0]["action_id"], rows[2]["action_id"])
        self.assertEqual(self.engine.confirm_effect.call_count, 2)

    def test_changed_target_or_payload_invalidates_confirmation(self):
        for field, replacement in (("window", 2), ("body", "changed")):
            with self.subTest(field=field):
                resource = {"window": 1, "body": "fixture"}
                self.engine.confirm_effect.side_effect = (
                    lambda q: resource.update({field: replacement}) or True
                )
                reason = self.engine._authorize_ui("enviar", "click", "Enviar", target=lambda: resource)
                self.assertIn("não autorizada", reason)
                self.assertEqual(self.ledger.events("synthetic-run")[-1]["phase"], "declined")

    def test_whatsapp_unread_counter_preserves_window_binding(self):
        from core.automation import _effect_window
        with patch("core.automation._fg_state", side_effect=[(7, "(1) WhatsApp"), (7, "(2) WhatsApp")]):
            self.assertEqual(self.engine._authorize_ui("enviar", "click", "Enviar", target=_effect_window), "")
        with patch("core.automation._fg_state", side_effect=[(7, "(2) WhatsApp"), (8, "(2) WhatsApp")]):
            self.assertIn("não autorizada", self.engine._authorize_ui("enviar", "click", "Enviar", target=_effect_window))

    def test_expired_approval_never_releases_effect(self):
        with patch("core.automation.time.monotonic", side_effect=[0, 181]):
            self.assertIn("não autorizada", self.authorize())
        self.assertEqual(self.ledger.events("synthetic-run")[-1]["phase"], "declined")

    def test_delete_confirmation_does_not_survive_file_replacement(self):
        target = self.ledger.root / "documento.txt"
        target.write_text("original", encoding="utf-8")

        def replace(_question):
            target.write_text("outro documento", encoding="utf-8")
            return True

        self.engine.confirm_effect.side_effect = replace
        with patch("core.action_policy.authorize", return_value=""), \
                patch.object(type(self.engine), "_delete_file") as delete:
            result = self.engine.execute("delete_file", {"path": str(target)})
        self.assertEqual(result["status"], "needs_confirmation")
        delete.assert_not_called()

    def test_written_uncertain_outcome_is_not_a_confirmed_failure(self):
        self.ledger.begin("synthetic-run", "fixture")
        self.ledger.step_started("synthetic-run", 1, "WEB", "browser_click", {})
        self.ledger.step_finished("synthetic-run", 1, "browser_click", {"status": "uncertain"})
        state = self.ledger.load("synthetic-run")
        self.assertEqual(state["steps_failed"], [])
        self.assertEqual(state["steps_uncertain"][0]["status"], "uncertain")

    def test_non_sensitive_read_does_not_require_journal(self):
        self.ledger.enabled = False
        self.assertEqual(self.engine._authorize_ui(None, "read_file"), "")
        self.engine.confirm_effect.assert_not_called()

    def test_shadow_and_off_cannot_bypass_durability(self):
        self.ledger.enabled = False
        for mode in ("shadow", "off"):
            with self.subTest(mode=mode), patch("core.action_risk.mode", return_value=mode):
                with patch("core.task_ledger.os.fsync", side_effect=OSError("fixture")):
                    self.assertIn("bloqueado", self.authorize())

    def test_unsafe_journal_id_cannot_escape_root(self):
        with self.assertRaises(LedgerUnavailable):
            self.ledger.effect("../escape", "id", "intent", agent="WEB", action="click", kind="enviar")

    def test_unavailable_journal_factory_blocks(self):
        with patch("core.task_ledger.get_ledger", side_effect=RuntimeError("fixture")):
            self.assertIn("bloqueado", self.authorize())
        self.engine.confirm_effect.assert_not_called()

    def test_approval_event_never_becomes_verified_execution_on_replay(self):
        self.ledger.begin("synthetic-run", "fixture")
        self.ledger.step_started("synthetic-run", 1, "DESKTOP", "app_task", {})
        self.assertEqual(self.authorize(), "")
        state = self.ledger.load("synthetic-run")
        self.assertEqual(state["steps_done"], [])
        self.assertEqual(len(state["steps_uncertain"]), 1)
        self.assertIsNone(state["verified"])

    def test_executor_handler_is_not_called_on_journal_failure_or_dry_run(self):
        self.engine.executed_steps, self.engine.workspace = [], {}
        handler = Mock(return_value="feito")
        with patch("core.action_policy.authorize", return_value=""), patch.object(type(self.engine), "_delete_file", handler), \
                patch("core.task_ledger.os.fsync", side_effect=OSError("fixture")):
            result = self.engine.execute("delete_file", {"path": "synthetic.txt"})
            self.assertFalse(result["success"])
            simulated = self.engine.execute("delete_file", {"path": "synthetic.txt"}, dry_run=True)
            self.assertEqual(simulated["status"], "simulated")
        handler.assert_not_called()

    def test_agent_cannot_supply_internal_effect_marker(self):
        self.engine.executed_steps, self.engine.workspace = [], {}
        handler = Mock(return_value="feito")
        with patch("core.action_policy.authorize", return_value=""), \
                patch("core.automation._fg_state", return_value=(1, "fixture")), \
                patch.object(type(self.engine), "_click", handler), patch("core.action_logger.log_action"):
            result = self.engine.execute("click", {"x": 10, "y": 20, "_effect_checked": "enviar"})
        self.assertTrue(result["success"])
        handler.assert_called_once_with({"x": 10, "y": 20})
