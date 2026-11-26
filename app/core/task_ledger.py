"""
Registro duravel de tarefas: um arquivo de eventos por tarefa, gravado ANTES e DEPOIS de cada passo.

O historico (desktop/data/history.jsonl) so recebe a execucao no fim, entao uma queda perdia tudo.
Aqui cada evento vai para o disco na hora. O estado e sempre calculado a partir dos eventos.
Passo iniciado e sem fim registrado tem resultado desconhecido: pode ter tido efeito, entao
nunca e repetido as cegas. Este registro nao retoma nada sozinho.

Grava o nome dos parametros, nao os valores (mesma regra de core/action_logger.py). Telemetria comum
degrada com aviso; intenção e decisão de efeito sensível exigem gravação durável e falham fechado.

Eventos: created, plan, step_started, step_finished, step_retry, progress, note, effect, interrupted, finished
Estados: running -> completed | failed | cancelled | interrupted
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[1] / "memory" / "tasks"
KEEP_TASKS = 300
RESULT_MAX = 240
TERMINAL = ("completed", "failed", "cancelled", "interrupted")
log = logging.getLogger("task_ledger")


def _valid_task_id(task_id) -> bool:
    return isinstance(task_id, str) and 0 < len(task_id) <= 160 and all(
        c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in task_id)


def _path_binding(task_id: str, path: str) -> str:
    resolved = os.path.normcase(os.path.realpath(path))
    return hashlib.sha256(f"{task_id}\0{resolved}".encode()).hexdigest()


class LedgerUnavailable(RuntimeError):
    """Um efeito sensível não pode começar sem registro confirmado no disco."""


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:
        return True          # na duvida nao marca uma tarefa viva como interrompida


def owner_active(task: dict) -> Optional[bool]:
    """Read-only liveness check for other processes, accounting for recycled PIDs."""
    pid = task.get("pid")
    if type(pid) is not int or pid <= 0:
        return None
    import psutil
    try:
        process = psutil.Process(pid)
        started = task.get("started_at")
        # Old and new journals both have a creation timestamp, at second precision.
        return not started or process.create_time() < time.mktime(
            time.strptime(started, "%Y-%m-%dT%H:%M:%S")) + 1
    except psutil.NoSuchProcess:
        return False
    except (psutil.Error, TypeError, ValueError, OSError, OverflowError):
        return None


def replay(events: Iterable[dict]) -> dict:
    """O estado da tarefa, calculado so a partir dos eventos."""
    task = {"id": "", "state": "running", "goal": "", "steps_done": [], "steps_failed": [], "steps_uncertain": [],
            "steps_pending": [], "evidence": [], "interruptions": [], "verified": None, "pid": None, "events": 0,
            "checkpoint": None}
    open_steps: dict = {}
    planned: list = []
    for event in events:
        kind = event.get("type")
        task["events"] += 1
        if kind == "created":
            task.update(id=event.get("task_id", ""), goal=event.get("goal", ""), pid=event.get("pid"),
                        source=event.get("source", ""), dry_run=bool(event.get("dry_run")),
                        session_id=event.get("session_id"), started_at=event.get("at"))
        elif kind == "plan":
            planned = [str(step) for step in event.get("steps", [])]
        elif kind == "checkpoint":
            task["checkpoint"] = event.get("cursor")
        elif kind == "step_started":
            open_steps[event.get("step")] = {"step": event.get("step"), "action": event.get("action", ""),
                                             "description": event.get("description", ""),
                                             "params": event.get("params", [])}
        elif kind == "step_finished":
            step = open_steps.pop(event.get("step"), {"step": event.get("step"), "action": event.get("action", "")})
            done = {**step, "status": event.get("status", ""), "verified": bool(event.get("verified"))}
            if event.get("outcome"):
                done["outcome"] = event["outcome"]
            if done["status"] in ("uncertain", "partial"):
                open_steps[event.get("step")] = done
            else:
                (task["steps_done"] if event.get("ok") else task["steps_failed"]).append(done)
            if event.get("result"):
                task["evidence"].append({"step": event.get("step"), "result": event["result"],
                                         "verified": bool(event.get("verified"))})
        elif kind == "copy_reconciled":
            step = open_steps.get(event.get("step"))
            if step and step["action"] == "copy_file":
                open_steps.pop(event["step"])
                task["steps_done"].append({**step, "status": "reconciled", "verified": True, "outcome": "verified"})
        elif kind == "progress":
            task["evidence"].append({"step": event.get("step"), "result": event.get("message", ""), "verified": False})
        elif kind == "note" and event.get("kind") == "interruption":
            task["interruptions"].append({"at": event.get("at"), "reason": event.get("reason", "")})
        elif kind == "interrupted":
            task["state"] = "interrupted"
            task["interruptions"].append({"at": event.get("at"), "reason": event.get("reason", "")})
        elif kind == "finished":
            task.update(state=event.get("state", "failed"), verified=event.get("verified"),
                        error=event.get("error"), ended_at=event.get("at"))
    task["steps_uncertain"] = list(open_steps.values())
    started = len(task["steps_done"]) + len(task["steps_failed"]) + len(open_steps)
    task["steps_pending"] = planned[started:] if task["state"] == "running" or task["state"] == "interrupted" else []
    return task


class TaskLedger:
    def __init__(self, root: Optional[Path] = None, enabled: bool = True):
        self.root = Path(root or ROOT)
        self.enabled = enabled
        self._lock = threading.Lock()
        self._seq: dict = {}

    def _path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.jsonl"

    def _write(self, task_id: str, event: dict, *, required: bool = False) -> None:
        """Evento inteiro em uma linha, ja no disco ao retornar. Cada evento e independente: uma linha
        cortada por uma queda se perde sozinha, sem levar as anteriores."""
        if (not self.enabled and not required) or not task_id:
            if required:
                raise LedgerUnavailable("Tarefa ausente no registro durável.")
            return
        if not _valid_task_id(task_id):
            if required:
                raise LedgerUnavailable("Identificador de tarefa inválido.")
            log.warning("identificador de tarefa inválido")
            return
        try:
            with self._lock:
                seq = self._seq.get(task_id, 0) + 1
                self._seq[task_id] = seq
                self.root.mkdir(parents=True, exist_ok=True)
                line = json.dumps({"seq": seq, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}, ensure_ascii=False)
                with self._path(task_id).open("a", encoding="utf-8") as stream:
                    stream.write(line + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
        except (OSError, TypeError, ValueError) as error:
            log.warning("registro de tarefa falhou: %s", type(error).__name__)
            if required:
                raise LedgerUnavailable("Não foi possível persistir o efeito sensível.") from error

    def effect(self, task_id: str, action_id: str, phase: str, *, agent: str,
               action: str, kind: str, session_id: str = "", policy: str = "") -> None:
        """Intenção e decisão antes do efeito; só metadados, sem conteúdo nem token de aprovação.

        Ao contrário da telemetria comum, falha de flush/fsync impede a autorização.
        Uma decisão permitida ainda não comprova que o efeito aconteceu.
        """
        if phase not in ("intent", "approved", "declined", "cancelled"):
            raise ValueError("Fase de efeito inválida.")
        self._write(task_id, {"type": "effect", "action_id": action_id, "phase": phase,
                              "agent": agent, "action": action, "kind": kind,
                              "session_id": session_id, "policy": policy}, required=True)

    # ── gravar ────────────────────────────────────────────────────
    def begin(self, task_id: str, goal: str, *, source: str = "", dry_run: bool = False, session_id=None) -> str:
        self._write(task_id, {"type": "created", "task_id": task_id, "goal": goal, "source": source, "dry_run": dry_run,
                              "session_id": session_id, "pid": os.getpid()})
        return task_id

    def plan(self, task_id: str, steps: list) -> None:
        self._write(task_id, {"type": "plan", "steps": [str(step)[:160] for step in steps]})

    def step_started(self, task_id: str, step: int, agent: str, action: str, params, description: str = "") -> None:
        """Vem ANTES da acao: sem isto, uma queda no meio nao deixaria rastro do que pode ter acontecido."""
        keys = sorted(params) if isinstance(params, dict) else []
        self._write(task_id, {"type": "step_started", "step": step, "agent": agent, "action": action, "params": keys,
                              "description": str(description)[:160]})

    def step_retry(self, task_id: str, step: int, action: str) -> None:
        self._write(task_id, {"type": "step_retry", "step": step, "action": action})

    def copy_intent(self, task_id: str, step: int, source: str, destination: str) -> None:
        """Persiste compromisso de conteúdo e destino antes de copiar, sem nomes de arquivo."""
        from core.verification import bounded_content
        if not self.enabled:
            return
        digest = bounded_content(source)
        if digest is not None:
            self._write(task_id, {"type": "copy_intent", "step": step,
                                  "destination": _path_binding(task_id, destination), "content": digest})

    def reconcile_copy(self, task_id: str, step: int, destination: str) -> bool:
        """Prova o estado final de uma cópia incerta. O estado global e as etapas restantes são preservados."""
        from core.verification import bounded_content
        if not self.enabled or not _valid_task_id(task_id):
            return False
        if type(step) is not int or step <= 0 or not os.path.isabs(destination):
            return False
        try:
            events = self.events(task_id, strict=True)
        except LedgerUnavailable:
            return False
        task = replay(events)
        if task["state"] not in ("interrupted", "failed", "cancelled") or task.get("dry_run"):
            return False
        if not any(row["step"] == step and row["action"] == "copy_file" for row in task["steps_uncertain"]):
            return False
        candidates = [row for row in events if row.get("type") == "copy_intent" and row.get("step") == step]
        if len(candidates) != 1:
            return False
        receipt = candidates[0]
        if _path_binding(task_id, destination) != receipt.get("destination"):
            return False
        expected = receipt.get("content")
        if not isinstance(expected, str) or bounded_content(destination) != expected or (
                _path_binding(task_id, destination) != receipt["destination"]):
            return False
        self._write(task_id, {"type": "copy_reconciled", "step": step}, required=True)
        return True

    def step_finished(self, task_id: str, step: int, action: str, result: dict) -> None:
        self._write(task_id, {"type": "step_finished", "step": step, "action": action,
                              "ok": bool(result.get("success")), "status": result.get("status", ""),
                              "outcome": result.get("outcome"),
                              "verified": result.get("verified") is True, "result": str(result.get("result", ""))[:RESULT_MAX]})

    def progress(self, task_id: str, step: int, message: str) -> None:
        self._write(task_id, {"type": "progress", "step": step, "message": str(message)[:RESULT_MAX]})

    def checkpoint(self, task_id: str, subtask: int, dependency: Optional[int], state: str) -> None:
        """Cursor observável. Recuperação mantém passos incertos e nunca executa ações."""
        self._write(task_id, {"type": "checkpoint", "cursor": {
            "schema": 1, "subtask": subtask, "dependency": dependency, "state": state,
        }})

    def note(self, task_id: str, kind: str, **data) -> None:
        self._write(task_id, {"type": "note", "kind": kind, **data})

    def finish(self, task_id: str, state: str, *, verified: bool = False, error=None) -> None:
        self._write(task_id, {"type": "finished", "state": state if state in TERMINAL else "failed",
                              "verified": verified, "error": str(error)[:RESULT_MAX] if error else None})
        with self._lock:
            self._seq.pop(task_id, None)

    # ── ler ───────────────────────────────────────────────────────
    def events(self, task_id: str, *, strict: bool = False) -> list:
        rows = []
        if not _valid_task_id(task_id):
            return rows
        try:
            path = self._path(task_id)
            if path.is_symlink():
                return rows
            for line in path.read_text(encoding="utf-8", errors="strict" if strict else "replace").splitlines():
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                        raise ValueError("Evento sem tipo.")
                    if event["type"] in ("step_started", "step_finished", "copy_intent", "copy_reconciled") and (
                            type(event.get("step")) is not int or event["step"] <= 0):
                        raise ValueError("Etapa inválida.")
                    rows.append(event)
                except ValueError:
                    if strict:
                        raise LedgerUnavailable("Registro corrompido. Reconciliação bloqueada.") from None
                    continue         # linha cortada por uma queda: as demais continuam valendo
        except (OSError, UnicodeError):
            if strict:
                raise LedgerUnavailable("Não foi possível verificar o registro.") from None
        return rows

    def load(self, task_id: str) -> dict:
        return replay(self.events(task_id))

    def task_ids(self) -> list:
        try:
            files = sorted(self.root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        except OSError:
            return []
        return [path.stem for path in files]

    def recover(self) -> list:
        """Ao abrir o app: tarefa sem fim cujo processo morreu fica marcada como interrompida. So isso:
        nada e executado de novo. -> as tarefas que precisam da atencao da pessoa."""
        if not self.enabled:
            return []
        found = []
        for task_id in self.task_ids():
            task = self.load(task_id)
            if task["state"] != "running" or not task["id"]:
                continue
            if task["pid"] is not None and int(task["pid"]) != os.getpid() and _pid_alive(task["pid"]):
                continue
            self._write(task_id, {"type": "interrupted", "reason": "o app fechou antes de a tarefa terminar"})
            found.append(self.load(task_id))
        self.prune()
        return found

    def prune(self, keep: int = KEEP_TASKS) -> int:
        ids = self.task_ids()
        removed = 0
        for task_id in ids[:max(0, len(ids) - keep)]:
            try:
                self._path(task_id).unlink()
                removed += 1
            except OSError:
                pass
        return removed


_ledger: Optional[TaskLedger] = None


def get_ledger() -> TaskLedger:
    global _ledger
    if _ledger is None:
        try:
            from core.config import get_config
            enabled = bool(get_config().get("execution.ledger", True))
        except Exception:
            enabled = True
        _ledger = TaskLedger(enabled=enabled)
    return _ledger
