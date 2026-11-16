"""Linha de base da recuperacao do segundo cerebro (sem modelo, sem custo).

Para pedidos fixos, grava o contexto que cada agente receberia (context_for) e as notas usadas.
  --save     grava a linha de base em memory/eval/brain_retrieval_baseline.json
  --compare  compara o estado atual com a linha de base (sai com 1 se mudou)
Sem camada pessoal: as duas execucoes devem ser identicas (etapa 1 sem regressao).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "memory" / "eval" / "brain_retrieval_baseline.json"

# Pedidos genericos: nada pessoal aqui (repositorio publico)
CASES = [
    ("MAESTRO", "abrir o bloco de notas e escrever uma lista de compras"),
    ("DESKTOP", "abrir as configuracoes de som do windows"),
    ("DESKTOP", "fechar o aplicativo da calculadora"),
    ("WEB", "pesquisar a previsao do tempo no navegador"),
    ("WEB", "abrir o youtube e buscar musica para estudar"),
    ("CODE", "criar um site estatico de portfolio com tres paginas"),
    ("CODE", "corrigir o erro no script python que le planilhas"),
    ("DATA", "gerar um grafico de vendas a partir de uma planilha excel"),
    ("FILE", "organizar a pasta downloads por tipo de arquivo"),
    ("FILE", "renomear as fotos da pasta imagens com a data"),
]


def snapshot(personal=None):
    from core.brain import Brain
    from core.config import get_config
    cfg = get_config()
    brain = Brain(cfg.get("brain.vault_path", "../vault"), **({"personal_path": personal} if personal else {}))
    out = []
    for agent, task in CASES:
        for compact in (False, True):
            ctx = brain.context_for(agent, task, compact=compact)
            out.append({"agent": agent, "task": task, "compact": compact,
                        "sources": brain.last_sources.get(agent, []), "chars": len(ctx),
                        "context": ctx})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    now = snapshot()
    if args.save or not OUT.exists():
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(now, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"linha de base: {len(now)} casos, {sum(1 for c in now if c['sources'])} com fontes")
        return 0
    base = json.loads(OUT.read_text(encoding="utf-8"))
    diffs = [(b["agent"], b["task"], b["compact"]) for b, c in zip(base, now)
             if b["context"] != c["context"] or b["sources"] != c["sources"]]
    if len(base) != len(now):
        diffs.append(("*", "quantidade de casos mudou", None))
    for d in diffs:
        print("MUDOU:", d)
    print(f"comparacao: {len(now) - len(diffs)}/{len(now)} identicos")
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
