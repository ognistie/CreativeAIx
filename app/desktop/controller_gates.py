"""Portas de confirmação do Controller (separadas de desktop/controller.py): aprovar o plano e confirmar um
efeito (envio, pagamento...) com o executor parado naquela ação. Uma resposta nunca inicia uma tarefa nova."""
from __future__ import annotations

import secrets
import time


class GateMixin:
    """Aprovação do plano e confirmação de efeito; usa self._lock, self._plan_gate e self._emit."""

    def approve_plan(self, ok: bool, token: str = "", skip=None) -> bool:
        """skip: numeros (1..n) dos passos do plano que a pessoa pulou; os outros executam."""
        with self._lock:
            if not token or token != self._plan_token or self._cancel_event.is_set():
                return False
            self._plan_skip = {int(n) for n in (skip or []) if isinstance(n, int) and not isinstance(n, bool) and n > 0}
            deadline = getattr(self, "_effect_deadline", 0)
            if deadline and time.monotonic() >= deadline:
                return False
            self._plan_token = ""
            self._plan_ok = bool(ok)
            self._plan_gate.set()
            return True

    def reply_to_effect(self, text: str) -> bool:
        from core.action_risk import effect_reply, spoken_effect_code
        code = spoken_effect_code(text)
        refused = effect_reply(text) is False
        with self._lock:
            if not getattr(self, "_effect_deadline", 0):
                return False
            if not refused and (not code or code != self._effect_code):
                return False
            token = self._plan_token
        return self.approve_plan(not refused, token)

    def _wait_effect(self, question: str, from_voice: bool, timeout: float = 180) -> bool:
        """The executor is paused on this exact action; a reply never starts a new task."""
        with self._lock:
            if not self._alive():
                return False
            token = secrets.token_hex(16)
            self._plan_token = token
            self._effect_sequence += 1
            self._effect_code = str(self._effect_sequence)
            self._effect_deadline = time.monotonic() + timeout
            self._plan_ok = False
            self._plan_gate.clear()
        try:
            self._emit("plan_review", {"token": token, "effect": True, "voice": from_voice,
                                      "spoken_code": self._effect_code,
                                      "plan": {"steps": [question]}})
            signaled = self._plan_gate.wait(timeout)
            with self._lock:
                approved = signaled and self._plan_ok and time.monotonic() < self._effect_deadline and self._alive()
            from core.panorama import activity
            activity("decision", status="completed" if approved else "blocked", action="effect_approval")
            return approved
        finally:
            with self._lock:
                self._plan_token = ""
                self._effect_deadline = 0.0
                self._effect_code = ""
            self._emit("plan_review", {})
