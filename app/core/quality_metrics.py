"""Métricas contínuas de qualidade, calculadas dos registros que o app já grava a cada pedido.

Fontes (locais, fora do git): desktop/data/history.jsonl (um pedido por linha: sucesso, estado, duração, custo,
efeitos feitos antes de falhar) e memory/authorization.jsonl (cada efeito que passou pela porta de confirmação).
Nada é enviado para fora; o resultado traz só números, nunca o texto dos pedidos.

Métricas (por 100 pedidos quando é taxa):
- taxa de sucesso; travas (tarefa parada pelo vigia por não avançar); cancelamentos;
- ações não pedidas: efeito que a porta interceptou e que a fala não pedia;
- efeito antes de falhar: tarefa que falhou depois de um envio/pagamento confirmado (risco de duplicar);
- custo por pedido (US$) e latência p50/p95 (s).
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

APP = Path(__file__).resolve().parents[1]
HISTORY = APP / "desktop" / "data" / "history.jsonl"
AUTHZ = APP / "memory" / "authorization.jsonl"
STALL = "parado: a tarefa ficou sem avançar"


def _rows(path: Path) -> list[dict]:
    out = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _when(row: dict, *keys: str) -> Optional[datetime]:
    for key in keys:
        try:
            return datetime.fromisoformat(str(row.get(key))[:19])
        except (TypeError, ValueError):
            continue
    return None


def _percentile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 2)


def measured_cost(metrics: dict) -> float | None:
    cost = metrics.get("cost_usd")
    if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
        return None
    if metrics.get("cost_known") is False or metrics.get("unknown_cost_calls"):
        return None
    # Linhas antigas podem trazer um zero padrão sem nenhuma medição.
    if cost == 0 and metrics.get("cost_known") is not True and metrics.get("api_calls") != 0:
        return None
    return float(cost)


def compute(history: Iterable[dict], authz: Iterable[dict], last: int = 200) -> dict:
    """Métricas dos últimos `last` pedidos; os registros de autorização contam só a partir do mais antigo deles."""
    runs = [r for r in history if not str(r.get("error") or "").startswith(("clarification", "limitation"))][-last:]
    n = len(runs)
    since = min((t for t in (_when(r, "started_at", "timestamp", "ended_at") for r in runs) if t), default=None)
    gate = [a for a in authz if since is None or (_when(a, "at") or since) >= since]
    per100 = (lambda count: round(100 * count / n, 1)) if n else (lambda count: None)
    seconds = [r["duration_ms"] / 1000 for r in runs if isinstance(r.get("duration_ms"), (int, float))]
    costs = [cost for r in runs if (cost := measured_cost(r.get("metrics") or {})) is not None]
    verified = sum(r.get("success") is True and r.get("verified") is True for r in runs)
    measured_runtime = [r["runtime"] for r in runs if isinstance(r.get("runtime"), dict)]
    unrequested = [a for a in gate if a.get("requested") is False]
    return {
        "pedidos": n,
        "taxa_sucesso": round(sum(1 for r in runs if r.get("success")) / n, 3) if n else None,
        "taxa_sucesso_verificado": round(verified / n, 3) if n else None,
        "custo_por_sucesso_verificado_usd": round(sum(costs) / verified, 5) if verified and len(costs) == n else None,
        "custo_medido_usd": round(sum(costs), 5) if costs else None,
        "pedidos_com_custo_medido": len(costs),
        "pedidos_sem_custo_medido": n - len(costs),
        "tokens_total": sum((r.get("metrics") or {}).get("tokens_est", 0) or 0 for r in runs),
        "tentativas_adicionais": sum(r.get("retries", 0) for r in measured_runtime),
        "passos_recuperados": sum(r.get("recovered", 0) for r in measured_runtime),
        "falsos_sucessos": sum(r.get("false_successes", 0) for r in measured_runtime),
        "pedidos_com_metricas_runtime": len(measured_runtime),
        "travas_por_100": per100(sum(1 for r in runs if str(r.get("error") or "") == STALL)),
        "cancelados_por_100": per100(sum(1 for r in runs if r.get("status") == "cancelled"
                                         and str(r.get("error") or "") != STALL)),
        "acoes_nao_pedidas_por_100": per100(len(unrequested)),
        "acoes_nao_pedidas_executadas": sum(1 for a in unrequested
                                            if a.get("decision") in ("allowed", "approved_once")),
        "efeito_antes_de_falhar_por_100": per100(sum(1 for r in runs if r.get("effects_done") and not r.get("success"))),
        "custo_por_pedido_usd": round(sum(costs) / n, 5) if n and len(costs) == n else None,
        "latencia_p50_s": _percentile(seconds, 0.5),
        "latencia_p95_s": _percentile(seconds, 0.95),
    }


def snapshot(last: int = 200, history_path: Path = HISTORY, authz_path: Path = AUTHZ) -> dict:
    return compute(_rows(history_path), _rows(authz_path), last=last)
