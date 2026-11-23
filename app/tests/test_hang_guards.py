"""Auditoria de 23/11/2026: travas (A2-A5) e itens M/B. Sem rede, sem modelo real, sem tela."""
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import action_risk as R


def bare_controller(**extra):
    from desktop.controller import Controller
    c = Controller.__new__(Controller)
    c._lock, c.state, c._run_id, c._tls = threading.Lock(), {"running": True}, 1, threading.local()
    c._cancel_event, c._plan_gate, c._plan_token, c._config = threading.Event(), threading.Event(), "", None
    for key, value in extra.items():
        setattr(c, key, value)
    return c


class A2_SpokenEffectCode(unittest.TestCase):
    def test_voice_says_the_code_digit_by_digit(self):
        from desktop.voice import effect_prompt_text
        text = effect_prompt_text("Antes de enviar preciso da sua confirmação.", "1001")
        self.assertIn("confirmo 1 0 0 1", text)
        self.assertIn("Ou diga não", text)

    def test_code_is_understood_in_digits_or_words(self):
        for said in ("confirmo 1001", "confirmo 1 0 0 1", "Confirmo um zero zero um.", "confirmo um, zero, zero, um"):
            self.assertEqual(R.spoken_effect_code(said), "1001", said)
        self.assertEqual(R.spoken_effect_code("confirmo um"), "")

    def test_prompt_is_spoken_and_reminded_only_while_waiting(self):
        from desktop.voice import VoiceController
        v = VoiceController.__new__(VoiceController)
        v._inflight, v.live, said, later = True, False, [], []
        v._say = lambda text, **k: said.append(text)
        v._later = lambda seconds, fn: later.append(fn)
        v.ctrl = Mock(_plan_token="t1")
        v._on_effect_prompt({"effect": True, "token": "t1", "spoken_code": "1002", "plan": {"steps": ["Antes de ligar."]}})
        self.assertIn("confirmo 1 0 0 2", said[0])
        later[0]()                                  # a mesma confirmacao ainda espera: lembra
        self.assertEqual(len(said), 2)
        v.ctrl._plan_token = ""
        later[0]()                                  # ja respondida: nao lembra
        self.assertEqual(len(said), 2)
        v._on_effect_prompt({})                     # fechamento do cartao: nada a dizer
        self.assertEqual(len(said), 2)


class A3_StopReachesTheModelCall(unittest.TestCase):
    def client(self):
        from core.ai_client import AIClient
        c = AIClient.__new__(AIClient)
        c.on_progress = None
        return c

    def test_cancelled_task_aborts_the_stream(self):
        from core.ai_client import LLMCancelled, bind_cancel
        bind_cancel(lambda: True)
        try:
            with self.assertRaises(LLMCancelled):
                self.client()._relay_progress(iter([Mock(type="message_start")]), "MAESTRO", time.time())
        finally:
            bind_cancel(None)

    def test_total_deadline_aborts_a_slow_stream(self):
        from core import ai_client
        with patch.object(ai_client, "call_limit_s", return_value=30.0):
            with self.assertRaises(ai_client.LLMCancelled):
                self.client()._relay_progress(iter([Mock(type="message_start")]), "MAESTRO", time.time() - 31)

    def test_other_threads_are_not_cancelled(self):
        from core.ai_client import _scope, bind_cancel
        bind_cancel(lambda: True)
        seen = []
        t = threading.Thread(target=lambda: seen.append(getattr(_scope, "should_stop", None)))
        t.start()
        t.join()
        bind_cancel(None)
        self.assertEqual(seen, [None])

    def test_new_request_while_stopping_says_so(self):
        c = bare_controller(session=Mock(id="s1"))
        c._cancel_event.set()
        events = []
        with patch("desktop.controller.bus.emit", side_effect=lambda name, payload=None: events.append(payload)):
            self.assertFalse(c.execute_task("abre o bloco de notas"))
        self.assertIn("parando", events[0]["msg"])


class A4_WaitsAndWatchdog(unittest.TestCase):
    def test_plan_timeout_is_capped(self):
        from core.wait_engine import MAX_WAIT_S, _cap
        self.assertEqual(_cap(600, 15), MAX_WAIT_S)
        self.assertEqual(_cap("lixo", 15), 15.0)

    def test_wait_for_window_stops_on_cancel(self):
        from core.wait_engine import wait_for_window
        started = time.time()
        r = wait_for_window("janela-que-nao-existe-xyz", 600, should_stop=lambda: True)
        self.assertFalse(r["success"])
        self.assertLess(time.time() - started, 5)

    def test_wait_for_element_escapes_the_title(self):
        from core.wait_engine import wait_for_element
        r = wait_for_element("app(", "elemento[", 1, should_stop=lambda: True)
        self.assertFalse(r["success"])

    def test_idle_task_is_stopped_by_the_watchdog(self):
        c = bare_controller(IDLE_LIMIT_S=0.1, _last_activity=time.monotonic() - 10)
        with patch("desktop.controller.bus.emit") as emit:
            c._start_watchdog(1)
            self.assertTrue(c._cancel_event.wait(6))
        self.assertIn("sem avançar", emit.call_args[0][1]["msg"])

    def test_waiting_for_the_person_is_not_idle(self):
        c = bare_controller(IDLE_LIMIT_S=0.1, _last_activity=time.monotonic() - 10, _plan_token="tok")
        c._start_watchdog(1)
        self.assertFalse(c._cancel_event.wait(3))
        c.state["running"] = False


