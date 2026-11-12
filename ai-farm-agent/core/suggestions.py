"""
Sugestoes dos agentes (etapa 6): ao fim de uma tarefa real, o app pode SUGERIR uma licao
(falha) ou um procedimento (sucesso sem referencia comprovada). A sugestao fica numa fila na
camada pessoal (.cerebro/sugestoes.json) e nao orienta ninguem ate o usuario aprovar.

Regras do memory_gate preservadas:
  - pendente = hipotese: nao entra no prompt;
  - aprovar = verificacao humana (verifier "human" no memory_gate): so entao vira nota;
  - licao exige a regra escrita/confirmada pelo usuario; procedimento exige o caminho;
  - simulacao (dry run) e tarefa sem passos nao geram sugestao.
Sem modelo: o texto vem do proprio registro da tarefa (com dados pessoais redigidos).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

QUEUE_FILE = "sugestoes.json"
MAX_PENDING = 40
LESSONS_NOTE = "60 Aprendizados/Sugeridas pelos agentes.md"
REFS_DIR = "30 Tarefas de referencia"


def _clean(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _key(kind: str, task: str) -> str:
    words = sorted(set(re.findall(r"[a-z0-9]{3,}", task.lower())))
    return kind + ":" + " ".join(words[:12])


class Suggestions:
    def __init__(self, personal: Optional[Path]) -> None:
        self.file = Path(personal) / ".cerebro" / QUEUE_FILE if personal else None
        self._lock = threading.Lock()

    def _load(self) -> list:
        if not self.file or not self.file.is_file():
            return []
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, items: list) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.file)

    def pending(self) -> list:
        return [s for s in self._load() if s.get("status") == "pendente"]

    def add(self, item: dict) -> Optional[dict]:
        if not self.file:
            return None
        with self._lock:
            items = self._load()
            if any(s.get("key") == item["key"] and s.get("status") in ("pendente", "recusada") for s in items):
                return None                    # ja sugerida (ou o usuario ja recusou): nao insiste
            item = {**item, "id": uuid.uuid4().hex[:10], "status": "pendente",
                    "created": time.strftime("%Y-%m-%d %H:%M")}
            items.append(item)
            pend = [s for s in items if s.get("status") == "pendente"]
            if len(pend) > MAX_PENDING:          # a mais antiga sai da fila
                oldest = pend[0]["id"]
                items = [s for s in items if s["id"] != oldest]
            self._save(items[-200:])
            return item

    def _take(self, sid: str, status: str) -> dict:
        with self._lock:
            items = self._load()
            for s in items:
                if s.get("id") == sid and s.get("status") == "pendente":
                    s["status"] = status
                    s["decided"] = time.strftime("%Y-%m-%d %H:%M")
                    self._save(items)
                    return dict(s)
        raise KeyError("sugestão não encontrada ou já decidida")

    def dismiss(self, sid: str) -> dict:
        return self._take(sid, "recusada")

    def approve(self, sid: str, store, title: str = "", body: str = "") -> dict:
        """Aprovacao humana: grava a nota na camada pessoal. title/body = o texto revisado."""
        current = next((s for s in self.pending() if s.get("id") == sid), None)
        if not current:
            raise KeyError("sugestão não encontrada ou já decidida")
        title = _clean(title or current["title"], 90)
        body = (body or current["body"]).strip()[:2000]
        if not title or not body or body == current.get("placeholder"):
            raise ValueError("escreva a regra ou o caminho antes de aprovar")
        if current["kind"] == "licao":
            text = store.read(LESSONS_NOTE) or ("---\ntipo: licoes\n---\n# Sugeridas pelos agentes\n\n"
                                                "Lições aprovadas por você a partir de tarefas reais.\n")
            text = text.rstrip() + f"\n\n> [!lesson] {title}\n> **Regra:** {_clean(body, 400)}\n> Origem: {current['created']} · aprovada por você\n"
            rel = store.write(LESSONS_NOTE, text)
        else:
            from core.brain_store import clean_rel
            name = re.sub(r"[^\w\s-]", "", title)[:70].strip() or "Procedimento"
            rel = clean_rel(f"{REFS_DIR}/{name}")
            agents = ", ".join(current.get("agents") or [])
            note = ("---\ntipo: tarefa-de-referencia\n"
                    f"tarefa: {title}\nagente: {agents}\nkeywords: {current.get('keywords', '')}\n"
                    # verificacao humana: e o "human" que o memory_gate aceita como evidencia
                    "verificado: sim\nverificador: human\nsucessos: 1\n---\n"
                    f"# {title}\n\n## Caminho\n{body}\n\nAprovado por você em {time.strftime('%Y-%m-%d')} a partir de uma tarefa real.\n")
            if store.resolve(rel):
                raise FileExistsError(rel)
            rel = store.write(rel, note)
        self._take(sid, "aprovada")
        return {"rel": rel}


def from_execution(entry: dict, records: list, has_reference: bool, redact=lambda t: t) -> Optional[dict]:
    """Sugestao a partir do resultado de uma tarefa real (ou None)."""
    if entry.get("dry_run") or not entry.get("task"):
        return None
    task = _clean(redact(entry["task"]), 160)
    agents = sorted({(s.get("agent") or "").upper() for s in entry.get("subtasks") or [] if s.get("agent")})
    words = " ".join(sorted(set(re.findall(r"[a-z0-9]{4,}", task.lower())))[:12])
    if not entry.get("success"):
        error = _clean(redact(str(entry.get("error") or "")), 220)
        if not error:
            return None
        return {"kind": "licao", "key": _key("licao", task), "title": task[:90], "agents": agents,
                "evidence": f"Falhou: {error}", "placeholder": "", "body": "",
                "hint": "Escreva a regra que evita essa falha (o que o agente deve fazer diferente)."}
    steps = [r for r in records if r.get("success")]
    if has_reference or len(steps) < 2:
        return None                            # ja existe caminho comprovado, ou nao ha caminho
    path = " → ".join(_clean(r.get("action", ""), 40) + (f" ({_clean(redact(str(r.get('description') or '')), 50)})"
                                                            if r.get("description") else "") for r in steps[:10])
    return {"kind": "procedimento", "key": _key("procedimento", task), "title": task[:90], "agents": agents,
            "keywords": words, "evidence": f"Deu certo em {len(steps)} passos.", "body": path,
            "placeholder": "", "hint": "Confira o caminho. Ao aprovar, os agentes passam a seguir este procedimento."}
