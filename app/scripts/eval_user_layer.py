"""Avaliacao da camada do usuario (segundo cerebro + Harness + Voce), sem custo.

Pergunta: o que o usuario escreve chega DE FATO ao que seria enviado ao modelo?
Para cada papel (Maestro, cada agente e a resposta final) a avaliacao planta um marcador
unico no Harness ou no Voce, roda o codigo real de montagem do prompt com um cliente
simulado que so registra a chamada, e confere o marcador na mensagem capturada (estado
final independente do retorno das funcoes). Tambem confere os casos negativos: sem camada
pessoal ou com modelo vazio, nenhum marcador aparece.

  python scripts/eval_user_layer.py          relatorio; sai com 1 se algum caso falhar
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

AGENTS = ("WEB", "DESKTOP", "CODE", "DATA", "FILE")
TASK = "organizar a planilha de vendas e mandar o resumo"


class Recorder:
    """Cliente simulado: guarda o que seria enviado e devolve um plano minimo."""
    def __init__(self):
        self.calls = []

    def message(self, model, system, user_content, **kw):
        self.calls.append({"system": system, "user": str(user_content), "agent": kw.get("agent", "")})
        return json.dumps({"analysis": "x", "subtasks": [{"agent": "DATA", "task": TASK}]})

    def message_with_meta(self, **kw):
        return {"text": self.message(**kw), "cost_usd": 0}


def run():
    import core.ai_client as ac
    import core.brain as cb
    from core.config import get_config
    from core.harness import YOU_SECTIONS, you_rel, you_template

    tmp = Path(tempfile.mkdtemp(prefix="eval-camada-"))
    vault = tmp / "cofre"
    src = (ROOT / get_config().get("brain.vault_path", "../vault")).resolve()
    shutil.copytree(src, vault, ignore=shutil.ignore_patterns(".obsidian", ".trash", "40 Execucoes", "50 Diario"))
    results = []

    def case(name, ok, detail=""):
        results.append({"case": name, "ok": bool(ok), "detail": detail})

    recorder = Recorder()
    old_client, old_brain = ac._instance, cb._instance
    ac._instance = recorder
    try:
        # ── Sem camada pessoal: nada do usuario aparece ──────────────────
        cb._instance = cb.Brain(str(vault))
        from agents.base_agent import brain_guide
        case("sem camada pessoal: agentes sem marcador", all("CANARIO" not in brain_guide(a, TASK) for a in AGENTS))

        # ── Camada pessoal com marcadores ───────────────────────────────
        brain = cb.Brain(str(vault), personal_path=str(tmp / "pessoal"))
        cb._instance = brain
        for section, hint in YOU_SECTIONS:                       # modelos vazios primeiro
            brain.store.write(you_rel(section), you_template(section, hint))
        case("Você só com modelo vazio: nada entra", "Sobre o usuário" not in brain_guide("DATA", TASK))
        brain.store.write(you_rel("Jeito de falar"), you_template("Jeito de falar", "dica") + "CANARIO-VOCE fala 'planilhinha'.")
        brain.harness.save({"agents": {a: {"instructions": f"CANARIO-{a} instrucao do usuario."}
                                       for a in ("MAESTRO",) + AGENTS},
                            "response": {"tone": "direto", "extra": "CANARIO-RESPOSTA terminar com o caminho."}})

        for a in AGENTS:                                         # o texto que cada agente poe no pedido
            g = brain_guide(a, TASK)
            case(f"{a}: instrução do Harness no prompt", f"CANARIO-{a}" in g)
            case(f"{a}: Você no prompt", "CANARIO-VOCE" in g)
            case(f"{a}: não recebe instrução de outro agente",
                 not any(f"CANARIO-{b}" in g for b in AGENTS + ("MAESTRO",) if b != a))

        from agents.maestro import Maestro
        recorder.calls.clear()
        Maestro().analyze(TASK)
        sent = "\n".join(c["system"] + "\n" + c["user"] for c in recorder.calls)
        case("Maestro: chamou o modelo", bool(recorder.calls), f"{len(recorder.calls)} chamada(s)")
        case("Maestro: instrução do Harness no prompt", "CANARIO-MAESTRO" in sent)
        case("Maestro: Você no prompt", "CANARIO-VOCE" in sent)

        from core.reply import compose
        seen = {}
        compose("organiza a planilha", TASK, "Planilha organizada em 3 abas.", True,
                llm=lambda system, user: seen.setdefault("system", system) and "Pronto.")
        case("resposta final: padrão de resposta no prompt", "CANARIO-RESPOSTA" in seen.get("system", ""))

        # Lista negra: instrução nunca vira permissão (o validador de plano nao le o Harness)
        import inspect
        import core.plan_validator as pv
        import core.action_risk as ar
        case("permissões não leem o Harness",
             "harness" not in inspect.getsource(pv).lower() and "harness" not in inspect.getsource(ar).lower())
    finally:
        ac._instance, cb._instance = old_client, old_brain
        shutil.rmtree(tmp, ignore_errors=True)
    return results


def main():
    results = run()
    for r in results:
        print(("PASS " if r["ok"] else "FAIL ") + r["case"] + (f" · {r['detail']}" if r["detail"] else ""))
    ok = sum(r["ok"] for r in results)
    print(f"{ok}/{len(results)} casos")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
