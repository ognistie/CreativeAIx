"""Voz → consulta da tela → resultado → conversa, sem microfone nem serviços pagos."""
import collections
import json
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.session import Session
from core.screen_question import answer, is_screen_question
from core.voice.live_session import LiveConversation
from desktop.controller import Controller
from desktop.voice import VoiceController
from desktop.event_bus import bus


class Socket:
    def __init__(self):
        self.events = []

    def send(self, data):
        self.events.append(json.loads(data))


def controller():
    c = Controller.__new__(Controller)
    c.state, c._lock = {"running": False}, threading.Lock()
    c._run_id, c._tls = 0, threading.local()
    c._cancel_event = threading.Event()
    c.session = Session()
    return c


def voice(c):
    v = VoiceController.__new__(VoiceController)
    v.ctrl, v.live, v._inflight, v._expect_reply = c, True, False, False
    v._qlock, v._cmd_q = threading.RLock(), collections.deque()
    v._seq, v._started, v._delegations, v._traces = 0, {}, {}, {}
    v._reply_delegation, v._reply_trace = None, None
    v._recent, v.progress_s, v._voice_epoch = [], 0, 0
    v._later, v._finish = Mock(), Mock()
    v.conv = LiveConversation(player=Mock(speaking=False))
    v.conv._open = True
    return v


class VisualIntent(unittest.TestCase):
    def test_customer_utterance_reaches_vision_without_an_interpreter_call(self):
        from core.followup import resolve
        from core.voice.understand import understand
        for said in ("vendo ali o endereço", "tá vendo esse endereço?", "leia o endereço nessa página"):
            with self.subTest(said=said):
                llm = Mock(side_effect=AssertionError("não deve consultar o intérprete"))
                self.assertEqual(resolve(said, Session(), llm=llm)["kind"], "look")
                self.assertEqual(understand(said, llm=llm)["via"], "tela")
                llm.assert_not_called()

    def test_contextual_question_does_not_turn_into_screen_capture_without_context(self):
        self.assertFalse(is_screen_question("qual é o endereço?"))
        self.assertTrue(is_screen_question("qual é o endereço?", visual_context=True))
        for said in ("vendo meu carro", "abra o Google e olhe a tela", "olha a tela e clica em enviar"):
            self.assertFalse(is_screen_question(said), said)

    def test_details_not_in_accessibility_tree_are_read_from_the_image(self):
        vision = Mock()
        vision.read_local.return_value = {"title": "Pesquisa - Google", "url": "https://example.com", "text": "Resultados"}
        vision.look.return_value = {"answer": "Rua dos Testes, 4826.", "seen": "resultado da busca", "confidence": .93}
        observed = answer("tá vendo esse endereço?", vision)
        self.assertTrue(observed["ok"])
        self.assertEqual(observed["answer"], "Rua dos Testes, 4826.")
        vision.look.assert_called_once()
        self.assertGreater(observed["observed_at"], 0)

    def test_failed_capture_is_reported_and_window_restored(self):
        vision = Mock()
        vision.read_local.return_value = None
        vision.look.side_effect = TimeoutError()
        self.assertFalse(answer("o que tem na tela?", vision)["ok"])
        vision.restore_browser.assert_called_once()


