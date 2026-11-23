"""
Bateria de cenários dos agentes, SEM API e sem tocar no desktop.

Cada pedido passa pelo caminho real até antes de executar: intérprete da conversa → atalhos sem modelo → planos
aprendidos → Maestro (o modelo é substituído por um que falha se for chamado) → agente de domínio → validador de
passos → política por agente → classificação de efeito. Nada é executado.

Mede, por categoria:
  - quantos pedidos chegam a um plano válido sem chamar a IA;
  - se o agente escolhido é o esperado;
  - quais passos teriam efeito externo (e por isso pediriam confirmação);
  - o ganho do auto-aperfeiçoamento: depois de 3 sucessos com o mesmo plano, quantos pedidos do mesmo tipo deixam
    de chamar o modelo.

    python app/scripts/bench_agents_offline.py            # relatório
    python app/scripts/bench_agents_offline.py --json     # para comparar rodadas

A memória de rotas local não é lida (substituída por vazia). O dicionário e as notas do segundo cérebro são lidos
como no app (só leitura); nada é gravado fora de uma pasta temporária.
"""
from __future__ import annotations

import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))


class ModelCalled(RuntimeError):
    pass


class NoModel:
    """Cliente de modelo que registra e recusa toda chamada."""
    calls: list = []

    def message(self, **kw):
        NoModel.calls.append(kw.get("agent") or "?")
        raise ModelCalled(kw.get("agent") or "?")

    def message_with_meta(self, **kw):
        return {"text": self.message(**kw)}

    metrics = {"total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_cost_usd": 0.0}
    on_progress = None


# (categoria, pedido, agentes esperados ou resposta esperada, deve sair sem IA?)
# "resposta:<kind>" = o intérprete responde sem plano (papo, tela, cancelar, esclarecer...).
SCENARIOS = [
    # Abrir apps e sites (atalho do dicionário)
    ("abrir", "abre o bloco de notas", ["DESKTOP"], True),
    ("abrir", "abrir o excel", ["DESKTOP"], True),
    ("abrir", "abre a calculadora", ["DESKTOP"], True),
    ("abrir", "abre o spotify", ["DESKTOP"], True),
    ("abrir", "abre o youtube", ["WEB"], True),
    ("abrir", "abre o g1", ["WEB"], True),
    ("abrir", "abre o whatsapp", ["DESKTOP"], True),
    ("abrir", "abre o vs code", ["DESKTOP"], True),
    ("abrir", "abre o teams", ["DESKTOP"], True),
    ("abrir", "abre o paint", ["DESKTOP"], True),
    # Pastas e Configurações
    ("sistema", "abre a pasta downloads", ["DESKTOP", "FILE"], None),
    ("sistema", "abre as configurações de bluetooth", ["DESKTOP"], None),
    ("sistema", "abre as configurações de som", ["DESKTOP"], None),
    ("sistema", "abre as configurações do windows", ["DESKTOP"], None),
    # Pesquisa (precisa do Maestro na primeira vez; aprendível)
    ("pesquisa", "pesquisa receita de bolo no google", ["WEB"], False),
    ("pesquisa", "pesquisa lofi no youtube", ["WEB"], False),
    ("pesquisa", "procura voo para recife", ["WEB"], False),
    ("pesquisa", "qual a cotação do dólar hoje", ["WEB"], False),
    # Escrever e criar conteúdo (precisa de modelo: conteúdo composto)
    ("escrever", "escreve 'lista do mercado' no bloco de notas", ["DESKTOP"], False),
    ("escrever", "escreve um poema sobre o mar no bloco de notas", ["DESKTOP"], False),
    ("escrever", "cria uma planilha de gastos do mês", ["DATA"], False),
    ("escrever", "cria um site de receitas", ["CODE"], False),
    ("escrever", "faz um resumo desse texto no word", ["DESKTOP"], False),
    # Mensagens, e-mail, chamadas (efeito externo: confirmação obrigatória)
    ("comunicar", "manda 'oi' pra Ana no whatsapp", ["DESKTOP"], False),
    ("comunicar", "manda um email pro ze@exemplo.com dizendo que chego tarde", ["DESKTOP", "WEB"], False),
    ("comunicar", "liga pro Luiz no teams", ["DESKTOP"], False),
    # Arquivos
    ("arquivos", "organiza a pasta downloads por tipo", ["FILE"], False),
    ("arquivos", "cria a pasta Projetos na área de trabalho", ["FILE"], False),
    ("arquivos", "apaga os arquivos temporários da pasta downloads", ["FILE"], False),
    # Agentes de código externos
    # Pasta inexistente: o agente externo pergunta em vez de criar ou adivinhar
    ("codigo", "com o claude, corrige o README na pasta C:\Pasta\Inexistente", "resposta:clarify", True),
    # Respostas sem plano
    ("conversa", "obrigado", "resposta:question", True),
    ("conversa", "valeu, era isso", "resposta:question", True),
    ("conversa", "legal, ficou ótimo", "resposta:question", True),
    ("conversa", "bom dia", "resposta:question", True),
    ("conversa", "para", "resposta:cancel", True),
    ("conversa", "cancela", "resposta:cancel", True),
    ("tela", "você está vendo o youtube?", "resposta:look", True),
    ("tela", "o que tem na minha tela?", "resposta:look", True),
    ("ambiguo", "abre aquilo", "resposta:clarify", True),
    ("ambiguo", "faz aquilo de novo", "resposta:clarify", True),
    ("ambiguo", "manda isso pra ele", "resposta:clarify", True),
]

