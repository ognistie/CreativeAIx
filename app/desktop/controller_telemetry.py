"""Telemetria do Controller (separada de desktop/controller.py): log estruturado, uso e custo do modelo por
execução e o andamento enquanto o modelo escreve."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


class TelemetryMixin:
    """Log, custo e andamento; usa self._emit, self.state e self._ai_client."""

    # Rotulo do andamento enquanto o modelo escreve (tarefas longas)
    _PROGRESS_LABEL = {
        "MAESTRO": "Planejando", "CODE": "Escrevendo o código", "DATA": "Montando a planilha",
        "WEB": "Planejando a navegação", "DESKTOP": "Planejando os passos", "FILE": "Organizando",
        "APP_PILOT": "Operando o app", "VISION": "Lendo a tela", "NARRATOR": "Escrevendo o relatório",
        "READER": "Lendo o arquivo",
    }

    def _on_llm_progress(self, agent: str, stage: str, chars: int) -> None:
        """Mostra o modelo trabalhando ("Montando a planilha · 2.400 caracteres") em vez de
        um texto parado por 30-70 s. So durante uma tarefa (a resposta final e a voz rodam
        fora dela e nao podem reabrir o estado de execucao)."""
        label = self._PROGRESS_LABEL.get((agent or "").upper())
        if not label or not self.state.get("running"):
            return
        if stage == "thinking" or not chars:
            msg = f"{label} · pensando"
        else:
            msg = f"{label} · {chars:,} caracteres".replace(",", ".")
        self._emit("phase", {"phase": "agent", "msg": msg, "progress": True})

    def _log(self, level: str, agent: str, msg: str,
             extra: Optional[Dict[str, Any]] = None) -> None:
        """Helper para emitir logs estruturados."""
        payload = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "level": level,
            "agent": agent,
            "msg": msg,
        }
        if extra:
            payload["extra"] = extra
        self._emit("log", payload)

    def _emit_usage(self) -> None:
        """Emite uso REAL agregado do AIClient (custo por modelo + tokens)."""
        m = self._ai_client.metrics
        payload = {
            "calls": m["total_calls"],
            "tokens_est": (m["total_input_tokens"] + m["total_output_tokens"]
                           + m.get("total_cache_read_tokens", 0)
                           + m.get("total_cache_write_tokens", 0)),
            "input_tokens": m["total_input_tokens"],
            "output_tokens": m["total_output_tokens"],
            "cache_read_tokens": m.get("total_cache_read_tokens", 0),
            "cost_usd": round(m["total_cost_usd"], 5),
            "unknown_cost_calls": m.get("unknown_cost_calls", 0),
            "by_model": m.get("calls_by_model", {}),
        }
        self._emit("api_usage", payload)

    @staticmethod
    def _metrics_delta(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uso de UMA execucao. O AIClient acumula desde a abertura do app;
        gravar o acumulado no historico fazia o total somar custos repetidos.
        """
        def d(key):
            return after.get(key, 0) - before.get(key, 0)

        by_agent = {}
        for agent, cur in after.get("calls_by_agent", {}).items():
            prev = before.get("calls_by_agent", {}).get(agent, {})
            calls = cur["calls"] - prev.get("calls", 0)
            if calls:
                by_agent[agent] = {
                    "calls": calls,
                    "cost_usd": round(cur["cost_usd"] - prev.get("cost_usd", 0.0), 6),
                    "ms": cur.get("ms", 0) - prev.get("ms", 0),
                }
        return {
            "api_calls": d("total_calls"),
            "tokens_est": (d("total_input_tokens") + d("total_output_tokens")
                           + d("total_cache_read_tokens") + d("total_cache_write_tokens")),
            "input_tokens": d("total_input_tokens"),
            "output_tokens": d("total_output_tokens"),
            "cache_read_tokens": d("total_cache_read_tokens"),
            "cache_write_tokens": d("total_cache_write_tokens"),
            "cost_usd": round(d("total_cost_usd"), 6),
            "unknown_cost_calls": d("unknown_cost_calls"),
            "cost_known": d("unknown_cost_calls") == 0,
            "llm_ms": d("total_llm_ms"),
            "by_agent": by_agent,
            "truncated": d("truncated"),
        }
