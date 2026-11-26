"""Chaves de API de provedores guardadas protegidas pelo Windows (DPAPI, escopo do usuário).

A chave digitada nas Configurações nunca vai para o config.yaml, para o git ou para logs. O arquivo
memory/provider_keys.json guarda só o blob cifrado pelo DPAPI (CryptProtectData): outro usuário do
Windows ou outra máquina não decifra. Não é um cofre contra malware rodando como o próprio usuário.
Fora do Windows o armazenamento fica indisponível e a chave continua podendo vir do ambiente (.env).
"""
from __future__ import annotations

import base64
import json
import re
import sys
import threading
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "memory" / "provider_keys.json"
_NAME = re.compile(r"[a-z][a-z0-9_-]{1,31}")
_KEY = re.compile(r"[\x21-\x7e]{8,512}")          # ASCII visivel, sem espacos nem quebras
_ENTROPY = b"creative-aix/provider-key/v1"
_lock = threading.Lock()


class SecretStoreError(RuntimeError):
    """Mensagem segura para a interface: nunca contém a chave."""


def available() -> bool:
    return sys.platform == "win32"


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer, DATA_BLOB


def _crypt(data: bytes, protect: bool) -> bytes:
    import ctypes
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    source, _keep, DATA_BLOB = _blob(data)
    entropy, _keep2, _ = _blob(_ENTROPY)
    out = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(source), None, ctypes.byref(entropy), None, None, CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out))
    if not ok:
        raise SecretStoreError("O Windows não conseguiu proteger a chave." if protect
                               else "A chave guardada não pôde ser lida neste usuário do Windows.")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    from core.atomic_io import replace_file
    replace_file(tmp, path)


def _check_name(provider: str) -> str:
    if not isinstance(provider, str) or not _NAME.fullmatch(provider):
        raise SecretStoreError("Provedor inválido.")
    return provider


def save(provider: str, key: str, path: Path = PATH) -> None:
    _check_name(provider)
    key = (key or "").strip() if isinstance(key, str) else ""
    if not _KEY.fullmatch(key):
        raise SecretStoreError("Chave inválida: cole a chave inteira, sem espaços.")
    if not available():
        raise SecretStoreError("Guardar chaves pelo app exige Windows; use o arquivo .env.")
    blob = base64.b64encode(_crypt(key.encode("utf-8"), True)).decode("ascii")
    with _lock:
        data = _read(path)
        data[provider] = blob
        _write(path, data)


def load(provider: str, path: Path = PATH) -> str:
    """'' quando não há chave guardada ou ela não decifra neste usuário."""
    _check_name(provider)
    blob = _read(path).get(provider)
    if not isinstance(blob, str) or not available():
        return ""
    try:
        return _crypt(base64.b64decode(blob), False).decode("utf-8")
    except (SecretStoreError, ValueError, UnicodeDecodeError):
        return ""


def has(provider: str, path: Path = PATH) -> bool:
    _check_name(provider)
    return isinstance(_read(path).get(provider), str)


def delete(provider: str, path: Path = PATH) -> bool:
    _check_name(provider)
    with _lock:
        data = _read(path)
        if provider not in data:
            return False
        del data[provider]
        _write(path, data)
        return True
