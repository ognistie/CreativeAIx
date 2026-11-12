"""
Resumo para a tela Atividade (F4 do estudo de design): so le o que o app ja registra
(desktop/history_store.py e a pergunta pendente da sessao). Nao grava nada e nao chama modelo.

summarize(items, now, pending, running) -> dict com:
- today:   execucoes de hoje (hora, pedido, ok/falhou, duracao, agentes), mais recente primeiro
- usage:   custo/chamadas/tokens do mes, divididos por agente (para o medidor segmentado),
           custo por dia nos ultimos 14 dias
- heatmap: 7 x 24 (dia da semana x hora) com o numero de execucoes dos ultimos 30 dias
- attention: o que espera a pessoa (pergunta ou confirmacao pendente)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _when(entry: dict) -> Optional[datetime]:
    raw = entry.get("started_at") or entry.get("ended_at")
    try:
        return datetime.fromisoformat(str(raw)) if raw else None
    except ValueError:
        return None


def _agents(entry: dict) -> list:
    out = []
    for sub in entry.get("subtasks") or []:
        agent = str((sub or {}).get("agent") or "").upper()
        if agent and agent not in out:
            out.append(agent)
    return out


def summarize(items: list, now: Optional[datetime] = None, pending: Optional[dict] = None,
              running: Optional[str] = None) -> dict:
    now = now or datetime.now()
    today, month_cost, month_calls, month_tokens = [], 0.0, 0, 0
    by_agent = defaultdict(float)
    days = {(now.date() - timedelta(days=i)): 0.0 for i in range(13, -1, -1)}
    heat = [[0] * 24 for _ in range(7)]
    month_runs = ok_runs = 0
    for e in items or []:
        when = _when(e)
        if when is None or e.get("dry_run"):
            continue
        m = e.get("metrics") or {}
        cost = float(m.get("cost_usd") or 0.0)
        agents = _agents(e) or ["MAESTRO"]
        if when.date() == now.date():
            today.append({"time": when.strftime("%H:%M"), "task": str(e.get("task", ""))[:120],
                          "ok": bool(e.get("success")), "duration_ms": int(e.get("duration_ms") or 0),
                          "agents": agents, "status": e.get("status") or ("ok" if e.get("success") else "falhou")})
        if (when.year, when.month) == (now.year, now.month):
            month_runs += 1
            ok_runs += 1 if e.get("success") else 0
            month_cost += cost
            month_calls += int(m.get("api_calls") or 0)
            month_tokens += int(m.get("tokens_est") or 0)
            for a in agents:
                by_agent[a] += cost / len(agents)
        if when.date() in days:
            days[when.date()] += cost
        if now - when <= timedelta(days=30):
            heat[when.weekday()][when.hour] += 1
    today.sort(key=lambda t: t["time"], reverse=True)
    total = sum(by_agent.values())
    segments = sorted(({"agent": a, "cost": round(c, 4), "share": (c / total) if total else 0.0}
                       for a, c in by_agent.items()), key=lambda s: -s["cost"])
    attention = []
    if pending and pending.get("question"):
        attention.append({"kind": pending.get("kind", "clarify"), "text": str(pending["question"])[:200],
                          "task": str(pending.get("task", ""))[:120]})
    peak = max((max(row) for row in heat), default=0)
    return {
        "running": running or "",
        "attention": attention,
        "today": today[:30],
        "usage": {"cost": round(month_cost, 4), "calls": month_calls, "tokens": month_tokens,
                  "runs": month_runs, "success_rate": round(ok_runs / month_runs * 100) if month_runs else 0,
                  "segments": segments[:6],
                  "daily": [{"day": d.strftime("%d/%m"), "cost": round(c, 4)} for d, c in days.items()]},
        "heatmap": {"rows": heat, "peak": peak, "weekdays": WEEKDAYS},
    }
