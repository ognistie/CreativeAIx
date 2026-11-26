"""Correcoes da auditoria interna de 2026-11-17, cada uma com o caso real."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def _engine():
    from core.automation import AutomationEngine
    engine = AutomationEngine.__new__(AutomationEngine)
    engine.dry_run, engine.current_agent, engine.authorized_task = False, "DESKTOP", "abra o whatsapp e escreva oi"
    engine.executed_steps, engine.workspace, engine._fg_before, engine._expect = [], {}, None, None
    engine.should_stop = None
    return engine


class RawClickUsesTheRealElement(unittest.TestCase):
    """S1: `click(x, y)` pegava o efeito so da descricao escrita pelo modelo ("Ponto inicial")."""

    def run_click(self, names, windows=((10, "Fixture"), (10, "Fixture"))):
        from core import automation
        engine = _engine()
        asked = []
        engine._authorize_ui = lambda kind, action, label="", **kwargs: (asked.append((kind, action, label))
                                                               or (f"Antes de {kind} preciso da sua confirmação."
                                                                   if kind else ""))
        clicked = Mock()
        with patch.object(automation, "names_at_point", return_value=names), \
                patch.object(automation, "_effect_window", side_effect=windows), \
                patch.object(automation, "_uia_point_state", return_value=((11,), "Fixture", 50000, "")), \
                patch.object(automation.pyautogui, "size", return_value=(1920, 1080)), \
                patch.object(automation.pyautogui, "click", clicked), patch.object(automation, "human_move"), \
                patch("core.action_policy.authorize", return_value=""):
            result = engine.execute("click", {"x": 1800, "y": 1000, "description": "Ponto inicial"})
        return result, asked, clicked

    def test_click_over_send_button_asks_before_clicking(self):
        result, asked, clicked = self.run_click(["", "Enviar"])
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertIn(("enviar", "click", "Enviar"), asked)
        clicked.assert_not_called()

    def test_click_over_harmless_element_still_clicks(self):
        result, _asked, clicked = self.run_click(["Área de desenho"])
        self.assertTrue(result["success"])
        clicked.assert_called_once()

    def test_click_aborts_when_foreground_changes_after_target_is_resolved(self):
        result, _asked, clicked = self.run_click(["Área de desenho"], ((10, "Fixture"), (20, "Outra")))
        self.assertEqual(result["status"], "needs_confirmation")
        clicked.assert_not_called()


class VisionSmartIsGone(unittest.TestCase):
    """S1: vision_smart deixava o modelo de visao clicar/digitar sem nenhuma porta."""

    def test_no_agent_can_use_it_and_the_engine_does_not_know_it(self):
        from core.action_policy import TOOLS, authorize
        self.assertFalse(any("vision_smart" in tools for tools in TOOLS.values()))
        self.assertTrue(authorize("DESKTOP", "x", "vision_smart", {"goal": "mandar a mensagem"}))
        result = _engine().execute("vision_smart", {"goal": "mandar a mensagem"})
        self.assertEqual(result["status"], "rejected")

    def test_desktop_prompt_no_longer_teaches_blocked_actions(self):
        from agents.desktop_agent import PROMPT_FALLBACK
        self.assertNotIn('"action":"click"', PROMPT_FALLBACK)
        self.assertNotIn("run_python", PROMPT_FALLBACK)


class ScreenshotShortcut(unittest.TestCase):
    """S2: "tire um print da tela" gerava run_python, que o validador e o motor recusam."""

    def test_shortcut_passes_the_validator(self):
        from agents.desktop_agent import _utility_steps
        from core.plan_validator import validate_steps
        task = "tire um print da tela"
        steps = _utility_steps(task)
        self.assertEqual([s["action"] for s in steps], ["screenshot"])
        self.assertTrue(validate_steps("DESKTOP", {"task": task, "params": {}}, steps, task).approved)

    def test_screenshot_saves_on_the_real_desktop_folder(self):
        from core import automation
        with tempfile.TemporaryDirectory() as desk:
            shot = Mock()
            shot.save.side_effect = lambda path: Path(path).write_bytes(b"png")
            with patch("core.paths.known_folder", return_value=desk), \
                    patch.object(automation.pyautogui, "screenshot", return_value=shot), \
                    patch.object(automation.subprocess, "Popen") as popen:
                result = _engine()._screenshot({})
            self.assertTrue(result["success"] and result["verified"])
            self.assertEqual(Path(result["artifacts"]["files"][0]).parent, Path(desk))
            popen.assert_not_called()                     # so mostra no Explorer quando pedido (reveal)


class KeyboardFallbackNeverPressesEnter(unittest.TestCase):
    """Sem area de transferencia, digitar tecla a tecla mandava "\\n" como Enter (envia em app de mensagem)."""

    def test_newline_is_refused_and_nothing_is_typed(self):
        from core import automation
        with patch.object(automation.pyautogui, "write") as write:
            self.assertEqual(automation.keyboard_fallback("oi\nmanda"), automation.NEWLINE_REFUSED)
            write.assert_not_called()
            self.assertEqual(automation.keyboard_fallback("oi"), "")
            write.assert_called_once_with("oi")

    def test_typing_actions_are_not_retried(self):
        from desktop.controller import RETRY_ACTIONS
        self.assertFalse(RETRY_ACTIONS & {"uia_type", "vision_type", "type_text", "app_type"})


class ServerWithoutCore(unittest.TestCase):
    """S2: sem nucleo o hello saia mesmo assim e toda chamada voltava "ainda carregando" para sempre."""

    def test_no_hello_without_core_the_connection_closes_to_retry(self):
        from desktop import server as S
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed
        srv = S.EventServer().start()
        self.addCleanup(srv.stop)

        async def go():
            async with connect(f"ws://127.0.0.1:{srv.port}") as ws:
                await ws.send(json.dumps({"token": srv.token}))
                with self.assertRaises(ConnectionClosed) as cm:
                    await ws.recv()
                return cm.exception.rcvd.code
        with patch.object(S, "CORE_WAIT_S", 0.3):
            self.assertEqual(asyncio.run(asyncio.wait_for(go(), 10)), 4503)

    def test_failure_text_says_what_happened_and_where_to_look(self):
        from desktop.web_host import core_failure_text
        text = core_failure_text(ValueError("config.yaml invalido" + "x" * 500))
        self.assertIn("vai fechar", text)
        self.assertIn("ValueError: config.yaml invalido", text)
        self.assertIn("app.log", text)
        self.assertLess(len(text), 700)


class HistoryReadOnce(unittest.TestCase):
    def test_history_screen_reads_the_file_once(self):
        from desktop import history_store
        from desktop.bridge_core import BridgeCore
        items = [{"success": True, "metrics": {"cost_usd": 0.5}, "duration_ms": 1000}] * 3
        with patch.object(history_store, "list_all", return_value=items) as read:
            data = json.loads(BridgeCore.loadHistory(object.__new__(BridgeCore)))
        read.assert_called_once()
        self.assertEqual(data["stats"]["total"], 3)
        self.assertEqual(data["stats"]["total_cost_usd"], 1.5)


class GateKeepsTheRealActionLogClean(unittest.TestCase):
    """O gate gravava acoes falsas dos testes em logs/actions.jsonl (o registro real de quem usa o app)."""

    def test_override_redirects_the_action_log(self):
        from core import action_logger
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "sub" / "actions.jsonl"
            with patch.dict("os.environ", {action_logger.LOG_ENV: str(target)}), \
                    patch.object(action_logger, "LOG_FILE", Path(folder) / "real.jsonl"):
                action_logger.log_action("DESKTOP", "wait", {}, {"success": True})
                self.assertEqual(action_logger.get_failure_stats()["total"], 1)
            self.assertTrue(target.is_file())
            self.assertFalse((Path(folder) / "real.jsonl").exists())

    def test_gate_sets_the_override(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "check_release.py").read_text(encoding="utf-8")
        self.assertIn("CREATIVE_AIX_ACTION_LOG", source)


if __name__ == "__main__":
    unittest.main()
