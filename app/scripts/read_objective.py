"""Executa uma leitura FILE pelo runtime compartilhado, sem navegador ou modelo."""
import argparse
from contextlib import nullcontext
from pathlib import Path, PureWindowsPath
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.action_policy import authorize
from core.automation_files import FileActions
from core.paths import is_network_path
from core.run_context import RunContext
from core.read_checkpoint import open_read_checkpoint, read_finished, read_started
from core.task_ledger import LedgerUnavailable, get_ledger
from core.verification import bounded_content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="pasta local autorizada")
    parser.add_argument("names", nargs="+", help="nomes literais dos arquivos procurados")
    parser.add_argument("--task-id", help="registra um lote retomável localmente")
    parser.add_argument("--resume", action="store_true", help="continua um lote de leituras interrompido")
    args = parser.parse_args()
    root = Path(args.root)
    if (is_network_path(args.root) or not root.is_absolute() or len(args.names) > 12
            or len(set(args.names)) != len(args.names) or any(
                PureWindowsPath(name).name != name or PureWindowsPath(name).is_reserved()
                or name.endswith((".", " ")) for name in args.names)):
        parser.error("informe uma pasta local absoluta e um nome simples de arquivo")
    if args.resume and not args.task_id:
        parser.error("--resume exige --task-id")
    if not root.is_dir():
        parser.error("pasta autorizada inexistente")
    goal = "Leia " + " e ".join(args.names) + " na pasta autorizada"
    run = RunContext(goal, lambda: False, monotonic() + 30, max_actions=3 * len(args.names), file_roots=(str(root),))

    def allowed(action, params):
        return not authorize("FILE", goal, action, params, file_scope=run.file_roots)

    def dispatch(params):
        if not allowed("read_file", params):
            return {"success": False, "status": "rejected", "result": "Leitura fora da pasta autorizada."}
        result = FileActions()._read_file(params)
        return result if isinstance(result, dict) else {"success": False, "result": result}

    ledger = get_ledger() if args.task_id else None
    permit = lambda path: allowed("read_file", {"path": path})
    try:
        checkpoint = open_read_checkpoint(ledger, args.task_id, root, args.names, permit, resume=args.resume) \
            if ledger else nullcontext(0)
        with checkpoint as completed:
            for index, name in enumerate(args.names[completed:], completed + 1):
                path = str(root / name)
                if ledger:
                    read_started(ledger, args.task_id, index)
                digest = bounded_content(path) if ledger and permit(path) else None
                result = run.execute_step("FILE", "read_file", {"path": path}, dispatch,
                                          authorize_patch=lambda p: allowed("read_file", p),
                                          allow_directory=lambda p: allowed("list_files", {"path": p}))
                verified = result.get("verified") is True
                if ledger:
                    after = bounded_content(path) if digest is not None and permit(path) else None
                    read_finished(ledger, args.task_id, index, result, digest if digest == after else None)
                print(result["result"])
                if not verified:
                    if ledger:
                        ledger._write(args.task_id, {"type": "finished", "state": "failed"}, required=True)
                    return 1
            if ledger:
                ledger._write(args.task_id, {"type": "finished", "state": "completed", "verified": True}, required=True)
            return 0
    except (LedgerUnavailable, OSError):
        print("Não foi possível abrir ou confirmar o checkpoint.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
