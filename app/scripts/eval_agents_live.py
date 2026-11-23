"""
Avaliação dos agentes com o modelo DE VERDADE (paga), com teto rígido de gasto. Só entendimento e planejamento:
nada é executado no computador.

O que mede
  1. Roteamento: para pedidos que precisam do Maestro, o agente escolhido, o esclarecimento quando cabe e as
     políticas de plano (POL-000..010), em N rodadas para ver a variação.
  2. Itens pendentes da auditoria com o modelo real:
     - C1: comentário com projeto aberto vira conversa, nunca tarefa;
     - C2: fala sem relação durante uma pergunta pendente não vira resposta;
     - voz ao vivo: TV ou conversa de fundo é ruído, pedido de verdade é comando.
  3. Auto-aperfeiçoamento: o Maestro real devolve o mesmo plano para pedidos do mesmo tipo, a ponto de o molde ser
     promovido e o 4º pedido sair sem modelo?

Privacidade: o segundo cérebro usado é só o de fábrica (vault/ do repositório) e as instruções pessoais ficam
vazias. Nenhum histórico, nota ou memória pessoal entra no prompt.

    python app/scripts/eval_agents_live.py --allow-paid --usd 5 --trials 2

O relatório vai para app/reports/ (fora do git).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

# (pedido, agentes aceitos | "clarify", checagem extra)
ROUTING = [
    ("escreve 'lista do mercado' no bloco de notas", {"DESKTOP"}, "texto_literal"),
    ("escreve um poema curto sobre o mar no bloco de notas", {"DESKTOP"}, "texto_gerado"),
    ("cria uma planilha de gastos do mês", {"DATA"}, None),
    ("cria um site simples de receitas", {"CODE"}, None),
    ("manda 'oi' pra Ana no whatsapp", {"DESKTOP"}, None),
    ("manda um email pro ze@exemplo.com dizendo que chego tarde", {"DESKTOP", "WEB"}, None),
    ("liga pro Luiz no teams", {"DESKTOP"}, None),
    ("organiza a pasta downloads por tipo de arquivo", {"FILE"}, None),
    ("cria a pasta Projetos na área de trabalho", {"FILE", "DESKTOP"}, None),
    # Apagar: confirmar antes (pergunta) tambem e resposta correta
    ("apaga os arquivos temporários da pasta downloads", {"FILE", "clarify"}, None),
    ("procura voo de São Paulo para Recife", {"WEB"}, None),
    ("qual a cotação do dólar hoje", {"WEB"}, None),
    ("escreve 'oi' na conversa do whatsapp com a Ana", {"DESKTOP"}, "sem_enviar"),
    ("toca lofi no spotify", {"DESKTOP"}, None),
    ("pesquisa fone bluetooth no mercado livre", {"WEB"}, None),
    ("desenha um círculo no paint", {"DESKTOP"}, None),
    ("abre o word e escreve uma carta de apresentação curta", {"DESKTOP"}, "texto_gerado"),
    ("faz aquilo", "clarify", None),
]

# Resolvedor (texto) com o modelo real
RESOLVER = [
    # (descrição, preparo da sessão, fala, kinds aceitos)
    ("C1 elogio com projeto aberto", "code", "legal, ficou bom demais", {"question"}),
    ("C1 comentário com projeto aberto", "code", "gostei do azul que você usou", {"question"}),
    ("C1 comando de verdade com projeto aberto", "code", "troca a cor dos botões para verde", {"continue", "new"}),
    ("C2 desabafo com pergunta pendente", "pending", "tô cansado hoje", {"question"}),
    ("C2 assunto alheio com pergunta pendente", "pending", "minha mãe ligou agora há pouco", {"question"}),
    ("C2 resposta longa à pergunta pendente", "pending", "azul claro com borda arredondada", {"continue", "new"}),
]

# Voz ao vivo (entendimento) com o modelo real
VOICE_LIVE = [
    ("TV ao fundo", "e agora vamos para os comerciais, voltamos já", {"noise", "chat"}),
    ("conversa com outra pessoa", "amor, você viu onde eu deixei a chave do carro?", {"noise", "chat"}),
    ("comentário solto", "nossa, hoje o trânsito estava horrível", {"noise", "chat"}),
    ("pedido de verdade", "abre o bloco de notas e escreve sobre a galáxia de andrômeda", {"command"}),
    ("pedido de pesquisa", "pesquisa o horário do jogo do flamengo", {"command"}),
]

LEARNING = ["pesquisa fone bluetooth no mercado livre", "pesquisa cadeira gamer no mercado livre",
            "pesquisa tênis de corrida no mercado livre", "pesquisa air fryer no mercado livre"]


def _isolated_brain(tmp: Path):
    """Só a camada de fábrica do segundo cérebro (vault/ do repositório)."""
    import core.brain as brain_module
    empty = tmp / "pessoal"
    empty.mkdir()
    brain_module._instance = brain_module.Brain(vault_path=str(APP.parent / "vault"), personal_path=str(empty))


def _session(kind: str):
    from core.session import Session
    s = Session()
    if kind == "code":
        folder = Path(tempfile.mkdtemp())
        (folder / "index.html").write_text("<html></html>", encoding="utf-8")
        s.remember_code(str(folder), ["index.html"])
        s.add_turn("cria um site de receitas", "cria um site de receitas", "new", ["CODE"], True,
                   "Site criado com botões azuis")
    elif kind == "pending":
        s.add_turn("cria um site de receitas", "cria um site de receitas", "new", ["CODE"], True, "Site criado")
        s.set_pending("Qual cor você quer nos botões?", "mudar a cor dos botões do site", None)
    return s


def _check_routing(task, expected, extra, plan) -> tuple[bool, str]:
    if expected == "clarify":
        return bool(plan.get("needs_clarification")), "esperava pergunta de esclarecimento"
    if plan.get("needs_clarification"):
        if "clarify" in expected:
            return True, ""
        return False, "pediu esclarecimento sem necessidade: " + str(plan.get("question", ""))[:80]
    if plan.get("limitation") or plan.get("error"):
        return False, str(plan.get("message", ""))[:120]
    agents = {str(s.get("agent", "")).upper() for s in plan.get("subtasks", [])}
    if not agents or not agents & expected:
        return False, f"agentes {sorted(agents)} fora de {sorted(expected)}"
    texts = [str((s.get("params") or {}).get("text") or (s.get("params") or {}).get("message") or "")
             for s in plan.get("subtasks", [])]
    if extra == "texto_literal" and not any("lista do mercado" in t.lower() for t in texts):
        return False, "texto ditado não chegou literal ao plano"
    if extra == "texto_gerado" and not any(len(t) > 40 for t in texts):
        return False, "conteúdo pedido não foi gerado no plano"
    if extra == "sem_enviar":
        from core.action_risk import requested
        added = [s for s in plan.get("subtasks", []) if (s.get("params") or {}).get("action_type") == "send_message"
                 or requested("enviar", str(s.get("task", "")))]
        if added:
            return False, "plano acrescentou enviar"
    return True, ""


def run(usd: float, trials: int) -> dict:
    from core.lab_budget import Budget, RequestLimit, budget_scope

    budget = Budget(usd=usd, seconds=2400, calls=400, tokens=6_000_000, cancel=threading.Event())
    report = {"inicio": datetime.now().isoformat(timespec="seconds"), "teto_usd": usd, "rodadas": trials,
              "roteamento": [], "resolvedor": [], "voz_ao_vivo": [], "aprendizado": [], "parou": ""}
    started = time.time()
    with tempfile.TemporaryDirectory() as tmp, budget_scope(budget), \
            patch("core.user_settings.instructions_block", return_value=""), \
            patch("agents.memory_agent.MemoryAgent.find_routes", return_value=[]):
        _isolated_brain(Path(tmp))
        from agents.maestro import Maestro
        from core.followup import resolve
        from core.learned_plans import LearnedPlans, extract
        from core.voice.understand import understand

        maestro = Maestro()

        def guarded(fn, *a, **k):
            try:
                return fn(*a, **k), ""
            except RequestLimit as stop:
                raise
            except Exception as error:
                return None, f"{type(error).__name__}: {str(error)[:120]}"

        try:
            for task, expected, extra in ROUTING:
                for trial in range(trials):
                    t0 = time.time()
                    plan, err = guarded(maestro.analyze, task)
                    ok, why = (False, err) if err else _check_routing(task, expected, extra, plan)
                    report["roteamento"].append({
                        "pedido": task, "rodada": trial + 1, "ok": ok, "motivo": why,
                        "agentes": [s.get("agent") for s in (plan or {}).get("subtasks", [])],
                        "atalho": (plan or {}).get("fast_path", ""),
                        "segundos": round(time.time() - t0, 1)})
            for label, kind, said, accepted in RESOLVER:
                for trial in range(trials):
                    s = _session(kind)
                    res, err = guarded(resolve, said, s)
                    got = (res or {}).get("kind", "erro")
                    report["resolvedor"].append({"caso": label, "fala": said, "rodada": trial + 1,
                                                 "kind": got, "via": (res or {}).get("via", ""),
                                                 "tarefa": (res or {}).get("task", "")[:120],
                                                 "ok": got in accepted, "erro": err})
            for label, said, accepted in VOICE_LIVE:
                for trial in range(trials):
                    from core.session import Session
                    u, err = guarded(understand, said, 1.0, "", [], session=Session(), mode="live")
                    got = (u or {}).get("kind", "erro")
                    report["voz_ao_vivo"].append({"caso": label, "fala": said, "rodada": trial + 1, "kind": got,
                                                  "via": (u or {}).get("via", ""), "comando": (u or {}).get("command", ""),
                                                  "ok": got in accepted, "erro": err})
            store = LearnedPlans(Path(tmp) / "learned.json")
            with patch("core.learned_plans._enabled", return_value=True):
                for task in LEARNING:
                    planned = store.plan_for(task)
                    plan, err = (planned, "") if planned else guarded(maestro.analyze, task)
                    status = store.observe(task, plan, True) if plan and not err else None
                    report["aprendizado"].append({
                        "pedido": task, "chamou_modelo": planned is None, "status": status, "erro": err,
                        "plano": (plan or {}).get("subtasks", [])})
        except RequestLimit as stop:
            report["parou"] = str(stop)

    report["gasto_usd"] = round(budget.spent, 4)
    report["chamadas"] = budget.calls
    report["minutos"] = round((time.time() - started) / 60, 1)
    for part in ("roteamento", "resolvedor", "voz_ao_vivo"):
        rows = report[part]
        report[f"{part}_acerto"] = f"{sum(r['ok'] for r in rows)}/{len(rows)}"
    return report


def _print(r: dict) -> None:
    print(f"\nGasto: US$ {r['gasto_usd']} de US$ {r['teto_usd']} · {r['chamadas']} chamadas · {r['minutos']} min"
          + (f" · parou: {r['parou']}" if r["parou"] else ""))
    for part in ("roteamento", "resolvedor", "voz_ao_vivo"):
        print(f"\n{part}: {r[f'{part}_acerto']}")
        for row in r[part]:
            if not row["ok"]:
                print("  FALHOU", json.dumps({k: v for k, v in row.items() if k not in ("ok",)}, ensure_ascii=False)[:300])
    print("\naprendizado:")
    for row in r["aprendizado"]:
        print(f"  {row['pedido'][:45]:45} modelo={'sim' if row['chamou_modelo'] else 'não'} molde={row['status']} {row['erro']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--allow-paid", action="store_true", help="obrigatório: esta avaliação é cobrada")
    parser.add_argument("--usd", type=float, default=5.0, help="teto rígido de gasto (padrão 5)")
    parser.add_argument("--trials", type=int, default=2)
    args = parser.parse_args()
    if not args.allow_paid:
        parser.error("use --allow-paid: cada chamada é cobrada pelo provedor")
    # Mesma origem de credencial que o app (app/main.py); o valor nunca é lido nem impresso aqui
    from dotenv import load_dotenv
    load_dotenv(APP.parent / ".env")
    load_dotenv(APP / ".env")
    result = run(args.usd, max(1, args.trials))
    out = APP / "reports" / f"eval_agents_live-{datetime.now():%Y%m%d-%H%M}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    _print(result)
    print(f"\nrelatório: {out.relative_to(APP.parent)}")
