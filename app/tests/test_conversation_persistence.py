"""Conversa gravada x resposta escrita em segundo plano (auditoria 2026-11-17, S1).

Antes: o pedido so era gravado DEPOIS da resposta do assistente (uma chamada ao modelo de 1 a 3 s). Abrir outra
conversa nesse intervalo apagava o pedido e gravava a resposta dele na conversa aberta.
"""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import session as session_mod
from core.session import Session


def _controller(session):
    from desktop.controller import Controller
    c = Controller.__new__(Controller)
    c.session, c.state, c._lock = session, {"running": False}, threading.Lock()
    c._tls, c._run_id = threading.local(), 1
    return c


class SlowReply:
    """compose que demora como o modelo; `started` avisa quando a resposta comecou a ser escrita."""

    def __init__(self, text):
        self.text, self.started, self.release = text, threading.Event(), threading.Event()

    def __call__(self, *args, **kwargs):
        self.started.set()
        self.release.wait(5)
        return {"text": self.text, "speak": False}


class ConversationPersistence(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        folder = patch.object(session_mod, "SESSIONS_DIR", self.base)
        folder.start()
        self.addCleanup(folder.stop)
        events = patch("desktop.controller.bus.emit")
        events.start()
        self.addCleanup(events.stop)

    def finish_request(self, ctl, said, reply):
        """O fim de um pedido como no _run: registra o pedido e dispara a resposta em segundo plano."""
        slow = SlowReply(reply)
        turn = {"kind": "new", "agents": ["DESKTOP"], "summary": "feito", "content": ""}
        entry = {"success": True}
        target = ctl._record_turn(said, said, turn, entry)
        with patch("core.reply.compose", slow):
            ctl._after_turn(said, said, turn, entry, *target)
            self.assertTrue(slow.started.wait(5))
        return slow, target[0]

    def wait_reply(self, sid, said, expected):
        for _ in range(100):
            data = Session.read_saved(sid) or {}
            turns = [t for t in data.get("turns", []) if t["said"] == said]
            if turns and turns[-1]["reply"] == expected:
                return
            time.sleep(0.02)
        self.fail(f"resposta '{expected}' nao chegou em {sid}")

    def saved_b(self):
        b = Session()
        b.add_turn("pedido de B", "pedido de B", "new", [], True, "ok")
        b.set_last_reply("resposta de B")
        b.save()
        return b

    def test_opening_another_conversation_keeps_both_intact(self):
        b = self.saved_b()
        ctl = _controller(Session())
        slow, a_id = self.finish_request(ctl, "pedido de A", "Resposta de A")
        self.assertIsNotNone(Session.read_saved(a_id), "o pedido tem de estar gravado antes da resposta")
        ctl.open_conversation(b.id)
        slow.release.set()
        self.wait_reply(a_id, "pedido de A", "Resposta de A")
        self.assertEqual(Session.read_saved(b.id)["turns"][-1]["reply"], "resposta de B")
        self.assertEqual(ctl.session.turns[-1].reply, "resposta de B")

    def test_new_conversation_does_not_lose_the_finished_request(self):
        ctl = _controller(Session())
        slow, a_id = self.finish_request(ctl, "pedido de A", "Resposta de A")
        ctl.new_session()
        slow.release.set()
        self.wait_reply(a_id, "pedido de A", "Resposta de A")
        self.assertEqual(ctl.session.turns, [])

    def test_restart_restores_last_accessed_conversation(self):
        b = self.saved_b()
        ctl = _controller(Session())
        ctl._record_turn("mais recente", "mais recente", {"kind": "new", "agents": [], "summary": ""}, {"success": True})
        ctl.open_conversation(b.id)
        restored = Session()
        restored.restore_active()
        self.assertEqual(restored.id, b.id)
        self.assertEqual(restored.turns[0].reply, "resposta de B")
        self.assertTrue(Session.delete_saved(b.id))
        restored = Session()
        restored.restore_active()
        self.assertTrue(restored.empty)

    def test_restart_keeps_explicitly_empty_conversation(self):
        self.saved_b()
        _controller(Session()).new_session()
        restored = Session()
        restored.restore_active()
        self.assertTrue(restored.empty)

    def test_reply_goes_to_its_own_request_when_another_one_follows(self):
        ctl = _controller(Session())
        slow, a_id = self.finish_request(ctl, "primeiro pedido", "Resposta do primeiro")
        ctl._record_turn("segundo pedido", "segundo pedido",
                         {"kind": "new", "agents": [], "summary": "", "content": ""}, {"success": True})
        slow.release.set()
        self.wait_reply(a_id, "primeiro pedido", "Resposta do primeiro")
        self.assertEqual(ctl.session.turns[-1].reply, "")

    def test_concurrent_saves_of_the_same_conversation_do_not_collide(self):
        s = Session()
        s.add_turn("pedido", "pedido", "new", [], True)
        errors = []

        def save():
            try:
                for _ in range(20):
                    s.save()
            except Exception as error:      # o .tmp unico era disputado e o os.replace falhava
                errors.append(error)
        threads = [threading.Thread(target=save) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(list(self.base.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