# Pedidos do mesmo tipo para medir o auto-aperfeiçoamento: os 3 primeiros ensinam, os demais devem sair sem IA
LEARNING = [
    "pesquisa fone bluetooth no mercado livre", "pesquisa cadeira gamer no mercado livre",
    "pesquisa tênis de corrida no mercado livre", "pesquisa air fryer no mercado livre",
    "pesquisa monitor 24 polegadas no mercado livre", "pesquisa capa de celular no mercado livre",
]


def _maestro_search_plan(task: str) -> dict:
    """O plano que o Maestro devolve para 'pesquisa X no mercado livre' (o modelo simulado so neste trecho:
    loja sem atalho proprio, entao a primeira vez passa pelo Maestro)."""
    from urllib.parse import quote_plus
    from core.learned_plans import extract
    query = next((v for k, v in extract(task)[1].items() if k.startswith("consulta")), task)
    return {"analysis": "pesquisar no Mercado Livre", "skills": [], "subtasks": [{
        "agent": "WEB", "task": f"pesquisar {query} no Mercado Livre",
        "params": {"query": query,
                   "url": f"https://www.mercadolivre.com.br/jm/search?as_word={quote_plus(query)}"}}]}


def _agents():
    from agents.code_agent import CodeAgent
    from agents.data_agent import DataAgent
    from agents.desktop_agent import DesktopAgent
    from agents.extcode_agent import ExtCodeAgent
    from agents.file_agent import FileAgent
    from agents.web_agent import WebAgent
    built = {"DATA": DataAgent(), "WEB": WebAgent(), "CODE": CodeAgent(), "DESKTOP": DesktopAgent(),
             "FILE": FileAgent(), "EXTCODE": ExtCodeAgent()}
    for agent in built.values():
        if hasattr(agent, "_client"):
            agent._client = NoModel()
    return built


