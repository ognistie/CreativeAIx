"""
BrainStore — ponto unico de acesso as notas do segundo cerebro.

Duas camadas de Markdown:
  base     o vault do repositorio (vault/): conhecimento de fabrica. A interface
           nunca altera esses arquivos (o repositorio e publico).
  pessoal  pasta do usuario, fora do repositorio (padrao: Documentos/AI Farm Agent/Cerebro).
           Vence a base: editar uma nota de fabrica grava uma copia aqui.

Remover uma nota de fabrica so a esconde (.cerebro/removidas.json); nota pessoal removida vai
para .lixeira/. "Restaurar" desfaz as duas coisas. O indice de busca (SQLite FTS5) e derivado
dos arquivos e pode ser apagado sem perda.

Sem camada pessoal, a listagem e a leitura sao identicas as do vault (sem regressao).
Conteudo das notas e DADO: nada aqui amplia permissoes de agente.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Iterator, Optional

logger = logging.getLogger("brain_store")

META = ".cerebro"
TRASH = ".lixeira"
REMOVED_FILE = "removidas.json"
INDEX_FILE = "indice.sqlite"
MAX_NOTE_CHARS = 400_000
_LINK = re.compile(r"\[\[([^\[\]|#^]+)(?:#[^\[\]|]*)?(?:\|([^\[\]]*))?\]\]")
_BAD_NAME = re.compile(r'[<>:"|?*\x00-\x1f]')


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def _hidden(rel: str) -> bool:
    return any(part.startswith(".") for part in PurePosixPath(rel).parts)


def clean_rel(rel: str, *, note: bool = True) -> str:
    """Caminho relativo seguro ('Pasta/Nota.md'). ValueError se escapar da camada."""
    rel = unicodedata.normalize("NFC", (rel or "").replace("\\", "/").strip().strip("/"))
    parts = [p.strip() for p in rel.split("/") if p.strip()]
    if not parts or any(p in (".", "..") or p.startswith(".") or _BAD_NAME.search(p) for p in parts):
        raise ValueError(f"caminho invalido: {rel!r}")
    rel = "/".join(parts)
    if note and not rel.lower().endswith(".md"):
        rel += ".md"
    return rel


def default_personal_path() -> Path:
    try:
        from core.paths import known_folder
        docs = Path(known_folder("Documents"))
    except Exception:
        docs = Path.home() / "Documents"
    return docs / "AI Farm Agent" / "Cérebro"


def links_in(text: str) -> list[str]:
    """Alvos de [[links]] na ordem em que aparecem (sem repetir)."""
    seen = []
    for m in _LINK.finditer(text or ""):
        t = m.group(1).strip()
        if t and t not in seen:
            seen.append(t)
    return seen


def _title_of(rel: str) -> str:
    return PurePosixPath(rel).stem


class BrainStore:
    def __init__(self, base: Path, personal: Optional[Path] = None) -> None:
        self.base = Path(base).resolve()
        self.personal = Path(personal).resolve() if personal else None
        self._lock = threading.RLock()
        self._db: Optional[sqlite3.Connection] = None
        self._fts = True
        self._removed_cache: tuple = (None, frozenset())

    # ── camadas ───────────────────────────────────────────────────────
    @property
    def writable(self) -> bool:
        return self.personal is not None

    def _meta(self) -> Optional[Path]:
        return self.personal / META if self.personal else None

    def removed(self) -> frozenset:
        meta = self._meta()
        if not meta:
            return frozenset()
        f = meta / REMOVED_FILE
        try:
            stamp = f.stat().st_mtime_ns
        except OSError:
            return frozenset()
        if self._removed_cache[0] == stamp:
            return self._removed_cache[1]
        try:
            items = frozenset(str(x) for x in json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            items = frozenset()
        self._removed_cache = (stamp, items)
        return items

    def _set_removed(self, items) -> None:
        meta = self._meta()
        meta.mkdir(parents=True, exist_ok=True)
        tmp = meta / (REMOVED_FILE + ".tmp")
        tmp.write_text(json.dumps(sorted(items), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, meta / REMOVED_FILE)
        self._removed_cache = (None, frozenset())

    def _inside(self, root: Path, rel: str) -> Optional[Path]:
        p = (root / rel).resolve()
        if root not in p.parents:
            return None
        return p

    def resolve(self, rel: str) -> Optional[Path]:
        """Arquivo que vale para `rel`: pessoal, senao base; None se removido ou inexistente."""
        rel = (rel or "").replace("\\", "/")
        if self.personal:
            p = self._inside(self.personal, rel)
            if p and p.is_file() and not _hidden(rel):
                return p
            if rel in self.removed():
                return None
        p = self._inside(self.base, rel)
        return p if p and p.is_file() else None

    def layer_of(self, rel: str) -> str:
        """'pessoal' (so existe la), 'editada' (copia pessoal de uma nota de fabrica), 'base'."""
        in_base = bool(self._inside(self.base, rel) and (self.base / rel).is_file())
        in_personal = bool(self.personal and (self.personal / rel).is_file())
        if in_personal:
            return "editada" if in_base else "pessoal"
        return "base"

    def files(self, folder: str = "", recursive: bool = True) -> Iterator[tuple[str, Path]]:
        """(rel, arquivo) das notas .md de `folder`. Ordem da base preservada (mesmo ranking de
        antes); notas so pessoais vem depois. Pastas ocultas (.obsidian, .cerebro) ficam de fora."""
        folder = (folder or "").strip("/")
        pattern = "*.md"
        seen = set()
        removed = self.removed()

        def walk(root: Path):
            start = root / folder if folder else root
            if not start.is_dir():
                return
            it = start.rglob(pattern) if recursive else start.glob(pattern)
            for f in it:
                rel = f.relative_to(root).as_posix()
                if not _hidden(rel):
                    yield rel, f

        for rel, f in walk(self.base):
            if self.personal:
                if rel in removed and not (self.personal / rel).is_file():
                    continue
                own = self.personal / rel
                if own.is_file():
                    f = own
            seen.add(rel)
            yield rel, f
        if self.personal:
            for rel, f in walk(self.personal):
                if rel not in seen:
                    yield rel, f

    def read(self, rel: str) -> str:
        p = self.resolve(rel)
        if not p:
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    # ── listagem para a interface ─────────────────────────────────────
    def notes(self) -> list[dict]:
        out = []
        for rel, f in self.files():
            try:
                st = f.stat()
            except OSError:
                continue
            folder = str(PurePosixPath(rel).parent)
            out.append({"rel": rel, "title": _title_of(rel), "folder": "" if folder == "." else folder,
                        "layer": self.layer_of(rel), "modified": st.st_mtime, "size": st.st_size})
        out.sort(key=lambda n: (n["folder"].lower(), n["title"].lower()))
        return out

    def folders(self) -> list[str]:
        found = set()
        for root in (self.base, self.personal):
            if not root or not root.is_dir():
                continue
            for d in root.rglob("*"):
                if d.is_dir():
                    rel = d.relative_to(root).as_posix()
                    if not _hidden(rel):
                        found.add(rel)
        return sorted(found, key=str.lower)

    def _by_title(self) -> dict:
        index = {}
        for rel, _ in self.files():
            index.setdefault(_fold(_title_of(rel)), rel)
            index.setdefault(_fold(rel[:-3]), rel)
        return index

    def resolve_link(self, target: str, index: Optional[dict] = None) -> Optional[str]:
        index = index if index is not None else self._by_title()
        t = _fold(target.strip())
        return index.get(t) or index.get(_fold(PurePosixPath(t).name))

    def links(self, rel: str) -> list[dict]:
        index = self._by_title()
        return [{"target": t, "rel": self.resolve_link(t, index)} for t in links_in(self.read(rel))]

    def backlinks(self, rel: str) -> list[dict]:
        index = self._by_title()
        out = []
        for other, f in self.files():
            if other == rel:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if any(self.resolve_link(t, index) == rel for t in links_in(text)):
                out.append({"rel": other, "title": _title_of(other)})
        return out

    def graph(self) -> dict:
        index = self._by_title()
        nodes, edges = [], []
        for rel, f in self.files():
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            nodes.append({"id": rel, "title": _title_of(rel), "folder": str(PurePosixPath(rel).parent)})
            for t in links_in(text):
                to = self.resolve_link(t, index)
                if to and to != rel:
                    edges.append({"from": rel, "to": to})
        return {"nodes": nodes, "edges": edges}

    # ── escrita (so na camada pessoal) ────────────────────────────────
    def _need_personal(self) -> Path:
        if not self.personal:
            raise PermissionError("camada pessoal indisponivel")
        return self.personal

    def write(self, rel: str, text: str) -> str:
        root = self._need_personal()
        rel = clean_rel(rel)
        if len(text or "") > MAX_NOTE_CHARS:
            raise ValueError("nota grande demais")
        p = self._inside(root, rel)
        if not p:
            raise ValueError("caminho fora do cerebro")
        with self._lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(text or "", encoding="utf-8")
            os.replace(tmp, p)
            removed = set(self.removed())
            if rel in removed:
                removed.discard(rel)
                self._set_removed(removed)
        return rel

    def create(self, rel: str, text: str = "") -> str:
        rel = clean_rel(rel)
        if self.resolve(rel):
            raise FileExistsError(rel)
        if not text:
            text = f"# {_title_of(rel)}\n\n"
        return self.write(rel, text)

    def create_folder(self, rel: str) -> str:
        root = self._need_personal()
        rel = clean_rel(rel, note=False)
        p = self._inside(root, rel)
        if not p:
            raise ValueError("caminho fora do cerebro")
        p.mkdir(parents=True, exist_ok=True)
        return rel

    def _to_trash(self, p: Path, rel: str) -> None:
        dest = self.personal / TRASH / f"{time.strftime('%Y%m%d-%H%M%S')}" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))

    def delete(self, rel: str) -> dict:
        """Nota some da lista. Copia pessoal vai para a lixeira; a de fabrica fica oculta."""
        root = self._need_personal()
        rel = clean_rel(rel)
        with self._lock:
            own = self._inside(root, rel)
            moved = False
            if own and own.is_file():
                self._to_trash(own, rel)
                moved = True
            hidden = False
            if (self.base / rel).is_file():
                removed = set(self.removed())
                removed.add(rel)
                self._set_removed(removed)
                hidden = True
            if not moved and not hidden:
                raise FileNotFoundError(rel)
        return {"rel": rel, "trash": moved, "hidden": hidden}

    def restore(self, rel: str) -> dict:
        """Volta ao original de fabrica: tira da lista de ocultas e descarta a copia pessoal."""
        root = self._need_personal()
        rel = clean_rel(rel)
        if not (self.base / rel).is_file():
            raise FileNotFoundError("so notas de fabrica tem original")
        with self._lock:
            removed = set(self.removed())
            if rel in removed:
                removed.discard(rel)
                self._set_removed(removed)
            own = self._inside(root, rel)
            if own and own.is_file():
                self._to_trash(own, rel)
        return {"rel": rel}

    def rename(self, old: str, new: str, update_links: bool = True) -> dict:
        root = self._need_personal()
        old, new = clean_rel(old), clean_rel(new)
        if old == new:
            return {"rel": new, "links": 0}
        text = self.read(old)
        if not self.resolve(old):
            raise FileNotFoundError(old)
        if self.resolve(new):
            raise FileExistsError(new)
        self.write(new, text)
        own = self._inside(root, old)
        with self._lock:
            if own and own.is_file():
                own.unlink()
            if (self.base / old).is_file():
                removed = set(self.removed())
                removed.add(old)
                self._set_removed(removed)
        changed = self._relink(_title_of(old), _title_of(new)) if update_links else 0
        return {"rel": new, "links": changed}

    def _relink(self, old_title: str, new_title: str) -> int:
        if _fold(old_title) == _fold(new_title):
            return 0
        pat = re.compile(r"\[\[" + re.escape(old_title) + r"((?:#[^\[\]|]*)?(?:\|[^\[\]]*)?)\]\]", re.IGNORECASE)
        changed = 0
        for rel, f in list(self.files()):
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            new_text = pat.sub(lambda m: f"[[{new_title}{m.group(1)}]]", text)
            if new_text != text:
                self.write(rel, new_text)
                changed += 1
        return changed

    # ── busca (SQLite FTS5) ───────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        if self._db is not None:
            return self._db
        meta = self._meta()
        target = ":memory:"
        if meta is not None and self.personal.is_dir():
            meta.mkdir(parents=True, exist_ok=True)
            target = str(meta / INDEX_FILE)
        db = sqlite3.connect(target, check_same_thread=False)
        try:
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS notas USING fts5(rel UNINDEXED, titulo, corpo, "
                       "tokenize='unicode61 remove_diacritics 2')")
        except sqlite3.OperationalError:
            self._fts = False
            db.execute("CREATE TABLE IF NOT EXISTS notas (rel TEXT, titulo TEXT, corpo TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS carimbo (rel TEXT PRIMARY KEY, marca TEXT)")
        self._db = db
        return db

    def refresh_index(self) -> int:
        """Atualiza so o que mudou (data/tamanho/camada). Devolve quantas notas reindexou."""
        with self._lock:
            db = self._conn()
            known = dict(db.execute("SELECT rel, marca FROM carimbo"))
            current = {}
            for rel, f in self.files():
                try:
                    st = f.stat()
                except OSError:
                    continue
                current[rel] = (f, f"{st.st_mtime_ns}:{st.st_size}:{f}")
            changed = 0
            for rel in set(known) - set(current):
                db.execute("DELETE FROM notas WHERE rel = ?", (rel,))
                db.execute("DELETE FROM carimbo WHERE rel = ?", (rel,))
                changed += 1
            for rel, (f, mark) in current.items():
                if known.get(rel) == mark:
                    continue
                try:
                    body = f.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    body = ""
                db.execute("DELETE FROM notas WHERE rel = ?", (rel,))
                db.execute("INSERT INTO notas (rel, titulo, corpo) VALUES (?, ?, ?)", (rel, _title_of(rel), body))
                db.execute("INSERT OR REPLACE INTO carimbo (rel, marca) VALUES (?, ?)", (rel, mark))
                changed += 1
            db.commit()
            return changed

    def search(self, query: str, limit: int = 30) -> list[dict]:
        words = [w for w in re.findall(r"\w+", _fold(query)) if len(w) >= 2][:8]
        if not words:
            return []
        self.refresh_index()
        with self._lock:
            db = self._conn()
            if not self._fts:
                rows = db.execute("SELECT rel, titulo, substr(corpo, 1, 160) FROM notas").fetchall()
                hits = [r for r in rows if all(w in _fold(r[1] + " " + r[2]) for w in words)]
                return [{"rel": r[0], "title": r[1], "snippet": r[2], "layer": self.layer_of(r[0])}
                        for r in hits[:limit]]
            out = []
            for joiner in (" ", " OR "):
                q = joiner.join(f'"{w}"*' for w in words)
                try:
                    rows = db.execute(
                        "SELECT rel, titulo, snippet(notas, 2, '«', '»', '…', 14) FROM notas "
                        "WHERE notas MATCH ? ORDER BY bm25(notas, 0.0, 6.0, 1.0) LIMIT ?", (q, limit)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                if rows:
                    out = [{"rel": r[0], "title": r[1], "snippet": re.sub(r"\s+", " ", r[2]).strip(),
                            "layer": self.layer_of(r[0])} for r in rows]
                    break
            return out

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None
