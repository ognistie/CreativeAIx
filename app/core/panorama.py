"""
Panorama do harness: os dados que a cena 3D da interface desenha (ui/src/lib/panorama.ts).

Tres camadas, todas lidas do que o app ja guarda, sem chamar modelo nem gravar nada:
  roteamento  por onde os pedidos passaram (atalho sem IA, plano aprendido, conversa, Maestro) e com que resultado,
              a partir do historico de execucoes (desktop/data/history.jsonl)
  evolucao    o auto-aperfeicoamento: planos aprendidos (core/learned_plans.py: candidato -> promovido / bloqueado) e
              as hipoteses do Lab (core/rsi.py: aguardando decisao, promovida, refutada...)
  agentes     quanto cada agente trabalhou e com que taxa de acerto

A memoria em notas (Cerebro) a interface ja le por brainOverview/brainGraph; aqui fica so o que nao tinha caminho.
Textos que saem daqui sao curtos: moldes de pedido ja vem sem dado pessoal (learned_plans redige), e hipoteses do Lab
mostram so o objetivo e o resultado.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Optional
from contextvars import ContextVar
from contextlib import contextmanager
from time import monotonic
from threading import RLock

# Observacao local e limitada: nao executa ferramentas, nao transporta prompts e nao decide permissoes.
STAGES = frozenset({"stimulus", "understanding", "memory", "context", "planning", "decision",
                    "transmission", "execution", "verification", "learning", "recovery", "model"})
STATES = frozenset({"started", "observed", "completed", "verified", "failed", "blocked", "uncertain", "cancelled"})
MAX_EVENTS = 256
_trace = ContextVar("cognitive_trace", default=None)


class ActivityTrace:
    def __init__(self, run_id, publish=lambda event: None):
        self.run_id, self.publish = run_id, publish
        self.started, self.events, self.dropped = monotonic(), [], 0
        self._lock = RLock()

    def record(self, stage, *, agent="", status="observed", count=0, refs=(), action=""):
        with self._lock:
            self._record(stage, agent=agent, status=status, count=count, refs=refs, action=action)

    def _record(self, stage, *, agent, status, count, refs, action):
        if stage not in STAGES or status not in STATES:
            return
        if len(self.events) >= MAX_EVENTS:
            self.dropped += 1
            return
        event = {"seq": len(self.events), "ms": round((monotonic() - self.started) * 1000),
                 "stage": stage, "agent": str(agent).upper()[:32], "status": status,
                 "count": max(0, int(count)), "refs": [str(r)[:160] for r in refs][:16],
                 "action": str(action)[:64]}
        self.events.append(event)
        try:
            self.publish({**event, "run_id": self.run_id})
        except Exception:
            pass  # A falha do observatorio nao altera a execucao da tarefa.


@contextmanager
def activity_scope(trace):
    token = _trace.set(trace)
    try:
        yield trace
    finally:
        _trace.reset(token)


def activity(stage, **metadata):
    trace = _trace.get()
    if trace is not None:
        trace.record(stage, **metadata)


def activity_callback():
    """Captura apenas o observador para leitores de stdout; nao transfere permissoes para a thread."""
    trace = _trace.get()
    return trace.record if trace is not None else lambda *args, **kwargs: None


def capture_event(name, payload):
    """Traduz eventos existentes sem interpretar frases como evidencias de atividade."""
    p = payload if isinstance(payload, dict) else {}
    if name == "resolved":
        activity("understanding", status="completed")
    elif name == "plan_ready":
        activity("decision", status="completed", count=len(p.get("plan", {}).get("steps", [])))
    elif name == "plan_review" and p:
        activity("decision", status="blocked")
    elif name == "step_start":
        activity("execution", status="started", agent=p.get("agent", ""), action=p.get("action", ""))
    elif name in ("cancelled", "error"):
        activity("decision", status="cancelled" if name == "cancelled" else "failed")


def recorded_runs(history):
    """Replay so de eventos capturados, nunca inferido do sucesso da tarefa."""
    out = []
    for row in history:
        if not isinstance(row, dict) or row.get("dry_run"):
            continue
        events = []
        for e in (row.get("cognitive") or [])[:MAX_EVENTS]:
            if not isinstance(e, dict) or e.get("stage") not in STAGES or e.get("status") not in STATES:
                continue
            events.append({k: e[k] for k in ("seq", "ms", "stage", "agent", "status", "count", "refs", "action") if k in e})
        out.append({"id": str(row.get("id") or ""), "when": str(row.get("started_at") or ""),
                    "ok": bool(row.get("success")), "route": _route_of_entry(row), "events": events,
                    "dropped": row.get("cognitive_dropped", 0)})
        if len(out) == 12:
            break
    return out

# Rotas na ordem do caminho de um pedido (a interface desenha os nos nesta ordem)
ROUTES = ("resposta", "atalho", "aprendido", "continuar", "conversa", "maestro")
_FAST = {"abrir": "atalho", "pesquisar": "atalho", "extcode": "atalho", "continuar": "continuar"}
_HANDED = "conversa→"
MAX_RUNS = 200
MAX_PLANS = 40
MAX_HYPOTHESES = 40


def route_of(plan: Optional[dict], handed_by_chat: bool = False) -> str:
    """Rota de um pedido que virou plano: plano aprendido, atalho sem IA, continuar no que esta aberto ou Maestro.
    handed_by_chat: a conversa devolveu o pedido de acao (fica registrado como "conversa→<rota>")."""
    plan = plan or {}
    if plan.get("learned_key"):
        route = "aprendido"
    elif plan.get("fast_path"):
        route = _FAST.get(str(plan["fast_path"]), "atalho")
    else:
        route = "maestro"
    return _HANDED + route if handed_by_chat else route


def _route_of_entry(entry: dict) -> str:
    """Rota de uma execucao antiga (sem o campo route): inferida pelo que ficou registrado."""
    route = entry.get("route")
    if isinstance(route, str) and route:
        return route
    agents = {str(s.get("agent") or "").upper() for s in entry.get("subtasks") or [] if isinstance(s, dict)}
    if "CHAT" in agents:
        return "conversa"
    if agents & {"VISION", "READER"}:
        return "resposta"
    if not agents:
        # Sem agente: respondida direto, ou o Maestro voltou sem plano (esclarecimento, "Sem subtasks")
        return "maestro" if entry.get("error") else "resposta"
    if entry.get("learned"):
        return "aprendido"
    return "maestro"


def _agents_of(entry: dict) -> list[str]:
    out = []
    for s in entry.get("subtasks") or []:
        name = str((s or {}).get("agent") or "").upper() if isinstance(s, dict) else ""
        if name and name not in out:
            out.append(name)
    return out


def routing(entries: Iterable[dict]) -> dict:
    """Trafego por rota e por agente nas ultimas execucoes reais (simulacao fica fora)."""
    runs = [e for e in entries if isinstance(e, dict) and not e.get("dry_run")][:MAX_RUNS]
    by_route: dict = defaultdict(lambda: {"runs": 0, "ok": 0, "ms": 0})
    by_agent: dict = defaultdict(lambda: {"runs": 0, "ok": 0})
    edges = Counter()
    recent = []
    for e in runs:
        route = _route_of_entry(e)
        base = route.split("→")[-1]
        ok = bool(e.get("success"))
        r = by_route[base]
        r["runs"] += 1
        r["ok"] += 1 if ok else 0
        r["ms"] += int(e.get("duration_ms") or 0)
        if route.startswith(_HANDED):
            edges[("conversa", base)] += 1
        for agent in _agents_of(e):
            by_agent[agent]["runs"] += 1
            by_agent[agent]["ok"] += 1 if ok else 0
            edges[(base, agent)] += 1
        if len(recent) < 12:
            recent.append({"route": route, "ok": ok, "agents": _agents_of(e),
                           "when": str(e.get("ended_at") or e.get("started_at") or "")[:16],
                           "ms": int(e.get("duration_ms") or 0)})
    total = len(runs)
    return {
        "total": total,
        "routes": [{"route": k, "runs": v["runs"], "ok": v["ok"],
                    "avg_ms": round(v["ms"] / v["runs"]) if v["runs"] else 0} for k, v in by_route.items()],
        "agents": [{"agent": k, "runs": v["runs"], "ok": v["ok"]} for k, v in by_agent.items()],
        "edges": [{"from": a, "to": b, "runs": n} for (a, b), n in edges.most_common(40)],
        "recent": recent,
    }


def evolution(plans: Iterable[dict], science: Iterable[dict]) -> dict:
    """Planos aprendidos (mais recentes primeiro) e hipoteses do Lab (mais recentes primeiro)."""
    plan_rows = []
    for p in list(plans)[:MAX_PLANS]:
        if not isinstance(p, dict):
            continue
        plan_rows.append({"key": str(p.get("key") or "")[:40], "template": str(p.get("template") or "")[:120],
                          "status": p.get("status") if p.get("status") in ("candidate", "promoted", "blocked") else "candidate",
                          "successes": int(p.get("successes") or 0), "failures": int(p.get("failures") or 0),
                          "streak": int(p.get("streak") or 0), "replays": int(p.get("replays") or 0),
                          "agents": [str(a) for a in (p.get("agents") or [])][:4]})
    hyp_rows = []
    for row in list(science)[:MAX_HYPOTHESES]:
        if not isinstance(row, dict):
            continue
        hyp_rows.append({"id": str(row.get("id") or "")[:16], "agent": str(row.get("agent") or "").upper(),
                         "objective": str(row.get("objective") or "")[:140], "result": str(row.get("result") or "")[:40],
                         "origin": str(row.get("origin") or "")[:12], "when": str(row.get("when") or "")[:16]})
    counts = Counter(p["status"] for p in plan_rows)
    return {"plans": plan_rows, "hypotheses": hyp_rows,
            "summary": {"promoted": counts.get("promoted", 0), "candidate": counts.get("candidate", 0),
                        "blocked": counts.get("blocked", 0), "hypotheses": len(hyp_rows)}}


def build(history: Iterable[dict], plans: Iterable[dict], science: Iterable[dict]) -> dict:
    history = list(history)
    return {"routing": routing(history), "evolution": evolution(plans, science), "runs": recorded_runs(history)}
