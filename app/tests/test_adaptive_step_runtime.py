"""Cenários sintéticos do runtime e da seleção de contexto."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.step_runtime import StepRuntime, verified_success


class AdaptiveSteps(unittest.TestCase):
    def setUp(self):
        self.clock = patch("core.step_runtime.monotonic", return_value=0)
        self.now = self.enterContext(self.clock)
        self.pause = self.enterContext(patch("core.step_runtime.sleep"))
        self.cancel = Mock(return_value=False)
        self.runtime = StepRuntime(2, 1, self.cancel)

    def test_baseline_retries_uncertain_failure_candidate_stops(self):
        from desktop.controller import should_retry
        result = {"success": False, "status": "failed", "result": "❌ sem confirmação"}
        self.assertTrue(should_retry("vision_click", result))
        handler = Mock(return_value=result)
        self.assertEqual(self.runtime.run(handler, retry=True), result)
        handler.assert_called_once()

    def test_recovers_pre_effect_failure_and_observes_action_limit(self):
        handler = Mock(side_effect=[
            {"success": False, "status": "failed", "effect_started": False},
            {"success": True, "verified": True},
        ])
        self.assertTrue(verified_success([self.runtime.run(handler, retry=True)]))
        self.assertEqual((self.runtime.actions, self.runtime.retries, self.runtime.recovered), (2, 1, 1))
        self.assertEqual(self.runtime.run(handler)["status"], "action_limit")

    def test_cancel_between_attempts_and_deadline_before_dispatch(self):
        handler = Mock(return_value={"success": False, "status": "failed", "effect_started": False})
        self.pause.side_effect = lambda *_: setattr(self.cancel, "return_value", True)
        self.runtime.run(handler, retry=True)
        handler.assert_called_once()
        self.cancel.return_value = False
        self.now.return_value = 1
        self.assertEqual(self.runtime.run(handler)["status"], "timeout")
        handler.assert_called_once()

    def test_history_prioritizes_relevant_older_pair_within_budget(self):
        from agents.chat_agent import history_messages
        turns = [SimpleNamespace(said="Orçamento fiscal", reply="sintético")]
        turns.extend(SimpleNamespace(said=f"outro assunto {i}", reply="x") for i in range(14))
        self.assertFalse(any("fiscal" in m["content"] for m in history_messages(turns)))
        result = history_messages(turns, request="Revisar orçamento fiscal", byte_budget=280)
        self.assertTrue(any("fiscal" in m["content"] for m in result))
        self.assertEqual([m["role"] for m in result], ["user", "assistant"] * (len(result) // 2))
        self.assertLessEqual(sum(len(m["content"].encode()) + 16 for m in result), 280)

    def test_no_absolute_limit_still_honors_cancel_and_action_limit(self):
        runtime = StepRuntime(1, None, self.cancel)
        self.now.return_value = 3600
        self.assertTrue(runtime.run(lambda: {"success": True})["success"])
        self.assertEqual(runtime.stop_reason(), "action_limit")
        self.cancel.return_value = True
        self.assertEqual(runtime.stop_reason(), "cancelled")

    def test_learning_ignores_successful_wait_only_when_an_outcome_was_verified(self):
        wait = {"action": "wait", "success": True, "verified": False}
        result = {"action": "copy_file", "success": True, "verified": True}
        self.assertFalse(verified_success([wait]))
        self.assertTrue(verified_success([wait, result]))
        self.assertFalse(verified_success([wait, {**result, "verified": False}]))
        self.assertFalse(verified_success([{**wait, "success": False}, result]))

    def test_click_adapters_only_recover_from_known_pre_dispatch_failure(self):
        from core.automation import AutomationEngine

        engine = AutomationEngine.__new__(AutomationEngine)
        engine.dry_run = False
        engine.vision = Mock()
        engine.il = Mock()
        for action, params, adapter in (
            ("uia", {"app_name": "Paint", "element": "Abrir"}, engine.il.click_element),
            ("browser", {"description": "Abrir"}, Mock()),
        ):
            with self.subTest(action=action), patch("core.browser_uia.click", adapter), \
                    patch.object(engine, "_vision_click") as fallback:
                adapter.side_effect = [
                    {"success": False, "ok": False, "error": "não localizado", "effect_started": False},
                    {"success": True, "ok": True},
                    {"success": False, "ok": False, "error": "resultado incerto", "effect_started": True},
                ]
                handler = getattr(engine, f"_{action}_click")
                def execute():
                    result = handler(params)
                    return result if isinstance(result, dict) else {"success": True}

                runtime = StepRuntime(5, None, self.cancel)
                self.assertTrue(runtime.run(execute, retry=True)["success"])
                self.assertEqual(runtime.recovered, 1)
                uncertain = runtime.run(execute, retry=True)
                self.assertEqual(uncertain["status"], "uncertain")
                self.assertEqual(adapter.call_count, 3)
                fallback.assert_not_called()

    def test_task_window_resolution_refuses_unrelated_foreground(self):
        from core.automation import AutomationEngine

        engine = AutomationEngine.__new__(AutomationEngine)
        engine.authorized_task = "seleciona o círculo no Paint"
        with patch("core.observer._foreground", return_value=(7, "Projeto - Paint")):
            self.assertEqual(engine._vision_request_window(), 7)
        with patch("core.observer._foreground", return_value=(13, "Site - Edge")):
            self.assertIsNone(engine._vision_request_window())

    def test_browser_link_dispatch_and_independent_destination_check(self):
        from core import browser_uia as browser

        initial = "https://test.invalid/start"
        target = "https://test.invalid/result"
        window = Mock(handle=7)
        element = Mock()
        link = browser.Link("Abrir resultado", target, (0, 0, 10, 10), elem=element)
        for observed, changed, verified in ((target, True, True), (initial, True, False), ("", False, False)):
            with self.subTest(observed=observed), patch.object(browser, "browser_window", return_value=window), \
                    patch.object(browser, "current_url", side_effect=[initial, *([observed] if changed else [])]), \
                    patch.object(browser, "page_title", return_value="Fixture"), \
                    patch.object(browser, "_signature", return_value=("Fixture", initial)), \
                    patch.object(browser, "links", return_value=([], ())), \
                    patch.object(browser, "pick", return_value=link), \
                    patch.object(browser, "wait_change", return_value=changed), \
                    patch("core.automation._is_front", return_value=True):
                element.reset_mock()
                outcome = browser.click("Abrir resultado", authorize=lambda *_: "")
                self.assertEqual(outcome["destination_verified"], verified)
                self.assertTrue(outcome["effect_started"])
                element.invoke.assert_called_once()
                element.click_input.assert_not_called()

    def test_pilot_keeps_text_result_when_vision_cannot_find_target(self):
        from core.automation import AutomationEngine

        engine = AutomationEngine.__new__(AutomationEngine)
        engine.dry_run = False
        engine.vision = Mock()
        engine.vision.find_element.return_value = {"found": False}
        with patch.object(engine, "_ensure_app_focus", return_value=True), patch("core.automation.time.sleep"):
            self.assertIsInstance(engine._vision_click({"description": "fixture"}), str)
            outcome = engine._vision_click({"description": "fixture"}, structured=True)
        self.assertIs(outcome["effect_started"], False)
        self.assertFalse(outcome["success"])

    def test_provider_transport_can_be_injected_without_sdk_creation(self):
        from core.ai_client import AIClient

        transport = Mock()
        with patch("core.ai_client.Anthropic") as sdk:
            client = AIClient(transport=transport)
        sdk.assert_not_called()
        self.assertIs(client._client, transport)
