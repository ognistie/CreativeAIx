"""Estratégia de recuperação FILE baseada em uma observação local limitada."""
import os
import re
import stat
from pathlib import Path


def alternative_copy(goal: str, params: dict, result: dict, stop, allow_directory) -> dict | None:
    """Mantém nome e destino do pedido e procura uma fonte única sob a pasta original."""
    return _alternative(goal, params, result, stop, allow_directory, "source", "copy_source_missing")


def alternative_read(goal: str, params: dict, result: dict, stop, allow_directory) -> dict | None:
    return _alternative(goal, params, result, stop, allow_directory, "path", "read_source_missing")


def _alternative(goal, params, result, stop, allow_directory, key, reason):
    if result.get("failure_reason") != reason or stop():
        return None
    from core.paths import is_network_path
    raw = os.path.expanduser(os.path.expandvars(params[key]))
    if is_network_path(raw):
        return None
    source = Path(raw)
    name = re.escape(source.name)
    if (not source.is_absolute()
            or re.search(rf"[/\\]{name}(?![\w.\-])", goal, re.IGNORECASE)
            or not re.search(rf"(?<![\w.\-]){name}(?![\w.\-])", goal, re.IGNORECASE)):
        return None
    root = source.parent
    if not allow_directory(str(root)):
        return None
    pending, match, scanned = [root], None, 0
    try:
        while pending:
            if stop():
                return None
            folder = pending.pop()
            info = os.lstat(folder)
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                return None
            with os.scandir(folder) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned > 256 or stop():
                        return None
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        if allow_directory(entry.path):
                            pending.append(entry.path)
                    elif stat.S_ISREG(info.st_mode) and os.path.normcase(entry.name) == os.path.normcase(source.name):
                        if match is not None:
                            return None
                        match = entry.path
    except OSError:
        return None
    if match is None or source.exists() or os.path.normcase(match) == os.path.normcase(str(source)):
        return None
    return {**params, key: match}
