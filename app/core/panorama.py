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
    return {"routing": routing(history), "evolution": evolution(plans, science)}
