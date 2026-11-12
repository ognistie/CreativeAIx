"""
Andamento real das tarefas, para responder "como esta?" sem executar nada.

A resposta vem do registro duravel (core/task_ledger.py) e da fila de pedidos falados, nunca
do modelo: antes, "verificar o estado do site" foi tratado como pedido e criou um projeto novo,
e a voz dizia "to checando" sem saber de nada.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

_STATUS = re.compile(
    r"\b(?:como (?:esta|ta|anda|vai|ficou)|qual (?:e |eh )?o (?:status|andamento|estado)|em que pe|"
    r"(?:ja )?(?:terminou|acabou|concluiu|ficou pronto)|(?:esta|ta) pronto|andamento|"
    r"verific\w* (?:o |como (?:esta|ta) o )?(?:estado|status|andamento)|"
    r"(?:informa\w*|diz\w*|me fala\w*) (?:o )?(?:status|andamento|estado)|"
    r"o que (?:voce )?(?:ta|esta) fazendo|ainda (?:ta|esta) (?:fazendo|rodando|executando)|deu certo)\b")
# Pedido de fazer algo nunca e pergunta de andamento ("abrir a pagina de status do servidor")
_ACTION = re.compile(r"^(?:abr[aei]\w*|cri[ae]\w*|faz\w*|faca|escrev\w*|mand[ae]\w*|envi[ae]\w*|pesquis\w*|"
                     r"procur\w*|busc\w*|organiz\w*|apag\w*|exclu\w*|instal\w*|baix\w*|toc[ae]\w*|coloc\w*)\b")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def is_status_question(text: str) -> bool:
    n = _norm(text)
    if not n or _ACTION.match(n) or len(n.split()) > 22:
        return False
    return bool(_STATUS.search(n))


def _goal(task: dict) -> str:
    goal = re.sub(r"\s+", " ", task.get("goal") or "").strip()
    goal = re.sub(r"\s+—\s+resposta à pergunta.*$", "", goal)
    return goal[:90]


def _last_result(task: dict) -> str:
    for ev in reversed(task.get("evidence") or []):
        text = re.sub(r"^[✅❌⛔]\s*", "", str(ev.get("result") or "")).split("\n")[0].strip()
        if text:
            return text[:140]
    return ""


def describe(ledger=None, running: Optional[str] = None, queued: Optional[list] = None,
             exclude: Optional[str] = None) -> str:
    """Frase curta com o que esta rodando, o que esta na fila e o ultimo resultado.
    exclude: a propria pergunta de andamento, quando ela ja virou um registro."""
    from core.task_ledger import owner_active
    if ledger is None:
        from core.task_ledger import get_ledger
        ledger = get_ledger()
    tasks = []
    for task_id in ledger.task_ids()[-12:]:
        if task_id == exclude:
            continue
        try:
            t = ledger.load(task_id)
        except Exception:
            continue
        if t.get("dry_run") or not t.get("goal"):
            continue
        if t.get("state") == "running":
            active = owner_active(t)
            if active is False:
                t = {**t, "state": "interrupted"}
            elif active is None:
                t = {**t, "state": "unknown"}
        tasks.append(t)
    active = next((t for t in reversed(tasks) if t.get("state") == "running"), None)
    parts = []
    if active is not None:
        done = len(active.get("steps_done") or [])
        last = _last_result(active)
        parts.append(f"Estou fazendo agora: {_goal(active)}" + (f" ({done} passo(s) concluído(s))" if done else "")
                     + (f". Último passo: {last}" if last else ""))
    elif running:
        parts.append(f"Estou começando: {running[:90]}")
    if queued:
        parts.append(f"Na fila: {len(queued)} pedido(s), o próximo é \"{str(queued[0])[:70]}\"")
    if not active and not running and tasks and tasks[-1].get("state") == "unknown":
        parts.append(f"Não consegui confirmar se ainda está em execução: {_goal(tasks[-1])}")
    finished = [t for t in tasks if t.get("state") in ("completed", "failed", "interrupted", "cancelled")]
    if finished and active is None:
        t = finished[-1]
        word = {"completed": "Terminei", "failed": "Não consegui concluir",
                "interrupted": "Foi interrompido", "cancelled": "Foi cancelado"}.get(t["state"], "Encerrado")
        result = _last_result(t)
        err = t.get("error") or ""
        if err == "clarification_required":
            result = "fiquei esperando uma resposta sua"
        parts.append(f"{word}: {_goal(t)}" + (f" — {result}" if result else ""))
    if not parts:
        return "Não há nenhuma tarefa rodando nem na fila agora."
    return ". ".join(p.rstrip(".") for p in parts) + "."