def _plan_request(task: str, maestro, agents, session, learned) -> dict:
    """Caminho do controller até antes de executar. -> resultado da medição."""
    from agents.extcode_agent import extcode_plan
    from agents.maestro import continue_plan, vault_plan
    from core.action_policy import authorize
    from core.action_risk import step_risk
    from core.existing_targets import existing_plan
    from core.followup import resolve
    from core.plan_validator import validate_steps

    NoModel.calls.clear()
    out = {"task": task, "kind": "", "agents": [], "actions": [], "effects": [], "model_calls": [], "error": ""}
    try:
        res = resolve(task, session, llm=lambda s, u: NoModel().message(agent="RESOLVER"))
    except ModelCalled:
        res = {"kind": "new", "task": task, "target": None, "via": "modelo"}
    out["kind"] = res["kind"]
    if res["kind"] in ("question", "look", "cancel", "clarify", "undo"):
        out["model_calls"] = list(NoModel.calls)
        return out
    route = res["task"]
    ext = extcode_plan(route, session)
    if ext and ext.get("reroute"):
        route, ext = ext["reroute"], None
    try:
        plan = vault_plan(route) or existing_plan(route, session) or ext \
            or continue_plan(route, res["kind"], res.get("target"), session) \
            or learned.plan_for(route) or maestro.analyze(route)
    except ModelCalled:
        plan = {"error": True, "message": "Maestro precisa do modelo"}
    if plan.get("needs_clarification"):
        out["kind"] = "clarify"
        out["model_calls"] = list(NoModel.calls)
        return out
    if plan.get("error") or not plan.get("subtasks"):
        out["error"] = plan.get("message") or "sem plano"
        out["model_calls"] = list(NoModel.calls)
        return out
    out["fast_path"] = plan.get("fast_path", "")
    for sub in plan["subtasks"]:
        name = str(sub.get("agent", "")).upper()
        out["agents"].append(name)
        agent = agents.get(name)
        if agent is None:
            out["error"] = f"agente desconhecido {name}"
            continue
        params = dict(sub.get("params") or {})
        payload = {"task": sub.get("task", ""), "original_task": route, "params": params}
        try:
            ctx = params if name == "DESKTOP" and params.get("app") else None
            agent_plan = agent.plan(payload, context=ctx)
        except ModelCalled:
            agent_plan = {"error": f"{name} precisa do modelo"}
        except Exception as error:                       # defeito real: aparece no relatório
            agent_plan = {"error": f"{name} quebrou: {type(error).__name__}: {error}"}
        steps = agent_plan.get("steps") or []
        if agent_plan.get("error") or not steps:
            out["error"] = out["error"] or str(agent_plan.get("error") or f"{name} sem passos")
            continue
        check = validate_steps(name, sub, steps, route)
        if not check.approved:
            out["error"] = out["error"] or f"{name} reprovado: {check.summary()}"
        for step in steps:
            action, sparams = step.get("action", ""), step.get("params") or {}
            out["actions"].append(action)
            denied = authorize(name, task, action, sparams)
            if denied:
                out["error"] = out["error"] or f"política: {denied[:80]}"
            kind = step_risk(action, sparams)
            if kind:
                out["effects"].append(kind)
    out["model_calls"] = list(NoModel.calls)
    return out


def run(json_out: bool = False) -> dict:
    from core.session import Session
    from core.learned_plans import LearnedPlans

    with tempfile.TemporaryDirectory() as tmp, \
            patch("core.ai_client.get_client", return_value=NoModel()), \
            patch("core.ai_client._instance", NoModel()), \
            patch("agents.memory_agent.MemoryAgent.find_routes", return_value=[]), \
