"""Confere o resultado de uma cópia interrompida, sem executá-la novamente."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.task_ledger import LedgerUnavailable, get_ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("step", type=int, nargs="?")
    parser.add_argument("destination", nargs="?", help="caminho absoluto de destino da cópia")
    parser.add_argument("--inspect", action="store_true", help="mostra estado e etapas conhecidas")
    args = parser.parse_args()
    if args.inspect:
        if args.step is not None or args.destination is not None:
            parser.error("--inspect recebe apenas o ID da tarefa")
        task = get_ledger().load(args.task_id)
        if task["id"] != args.task_id:
            print("Tarefa não encontrada.")
            return 1
        keys = ("steps_done", "steps_failed", "steps_uncertain")
        print(json.dumps({"id": task["id"], "state": task["state"], "checkpoint": task["checkpoint"],
                          **{key: [{name: step[name] for name in ("step", "action", "status", "verified") if name in step}
                                   for step in task[key]] for key in keys}}, ensure_ascii=False))
        return 0
    if args.step is None or args.destination is None:
        parser.error("informe etapa e destino absoluto para reconciliar")
    try:
        if get_ledger().reconcile_copy(args.task_id, args.step, args.destination):
            print("Conteúdo no destino conferido. Etapa registrada como reconciliada.")
            return 0
    except LedgerUnavailable:
        print("A reconciliação não pôde ser gravada.")
        return 1
    print("Evidência insuficiente. Etapa preservada para conferência.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
