"""Métricas contínuas dos últimos pedidos (sem custo, sem rede): python app/scripts/quality_metrics.py [--last 200]

Lê só os registros locais que o app já grava. Imprime números, nunca o texto dos pedidos.
Use antes e depois de uma mudança no Maestro, no validador ou nos agentes para ver se a qualidade real mudou.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.quality_metrics import snapshot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--last", type=int, default=200, help="quantos pedidos recentes (padrão 200)")
    args = parser.parse_args()
    print(json.dumps(snapshot(max(1, args.last)), ensure_ascii=False, indent=1))