class ExecutionExchange(unittest.TestCase):
    def test_voice_runs_and_gets_visual_result_without_a_react_consumer(self):
        c, finished = controller(), threading.Event()
        v = voice(c)
        v._cmd_q.append(("vendo ali o endereço", "vendo ali o endereço", 0))
        observation = {"ok": True, "answer": "Rua dos Testes, 4826.", "seen": "resultado do Google",
                       "confidence": .93, "via": "vision", "observed_at": 123}
        calls, ui = [], []

        def run(task, dry, report, run_id):
            calls.append((task, c._tls.voice))
            bus.emit("answer", {"msg": observation["answer"], "observation": observation,
                                "run_id": run_id, "session_id": c.session.id})
            finished.set()

        c._run = run
        off_answer = bus.on("answer", v._on_answer)
        off_ui = bus.on("voice_command", ui.append)
        try:
            v._dispatch()
            self.assertTrue(finished.wait(3))
            self.assertEqual(calls, [("vendo ali o endereço", True)])
            self.assertTrue(ui[0]["executing"])
            socket = Socket()
            v.conv._send_pending(socket, "")
            spoken = [e for e in socket.events if e["type"] == "session.commentary.append"]
            self.assertEqual(len(spoken), 1)
            self.assertIn("Rua dos Testes, 4826", spoken[0]["content"])
            self.assertTrue(any("resultado do Google" in e.get("content", "") for e in socket.events))
        finally:
            off_answer()
            off_ui()

    def test_busy_core_does_not_emit_a_new_voice_task(self):
        c = controller()
        c.state["running"] = True
        with patch("desktop.controller.bus.emit") as emit:
            self.assertFalse(c.execute_task("abra o Google", source="voice"))
            emit.assert_not_called()

    def test_core_refuses_a_request_from_the_previous_conversation(self):
        c = controller()
        with patch("desktop.controller.threading.Thread") as thread:
            self.assertFalse(c.execute_task("abra o Google", source="voice", session_id="old"))
            thread.assert_not_called()
        self.assertFalse(c.state["running"])

    def test_reset_during_dispatch_does_not_retry_in_the_new_conversation(self):
        c = controller()
        v = voice(c)

        def refused(*args, **kwargs):
            v._voice_epoch += 1
            c.session.reset()
            return False

        c.execute_task = refused
        v._cmd_q.append(("abra o Google", "abra o Google", 0))
        v._dispatch()
        self.assertFalse(v._cmd_q)
        v._later.assert_not_called()

    def test_rejected_dispatch_retries_without_repeating_a_running_effect(self):
        c = controller()
        c.execute_task = Mock(return_value=False)
        v = voice(c)
        v._cmd_q.append(("abra o Google", "abra o Google", 0))
        v._dispatch()
        self.assertFalse(v._inflight)
        self.assertFalse(v._expect_reply)
        self.assertEqual(v._cmd_q[0][2], 1)
        self.assertEqual(c.execute_task.call_count, 1)

    def test_voice_result_avoids_a_second_rewriting_model(self):
        c = controller()
        c._tls.run_id = 4
        delivered = threading.Event()
        events = []

        def emit(name, payload):
            if name == "assistant_message":
                events.append(payload)
                delivered.set()

        with patch("desktop.controller.bus.emit", side_effect=emit), \
                patch("core.reply.compose") as compose:
            c._after_turn("leia o endereço", "leia o endereço", {"voice": True, "kind": "new", "summary": "Rua dos Testes, 4826."},
                          {"success": True, "verified": True})
            self.assertTrue(delivered.wait(3))
            compose.assert_not_called()
        self.assertEqual(events[0]["text"], "Rua dos Testes, 4826.")
        self.assertTrue(events[0]["verified"])

    def test_old_conversation_result_never_enters_new_voice_context(self):
        c = controller()
        v = voice(c)
        v._inflight = v._expect_reply = True
        v._reply_session_id = "old"
        v._reply_run_id = 4
        v._on_answer({"msg": "resultado antigo", "run_id": 4, "session_id": "old"})
        v._on_assistant({"text": "resultado antigo", "source": "executor", "speak": True,
                         "run_id": 4, "session_id": "old"})
        self.assertFalse(v.conv._outbox)

    def test_session_reset_cancels_pending_voice_and_stops_old_live_session(self):
        v = voice(controller())
        v._cmd_q.append(("tarefa antiga", "tarefa antiga", 0))
        v._pending_guess = "palpite antigo"
        v.record_cancel, v.set_live, v.tts = Mock(), Mock(), Mock()
        v._on_session_reset({})
        self.assertFalse(v._cmd_q)
        self.assertEqual(v._pending_guess, "")
        v.record_cancel.assert_called_once()
        v.set_live.assert_called_once_with(False)


class LiveContext(unittest.TestCase):
    def test_reconnect_keeps_latest_context_and_early_conversation_anchor(self):
        c = controller()
        c.session.add_turn("Meu nome é Joana", "Meu nome é Joana", "chat", [], True)
        c.session.set_last_reply("Olá, Joana")
        for index in range(12):
            c.session.add_turn(f"assunto {index}", f"assunto {index}", "chat", [], True)
            c.session.set_last_reply(f"resposta {index}")
        v = voice(c)
        self.assertIn("Meu nome é Joana", v._conv_context())
        conv = LiveConversation(player=Mock(), context=lambda: "antigo " * 1200 + "RESULTADO MAIS RECENTE")
        payload = conv._session_payload()
        self.assertIn("RESULTADO MAIS RECENTE", payload["input"][0]["content"][0]["text"])
        self.assertIn("Vision", payload["instructions"])

    def test_only_latest_context_is_sent_and_does_not_wake_a_paid_session(self):
        current = ["estado inicial"]
        conv = LiveConversation(player=Mock(), context=lambda: current[0])
        conv.refresh_context()
        self.assertFalse(conv._wake.is_set())
        self.assertFalse(conv._pending_context)
        conv._open = True
        conv.refresh_context()
        current[0] = "estado novo"
        conv.refresh_context()
        socket = Socket()
        conv._send_pending(socket, "")
        text = " ".join(e.get("content", "") for e in socket.events)
        self.assertIn("estado novo", text)
        self.assertNotIn("estado inicial", text)

    def test_long_unicode_results_preserve_tail_facts_and_append_limits(self):
        conv = LiveConversation(player=Mock())
        conv._open = True
        text = "Descrição 🌳 com números e contexto. " * 35 + "Telefone 11 4826 1234."
        conv.say(text, "delegacao_1")
        socket = Socket()
        conv._send_pending(socket, "")
        self.assertTrue(all(len(e["content"].encode("utf-8")) <= 480 for e in socket.events))
        # O limite da fala é explícito; o dado completo é transmitido pelo canal de contexto.
        conv.think(text, "delegacao_1")
        socket = Socket()
        conv._send_pending(socket, "")
        self.assertIn("Telefone 11 4826 1234.", " ".join(e["content"] for e in socket.events))
        self.assertTrue(all(e["delegation_id"] == "delegacao_1" for e in socket.events))