\
            patch("core.learned_plans._enabled", return_value=True):
        from agents.maestro import Maestro
        maestro = Maestro.__new__(Maestro)
        maestro._client, maestro._memory = NoModel(), None
        from core.config import get_config
        maestro._config, maestro.model, maestro.effort = get_config(), "simulado", "low"
        agents = _agents()
        learned = LearnedPlans(Path(tmp) / "learned.json")

        rows, by_cat = [], defaultdict(lambda: {"total": 0, "sem_ia": 0, "agente_ok": 0, "erros": 0})
        for cat, task, expected, free_expected in SCENARIOS:
            r = _plan_request(task, maestro, agents, Session(), learned)
            free = not r["model_calls"] and not r["error"]
            if isinstance(expected, str):
                agent_ok = expected == f"resposta:{r['kind']}"
            else:
                agent_ok = bool(r["agents"]) and all(a in expected for a in r["agents"]) if free else None
            r.update(categoria=cat, sem_ia=free, agente_ok=agent_ok, esperado_sem_ia=free_expected)
            rows.append(r)
            c = by_cat[cat]
            c["total"] += 1
            c["sem_ia"] += free
            c["agente_ok"] += bool(agent_ok)
            # Erro de verdade: nao e "precisa do modelo", e quebra, politica ou plano reprovado
            c["erros"] += bool(r["error"]) and "precisa do modelo" not in r["error"] and "sem passos" not in r["error"]

        # Auto-aperfeiçoamento: Maestro simulado responde os 3 primeiros; o resto deve vir do molde aprendido
        learning = []
        for i, task in enumerate(LEARNING):
            planned = learned.plan_for(task)
            used_model = planned is None
            plan = planned or _maestro_search_plan(task)
            learned.observe(task, plan, True)
            learning.append({"pedido": task, "chamou_modelo": used_model,
                             "status": next((e["status"] for e in learned.entries()), "")})

    report = {
        "total": len(rows),
        "sem_ia": sum(r["sem_ia"] for r in rows),
        "por_categoria": dict(by_cat),
        "divergencias": [
            {k: r[k] for k in ("categoria", "task", "kind", "agents", "error", "model_calls")}
            for r in rows
            if r["agente_ok"] is False or (r["esperado_sem_ia"] is True and not r["sem_ia"])
            or (r["error"] and "precisa do modelo" not in r["error"] and "sem passos" not in r["error"])
        ],
        "efeitos": [{"task": r["task"], "efeitos": r["effects"]} for r in rows if r["effects"]],
        "aprendizado": learning,
        "chamadas_poupadas": sum(not x["chamou_modelo"] for x in learning),
    }
    if json_out:
        print(json.dumps({**report, "linhas": rows}, ensure_ascii=False, indent=1))
    else:
        _print(report, rows)
    return report


def _print(report: dict, rows: list) -> None:
    print(f"\nCenários: {report['total']} · prontos sem IA: {report['sem_ia']}\n")
    print(f"{'categoria':10} {'total':>5} {'sem IA':>7} {'agente ok':>9} {'erros':>6}")
    for cat, c in report["por_categoria"].items():
        print(f"{cat:10} {c['total']:>5} {c['sem_ia']:>7} {c['agente_ok']:>9} {c['erros']:>6}")
    print("\nPor pedido:")
    for r in rows:
        mark = "sem IA" if r["sem_ia"] else ("IA: " + ",".join(sorted(set(r["model_calls"]))) if r["model_calls"]
                                              else "falhou")
        what = r["kind"] if not r["agents"] else "+".join(r["agents"])
        extra = f" · efeitos: {','.join(r['effects'])}" if r["effects"] else ""
        err = f" · {r['error'][:70]}" if r["error"] and "precisa do modelo" not in r["error"] else ""
        print(f"  [{r['categoria']:9}] {r['task'][:52]:52} → {what:14} {mark}{extra}{err}")
    if report["divergencias"]:
        print("\nDivergências:")
        for d in report["divergencias"]:
            print("  ", json.dumps(d, ensure_ascii=False))
    print("\nAuto-aperfeiçoamento (mesmo tipo de pedido):")
    for x in report["aprendizado"]:
        print(f"  {x['pedido'][:45]:45} modelo={'sim' if x['chamou_modelo'] else 'não':3}  molde={x['status']}")
    print(f"  chamadas ao Maestro poupadas: {report['chamadas_poupadas']} de {len(report['aprendizado'])}")


if __name__ == "__main__":
    run(json_out="--json" in sys.argv)
