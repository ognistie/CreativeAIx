"""Classificação do resultado observado na fronteira de execução."""
import hashlib
import os
import stat


def file_identity(path: str) -> tuple | None:
    try:
        info = os.stat(path, follow_symlinks=False)
        return (os.path.normcase(os.path.realpath(path)), info.st_dev, info.st_ino,
                info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    except OSError:
        return None


def file_copy(source: str, destination: str, original: os.stat_result) -> bool:
    """Confere conteúdo de cópias regulares pequenas e estabilidade da origem."""
    if original.st_size > 16 * 1024 * 1024:
        return False
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns

    try:
        with open(source, "rb") as origin, open(destination, "rb") as copy:
            if identity(os.fstat(origin.fileno())) != identity(original):
                return False
            copy_before = os.fstat(copy.fileno())
            if original.st_size != copy_before.st_size:
                return False
            # Limita inclusive arquivos modificados por outro processo durante a conferência.
            left, right = origin.read(original.st_size + 1), copy.read(original.st_size + 1)
            return (len(left) == len(right) == original.st_size
                    and hashlib.sha256(left).digest() == hashlib.sha256(right).digest()
                    and identity(os.stat(source)) == identity(original)
                    and identity(os.stat(destination)) == identity(copy_before))
    except OSError:
        return False


def bounded_content(path: str) -> str | None:
    """Hash de arquivo regular pequeno, estável durante a leitura e sem link final."""
    before = file_identity(path)
    if before is None or not stat.S_ISREG(before[3]) or before[4] > 16 * 1024 * 1024:
        return None
    try:
        with open(path, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (info.st_dev, info.st_ino) != before[1:3]:
                return None
            data = stream.read(before[4] + 1)
        return hashlib.sha256(data).hexdigest() if len(data) == before[4] and file_identity(path) == before else None
    except OSError:
        return None


def classify(result: dict) -> str:
    status = result.get("status")
    if status in ("simulated", "cancelled", "timeout", "action_limit", "budget_limit"):
        return status
    if status in ("rejected", "needs_confirmation"):
        return "policy_stop"
    if status in ("uncertain", "partial"):
        return status
    if result.get("success") is True:
        return "verified" if result.get("verified") is True else "operational"
    if result.get("effect_started") is False:
        return "pre_effect_failure"
    return "unverified_failure"


# ── Verificação independente (Phase VI.2) ─────────────────────────────────────────────────────────
# Uma segunda conferência, fora do handler que executou: observa o estado final do recurso. O executor deixa de
# ser a única fonte de verdade; divergência vira "falso sucesso" e o passo deixa de contar como verificado.
VERIFIER_VERSION = "independent-v2"


def independent_check(action: str, params: dict, result: dict) -> dict | None:
    """-> {action, resource, method, observed, ok, version, at} ou None quando não há verificador para a ação.
    Só leitura, limitada (16 MiB); nunca repete nem desfaz o efeito."""
    from datetime import datetime
    from pathlib import Path
    from core.automation_files import expand

    def record(resource, method, ok, observed):
        return {"action": action, "resource": str(resource)[:300], "method": method, "observed": observed,
                "ok": bool(ok), "version": VERIFIER_VERSION, "at": datetime.now().isoformat(timespec="seconds")}

    p = params if isinstance(params, dict) else {}
    try:
        if action == "create_folder":
            path = expand(p.get("path", ""))
            return record(path, "directory_exists", os.path.isdir(path), "pasta presente" if os.path.isdir(path) else "pasta ausente")
        if action == "move_file":
            src, dst = expand(p.get("source", "")), expand(p.get("destination", ""))
            ok = os.path.lexists(dst) and not os.path.lexists(src)
            return record(dst, "destination_present_source_absent", ok, "movido" if ok else "origem ou destino divergente")
        if action == "copy_file":
            src, dst = expand(p.get("source", "")), expand(p.get("destination", ""))
            if os.path.isfile(src) and os.path.isfile(dst):
                a, b = bounded_content(src), bounded_content(dst)
                ok = a is not None and a == b
                return record(dst, "sha256_equal", ok, "conteúdo igual" if ok else "conteúdo diferente ou grande demais")
            return record(dst, "destination_present", os.path.exists(dst), "presente" if os.path.exists(dst) else "ausente")
        if action == "write_file":
            path, content = expand(p.get("path", "")), p.get("content", "")
            digest = bounded_content(path)
            ok = isinstance(content, str) and digest == hashlib.sha256(content.encode("utf-8")).hexdigest()
            return record(path, "sha256_of_requested_content", ok, "conteúdo igual ao pedido" if ok else "conteúdo divergente")
        if action == "create_workbook":
            files = ((result or {}).get("artifacts") or {}).get("files") or []
            manifest = p.get("manifest") or {}
            if not files:
                return record("", "workbook_reopen", False, "planilha sem arquivo registrado")
            from openpyxl import load_workbook
            wb = load_workbook(files[0], read_only=True, data_only=False)
            try:
                expected = [s.get("title") for s in manifest.get("sheets", []) if isinstance(s, dict)]
                ok = bool(wb.sheetnames) and (not expected or wb.sheetnames == expected)
                for sheet in manifest.get("sheets", []):
                    if sheet.get("title") not in wb.sheetnames:
                        ok = False
                        continue
                    ws = wb[sheet["title"]]
                    for r, row in enumerate(sheet.get("rows", []), 1):
                        for c, value in enumerate(row, 1):
                            ok = ok and ws.cell(r, c).value == (None if value == "" else value)
            finally:
                wb.close()
            return record(files[0], "workbook_reopen_requested_cells", ok, ", ".join(wb.sheetnames)[:200])
        if action in ("create_project", "edit_project"):
            files = ((result or {}).get("artifacts") or {}).get("files") or []
            missing = [f for f in files if not Path(f).is_file()]
            return record(((result or {}).get("artifacts") or {}).get("folder", ""), "artifact_files_present",
                          bool(files) and not missing, f"{len(files) - len(missing)}/{len(files)} arquivos")
    except Exception as error:                 # verificador nunca derruba a tarefa: falha vira não verificado
        return record("", "verifier_error", False, type(error).__name__)
    return None


def apply_independent_check(action: str, params: dict, result: dict) -> dict:
    """Passo dado como verificado pelo executor passa pela segunda conferência. Divergência -> não verificado."""
    if not isinstance(result, dict) or result.get("verified") is not True or result.get("dry_run"):
        return result
    check = independent_check(action, params, result)
    if check is None:
        return result
    out = {**result, "independent_check": check}
    if not check["ok"]:
        out.update(verified=False, false_success=True)
    return out