class A5_PilotClockPausesForThePerson(unittest.TestCase):
    def test_confirmation_time_does_not_count(self):
        from core.app_pilot import AppPilot
        pilot = AppPilot(llm=Mock(), authorize_ui=lambda kind, act, label: (time.sleep(0.3), "")[1])
        pilot._paused, pilot._window = 0.0, "geral | Slack"
        self.assertTrue(pilot._check("press", "", key="enter"))
        self.assertGreaterEqual(pilot._paused, 0.3)


class M_RoutingPlansAndVoice(unittest.TestCase):
    def fake_session(self, key):
        tgt = {"type": "app", "key": key, "hwnd": 1}
        return SimpleNamespace(target=lambda name: tgt if name == f"app:{key}" else None,
                               agent_for=lambda name: "DESKTOP")

    def test_writing_reuses_open_doc_only_when_the_resolver_said_so(self):
        from core.lexicon import get_lexicon
        from core.routing import continue_target_for
        key = get_lexicon().app_key("bloco de notas")
        s = self.fake_session(key)
        params = {"app": "bloco de notas", "text": "lista do mercado"}
        self.assertIsNone(continue_target_for(s, "DESKTOP", params, None, "abre o bloco de notas e escreve")[0])
        self.assertIsNotNone(continue_target_for(s, "DESKTOP", params, f"app:{key}", "escreve aí")[0])
        self.assertIsNotNone(continue_target_for(s, "DESKTOP", {"app": "bloco de notas"}, None, "abre o bloco de notas")[0])

    def test_click_that_happened_is_never_repeated(self):
        from desktop.controller import should_retry
        self.assertFalse(should_retry("browser_click", {"success": False, "result": "⚠️ Clique por visão sem efeito"}))
        self.assertFalse(should_retry("vision_click", {"success": False, "result": "⛔ Antes de enviar..."}))
        self.assertTrue(should_retry("vision_click", {"success": False, "result": "❌ Enviar: não encontrado"}))
        self.assertFalse(should_retry("type_text", {"success": False, "result": "❌ x"}))

    def test_code_filter_remaps_dependencies(self):
        from agents.maestro import Maestro
        from core.config import get_config
        plan = {"subtasks": [
            {"agent": "DESKTOP", "task": "abrir o bloco de notas e colar o código",
             "params": {"app": "notepad", "action_type": "paste", "text": "<html>"}},
            {"agent": "CODE", "task": "criar o site", "params": {}},
            {"agent": "WEB", "task": "abrir o site criado", "params": {}, "depends_on": 2},
            {"agent": "DESKTOP", "task": "mostrar o resultado", "params": {"app": "explorer"}, "depends_on": 1},
        ]}
        m = Maestro.__new__(Maestro)
        m._config, m.model, m.effort = get_config(), "claude-sonnet-5", "low"
        m._client = Mock(message=Mock(return_value=json.dumps(plan)))
        out = m._ask("cria um site e abre")
        self.assertEqual([s["agent"] for s in out["subtasks"]], ["CODE", "WEB", "DESKTOP"])
        self.assertEqual([s.get("depends_on") for s in out["subtasks"]], [None, 1, None])

    def test_voice_dedupe_ignores_case_accents_and_punctuation(self):
        from desktop.voice import similar_request
        self.assertTrue(similar_request("Abrir o Bloco de Notas.", "abrir o bloco de notas"))
        self.assertFalse(similar_request('escrever "Oi" no Bloco', 'escrever "Olá" no Bloco'))

    def test_failure_before_the_task_starts_frees_the_app(self):
        c = bare_controller()
        with patch("desktop.controller.bus.emit") as emit:
            c._run("abre o bloco de notas", False, False, 1)    # sem _ai_client: falha antes do try interno
        self.assertFalse(c.state["running"])
        self.assertIn("execution_finished", [call.args[0] for call in emit.call_args_list])

    def test_new_external_effects_are_covered_by_pol009(self):
        from core.plan_validator import validate_plan
        plan = {"subtasks": [{"agent": "WEB", "task": "abrir o perfil e bloquear o contato", "params": {}}]}
        self.assertFalse(validate_plan("abre o perfil do Ze", plan).approved)


if __name__ == "__main__":
    unittest.main()
