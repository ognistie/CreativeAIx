"""Resumo compartilhado com a interface e exportação local de evidências."""
from collections import Counter
from typing import Optional


EXCLUDED = {"cancelado", "indisponivel", "falha_execucao", "timeout"}


def comparison(run: dict) -> dict:
    if len(run["versions"]) != 2:
        return {"regressions": [], "improvements": [], "pairs": 0, "recommendation": "repetir"}
    baseline, candidate = run["versions"]
    pairs = {}
    for result in run["results"]:
        pairs.setdefault((result["case"], result.get("trial", 1)), {})[result["version"]] = result["status"]
    regressions, improvements = [], []
    valid = 0
    for (case, trial), outcomes in pairs.items():
        a, b = outcomes.get(baseline), outcomes.get(candidate)
        if a is None or b is None or a in EXCLUDED or b in EXCLUDED:
            continue
        valid += 1
        if a == "passou" and b != "passou":
            regressions.append({"case": case, "trial": trial})
        elif b == "passou" and a != "passou":
            improvements.append({"case": case, "trial": trial})
    next_step = "repetir"
    if regressions:
        next_step = "ajustar"
    elif run["status"] == "concluido" and improvements and valid == len(pairs):
        next_step = "revisar promoção" if run["origin"] == "real" else "validar com inferência real"
    return {"regressions": regressions, "improvements": improvements, "pairs": valid, "recommendation": next_step}


def report(run: dict, format: str, hypothesis: Optional[str] = None) -> str:
    """Lista permitida de campos. Conteúdo de prompts, fixtures, logs e feedback fica no app."""
    import json
    from agents.memory_agent import _redact_pii
    if format not in ("json", "md"):
        raise ValueError("escolha JSON ou Markdown")
    versions = [{"id": v["id"], "hash": v["hash"]} for v in run.get("version_snapshots", [])]
    case_ids = {case: f"C{number:02d}" for number, case in enumerate(dict.fromkeys(
        row["case"] for row in run["results"]), 1)}
    diagnostic = comparison(run)
    for key in ("regressions", "improvements"):
        for item in diagnostic[key]:
            item["case"] = case_ids[item["case"]]
    payload = {
        "run_id": run["id"], "task_id": run.get("task_id"), "agent": run.get("agent"),
        "started": run.get("started"), "ended": run.get("ended"),
        "origin": run["origin"], "status": run["status"],
        "dataset_version": run["set_version"], "dataset_hash": run.get("dataset_snapshot", {}).get("hash"),
        "versions": versions, "code_revision": run.get("code_revision"), "environment": run.get("environment"),
        "context_mode": run.get("context_mode"), "usage": run.get("usage"), "limits": run.get("protocol", {}).get("limits", {}),
        "runtime_strategies": run.get("runtime_strategies", {}),
        "repeats": run.get("repeats", 1), "split": run.get("split", "all"),
        "summary": run.get("summary", {}), "comparison": diagnostic,
        "cases": [{"id": case_ids[row["case"]], "trial": row.get("trial", 1), "version": row["version"],
                   "status": row["status"], "verified": sum(c["ok"] for c in row.get("checks", [])),
                   "checks": len(row.get("checks", [])), "source_run": row.get("source_run")}
                  for row in run["results"]],
        "method": "Mesmos casos e fixtures para cada versão. Verificação independente por agente.",
        "limitations": "Custos estimados. Código avaliado sem execução e fórmulas sem recálculo. IDs de casos exportados como referências locais.",
    }
    if hypothesis:
        payload["hypothesis"] = _redact_pii(hypothesis[:400])[0]
    if format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    lines = ["# Relatório do AI Research Lab", "", f"Rodada {run['id']} · {run['origin']} · {run['status']}", "",
             payload["method"], "", payload["limitations"], ""]
    if payload.get("hypothesis"):
        lines.extend(["## Hipótese (incluída pela pessoa)", "", payload["hypothesis"], ""])
    for version, summary in payload["summary"].items():
        counts = Counter(case["status"] for case in payload["cases"] if case["version"] == version)
        lines.append(f"- **{version}** · {summary['passed']}/{summary.get('valid', summary['cases'])} casos válidos aprovados · {dict(counts)}")
    lines.extend(["", f"Próximo passo: {diagnostic['recommendation']}", "", "## Evidências", "",
                  "```json", json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), "```", ""])
    return "\n".join(lines)
