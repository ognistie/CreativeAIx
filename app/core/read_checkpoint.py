"""Checkpoint retomável de um lote FILE estritamente de leitura."""
from contextlib import contextmanager
import hashlib
import json
import os
import stat
from pathlib import Path

from core.task_ledger import LedgerUnavailable, _valid_task_id, replay
from core.verification import bounded_content, file_identity


@contextmanager
def _exclusive(ledger, task_id):
    ledger.root.mkdir(parents=True, exist_ok=True)
    path = ledger.root / f"{task_id}.lease"
    if path.is_symlink():
        raise LedgerUnavailable("Identidade do registro inválida.")
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise LedgerUnavailable("A tarefa já está em execução.") from error
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise LedgerUnavailable("A tarefa já está em execução.") from error
        yield


@contextmanager
def open_read_checkpoint(ledger, task_id: str, root: Path, names: list[str], permit, *, resume: bool):
    if not ledger.enabled or not _valid_task_id(task_id):
        raise LedgerUnavailable("Registro desativado ou identificador inválido.")
    root_identity = file_identity(str(root))
    if root_identity is None or not stat.S_ISDIR(root_identity[3]):
        raise LedgerUnavailable("Pasta autorizada indisponível.")
    binding = hashlib.sha256(json.dumps(
        [task_id, root_identity[:4], names], ensure_ascii=True).encode()).hexdigest()
    with _exclusive(ledger, task_id):
        if resume:
            events = ledger.events(task_id, strict=True)
            task = replay(events)
            plans = [event for event in events if event["type"] == "read_checkpoint"]
            if (len(plans) != 1 or plans[0].get("schema") != 1 or plans[0].get("binding") != binding
                    or task["source"] != "cli-read" or task["state"] not in ("running", "interrupted")
                    or task["steps_uncertain"] or task["steps_failed"] or task["dry_run"]
                    or any(event["type"] == "effect" for event in events)):
                raise LedgerUnavailable("O checkpoint não autoriza retomada.")
            done = [event for event in events if event["type"] == "step_finished"]
            if len(done) > len(names):
                raise LedgerUnavailable("Histórico do lote inválido.")
            for index, event in enumerate(done, 1):
                path = str(root / names[index - 1])
                digest = event.get("content")
                if (event["step"] != index or event.get("action") != "read_file"
                        or event.get("verified") is not True or not isinstance(digest, str)
                        or not permit(path) or bounded_content(path) != digest):
                    raise LedgerUnavailable("Resultado anterior indisponível ou alterado.")
            ledger._seq[task_id] = max((event.get("seq", 0) for event in events
                                        if type(event.get("seq")) is int), default=0)
        else:
            if ledger._path(task_id).exists():
                raise LedgerUnavailable("O identificador já existe.")
            ledger._write(task_id, {"type": "created", "task_id": task_id, "source": "cli-read",
                                    "pid": os.getpid()}, required=True)
            ledger._write(task_id, {"type": "read_checkpoint", "schema": 1, "binding": binding}, required=True)
            done = []
        yield len(done)


def read_started(ledger, task_id, step):
    ledger._write(task_id, {"type": "step_started", "step": step, "agent": "FILE", "action": "read_file"},
                  required=True)


def read_finished(ledger, task_id, step, result, digest):
    ledger._write(task_id, {"type": "step_finished", "step": step, "action": "read_file", "content": digest,
                            "ok": result["success"], "verified": result.get("verified") is True,
                            "status": result.get("status", "")}, required=True)
