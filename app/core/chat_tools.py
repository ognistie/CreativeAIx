"""
Ferramentas da conversa (agents/chat_agent.py): SO LEITURA, executadas aqui, nunca pelo modelo.

O modelo pede "listar_pasta", "ler_arquivo", "buscar_arquivos" ou consultas ao Cerebro; este modulo decide se
o caminho pode ser lido e devolve texto curto. Nada aqui grava, move, apaga, abre programa ou acessa a rede.
Agir no computador e outra ferramenta (executar_no_computador), que devolve o pedido ao fluxo com politicas
(Maestro -> plan_validator -> action_policy -> action_risk).

Escopo de leitura (ReadScope)
- Raizes: a pasta do usuario (~) e as pastas que a PESSOA citou na conversa ou anexou. Caminho vindo do
  modelo e dado nao confiavel: e resolvido (sem "..", sem atalho simbolico para fora) e conferido contra as
  raizes antes de qualquer acesso.
- Sempre recusado: caminho de rede (\\\\servidor: so tocar nele envia o hash NTLM), pasta do Windows,
  AppData (perfis de navegador, tokens), pastas de chaves (.ssh, .aws...) e arquivos de segredo (.env, .pem,
  chaves). Texto devolvido passa por um filtro que mascara chaves e senhas.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

MAX_LIST_ENTRIES = 300
MAX_READ_LINES = 800
MAX_READ_CHARS = 60_000
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_SEARCH_FILES = 6000
MAX_SEARCH_HITS = 60
MAX_GREP_BYTES = 1024 * 1024

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache",
             ".next", "dist", "build", ".idea", ".vs", "$recycle.bin", "system volume information"}
# Pastas inteiras que guardam credenciais ou perfis (navegador, nuvem, chaves)
DENIED_DIRS = {"appdata", ".ssh", ".aws", ".azure", ".gnupg", ".kube", ".docker", ".gcloud", ".password-store",
               "$recycle.bin", "system volume information"}
_SECRET_FILE = re.compile(
    r"^(?:\.env(?:\..*)?|.*\.(?:pem|key|pfx|p12|kdbx|keystore|jks|ppk)|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|"
    r"\.npmrc|\.pypirc|\.netrc|\.git-credentials|credentials(?:\.json)?|secrets?\.(?:json|ya?ml|toml)|"
    r"login data|cookies|web data)$", re.I)
# Chaves com formato conhecido, literais entre aspas atribuidos a nomes de segredo e linhas KEY=valor.
# `token = secrets.token_hex(16)` (codigo) nao e mascarado: so valor literal.
_SECRET_TEXT = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"(?i:api[_-]?key|token|secret|password|passwd|senha)[\"']?\s*[:=]\s*[\"'][^\s\"']{8,}[\"']|"
    r"(?m:^[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*=\s*\S{8,}))")
OFFICE_EXT = (".xlsx", ".xlsm", ".docx", ".pdf")


class ToolError(Exception):
    """Erro que volta ao modelo como resultado da ferramenta (ele corrige e tenta de novo)."""


def mask_secrets(text: str) -> str:
    return _SECRET_TEXT.sub("[omitido]", text or "")


def _windows_dir() -> Optional[Path]:
    root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    return Path(root).resolve() if root else None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@dataclass
class ReadScope:
    roots: list = field(default_factory=list)

    @classmethod
    def for_conversation(cls, user_texts: Iterable[str] = (), attached: Iterable[str] = (),
                         home: Optional[str] = None, include_home: bool = True) -> "ReadScope":
        """Raizes = pasta do usuario + pastas que a pessoa citou ou anexou (nunca as que o modelo inventa).
        include_home=False: so o que a pessoa citou/anexou (escopo para abrir conteudo ativo)."""
        from core.paths import existing_prefix, extract_path, is_network_path
        roots: list[Path] = []

        def add(p: Optional[str]) -> None:
            if not p or is_network_path(p):
                return
            try:
                rp = Path(p).resolve()
            except (OSError, ValueError):
                return
            if rp.is_file():
                rp = rp.parent
            if rp.is_dir() and not any(_inside(rp, r) for r in roots):
                roots[:] = [r for r in roots if not _inside(r, rp)] + [rp]

        if include_home:
            add(home or os.path.expanduser("~"))
        for text in user_texts:
            cited = extract_path(text or "")
            if cited:
                add(existing_prefix(cited))
        for f in attached:
            add(f)
        return cls(roots)

    def check(self, raw: str, *, want: str = "any") -> Path:
        """Caminho do modelo -> Path real autorizado, ou ToolError com o motivo (acionavel)."""
        from core.paths import is_network_path, resolve_path
        if not isinstance(raw, str) or not raw.strip():
            raise ToolError("caminho vazio")
        if is_network_path(raw):
            raise ToolError("caminho de rede nao e lido (o Windows enviaria suas credenciais ao servidor)")
        try:
            path = Path(resolve_path(raw)).resolve()
        except (OSError, ValueError) as exc:
            raise ToolError(f"caminho invalido: {exc}") from None
        if not path.is_absolute():
            raise ToolError("use um caminho completo (ex.: C:\\Users\\...)")
        win = _windows_dir()
        if win and _inside(path, win):
            raise ToolError("a pasta do Windows nao e lida")
        if any(part.lower() in DENIED_DIRS for part in path.parts):
            raise ToolError("pasta protegida (credenciais/perfis); nao e lida")
        if _SECRET_FILE.match(path.name):
            raise ToolError("arquivo de segredo (chaves, senhas, .env); nao e lido")
        if not any(_inside(path, r) for r in self.roots):
            allowed = "; ".join(str(r) for r in self.roots) or "nenhuma"
            raise ToolError(f"fora das pastas liberadas ({allowed}). Peca a pessoa para citar a pasta.")
        if not path.exists():
            raise ToolError(f"nao existe: {path}")
        if want == "dir" and not path.is_dir():
            raise ToolError(f"nao e uma pasta: {path}")
        if want == "file" and not path.is_file():
            raise ToolError(f"nao e um arquivo: {path}")
        return path

    def visible(self, path: Path) -> bool:
        """Entrada que aparece numa listagem/busca (sem segredos nem pastas protegidas)."""
        name = path.name.lower()
        if name in DENIED_DIRS or _SECRET_FILE.match(path.name):
            return False
        return True


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _allowed(scope: ReadScope, path: Path) -> bool:
    """Subpasta que pode ser aberta: resolvida (juncao do Windows que aponta para fora da raiz nao entra)."""
    try:
        scope.check(str(path), want="dir")
        return True
    except ToolError:
        return False


def list_folder(scope: ReadScope, path: str, depth: int = 1) -> str:
    root = scope.check(path, want="dir")
    depth = max(1, min(3, int(depth or 1)))
    lines, count, truncated = [f"{root}"], 0, False

    def walk(folder: Path, level: int) -> None:
        nonlocal count, truncated
        try:
            entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            lines.append("  " * level + f"(sem acesso: {exc.strerror or exc})")
            return
        for entry in entries:
            if count >= MAX_LIST_ENTRIES:
                truncated = True
                return
            if not scope.visible(entry):
                continue
            count += 1
            pad = "  " * level
            if entry.is_dir():
                skipped = entry.name.lower() in SKIP_DIRS
                lines.append(f"{pad}{entry.name}/" + ("  (conteudo omitido)" if skipped else ""))
                if level < depth and not skipped and not entry.is_symlink() and _allowed(scope, entry):
                    walk(entry, level + 1)
            else:
                try:
                    size = _size(entry.stat().st_size)
                except OSError:
                    size = "?"
                lines.append(f"{pad}{entry.name}  ({size})")

    walk(root, 1)
    if count == 0:
        lines.append("  (pasta vazia)")
    if truncated:
        lines.append(f"... (parei em {MAX_LIST_ENTRIES} itens; liste uma subpasta para ver mais)")
    return "\n".join(lines)


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def read_text(scope: ReadScope, path: str, start: int = 1, max_lines: int = 400) -> str:
    target = scope.check(path, want="file")
    size = target.stat().st_size
    if target.suffix.lower() in OFFICE_EXT:
        from core.artifact_qa import read_file as read_office
        try:
            text = read_office(str(target))
        except Exception as exc:
            raise ToolError(f"nao consegui ler {target.name}: {type(exc).__name__}") from None
        if not text.strip():
            raise ToolError(f"{target.name}: formato sem leitor de texto instalado")
        return f"{target} ({_size(size)})\n" + mask_secrets(text[:MAX_READ_CHARS])
    if size > MAX_FILE_BYTES:
        raise ToolError(f"arquivo grande demais ({_size(size)}); use buscar_arquivos com um texto")
    if _is_binary(target):
        raise ToolError(f"{target.name} e binario (imagem, executavel...); nao tem texto para ler")
    start = max(1, int(start or 1))
    max_lines = max(1, min(MAX_READ_LINES, int(max_lines or 400)))
    out, chars, total = [], 0, 0
    with open(target, encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, start=1):
            total = n
            if n < start or len(out) >= max_lines or chars > MAX_READ_CHARS:
                continue
            line = line.rstrip("\n")[:2000]
            out.append(f"{n:>5}  {line}")
            chars += len(line)
    head = f"{target} ({_size(size)}, {total} linhas)"
    shown_end = start + len(out) - 1
    if total > shown_end:
        head += f" — mostrando {start}-{shown_end}; peca linha_inicial={shown_end + 1} para continuar"
    return head + "\n" + mask_secrets("\n".join(out))


def search_files(scope: ReadScope, folder: str, name: str = "", text: str = "", limit: int = 40) -> str:
    root = scope.check(folder, want="dir")
    name = (name or "").strip()
    text = (text or "").strip()
    if not name and not text:
        raise ToolError("informe 'nome' (ex.: *.py) e/ou 'texto' para buscar")
    limit = max(1, min(MAX_SEARCH_HITS, int(limit or 40)))
    pattern = name.lower() if any(c in name for c in "*?[") else f"*{name.lower()}*" if name else "*"
    needle = text.lower()
    hits, scanned = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and d.lower() not in DENIED_DIRS]
        for fname in filenames:
            scanned += 1
            if scanned > MAX_SEARCH_FILES or len(hits) >= limit:
                break
            path = Path(dirpath) / fname
            if not scope.visible(path) or not fnmatch.fnmatch(fname.lower(), pattern):
                continue
            try:
                # Cada achado passa pelo escopo: uma juncao/atalho dentro da raiz pode apontar para fora dela
                path = scope.check(str(path), want="file")
            except ToolError:
                continue
            if not needle:
                hits.append(str(path))
                continue
            try:
                if path.stat().st_size > MAX_GREP_BYTES or _is_binary(path):
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for n, line in enumerate(fh, start=1):
                        if needle in line.lower():
                            hits.append(f"{path}:{n}: {mask_secrets(line.strip()[:200])}")
                            if len(hits) >= limit:
                                break
            except OSError:
                continue
        if scanned > MAX_SEARCH_FILES or len(hits) >= limit:
            break
    if not hits:
        return f"Nada encontrado em {root}" + (" (busca parcial: pasta muito grande)" if scanned > MAX_SEARCH_FILES else "")
    tail = []
    if len(hits) >= limit:
        tail.append(f"... (mostrando {limit}; refine a busca)")
    if scanned > MAX_SEARCH_FILES:
        tail.append(f"(parei em {MAX_SEARCH_FILES} arquivos; busque numa subpasta)")
    return "\n".join(hits + tail)
