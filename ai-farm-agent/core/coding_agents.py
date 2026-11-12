"""
Claude Code e Codex como agentes do app (E1 de docs/architecture/coding-agents-and-studio-prompt.md).

Adaptadores das CLIs oficiais, ja instaladas e autenticadas pela propria pessoa:
- Claude Code em modo nao interativo: `claude -p --output-format stream-json --verbose --restricted
  --permission-mode acceptEdits` (o prompt vai pelo stdin). `--restricted` tira Bash/WebFetch e
  confina as ferramentas de arquivo a pasta de trabalho; `acceptEdits` aceita so edicoes nela.
- Codex em modo nao interativo: `codex exec --json --cd <pasta> --sandbox workspace-write`
  (prompt pelo stdin). O sandbox do Codex so escreve dentro da pasta.

Regras (nao negociaveis):
- O app NUNCA pede, le, grava ou repassa chave de API ou token. Usa a sessao que a pessoa ja fez
  na CLI; sem sessao, explica como entrar e para. Variaveis com cara de segredo nao chegam ao
  processo filho (core/process_runner.stream_process).
- O agente externo so trabalha na pasta que a pessoa escolheu, nunca na pasta do proprio
  AI Farm Agent. Um caminho fora da pasta nos eventos da CLI e falha, nao sucesso.
- O processo filho vive num Job Object: morre com o app, com o botao Parar e no tempo limite.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Callable, Optional

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
TOOLS = ("claude", "codex")
NAMES = {"claude": "Claude Code", "codex": "Codex"}
DEFAULT_TIMEOUT_S = 600
MAX_TIMEOUT_S = 1800
DEFAULT_BUDGET_USD = 2.0
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
SNAPSHOT_LIMIT = 20000          # pasta maior que isso: nao comparamos arquivo a arquivo
TOOL_WORD = re.compile(r"\b(?:claude(?:\s+code)?|codex)\b", re.I)
_VERSION_DIR = re.compile(r"(\d+)\.(\d+)\.(\d+)")

LOGIN_HELP = {
    "claude": "Entre no Claude Code uma vez: abra um terminal, rode `claude` e use /login. "
              "O AI Farm Agent usa essa sessao e nunca pede sua chave.",
    "codex": "Entre no Codex uma vez: abra um terminal e rode `codex login`. "
             "O AI Farm Agent usa essa sessao e nunca pede sua chave.",
}
INSTALL_HELP = {
    "claude": "Claude Code nao foi encontrado. Instale o app Claude (que traz o Claude Code) ou a CLI "
              "`claude` e tente de novo.",
    "codex": "Codex nao foi encontrado. Instale o app Codex ou a CLI `codex` e tente de novo.",
}


# ── Descoberta das CLIs ───────────────────────────────────────────────────────

def _version_key(path: str) -> tuple:
    m = _VERSION_DIR.search(path.replace("\\", "/"))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _candidates(tool: str):
    if tool == "claude":
        yield shutil.which("claude")
        yield shutil.which("claude.cmd")
        appdata = os.environ.get("APPDATA", "")
        if appdata:   # o app Claude para Windows traz o Claude Code aqui, uma pasta por versao
            found = glob.glob(os.path.join(appdata, "Claude", "claude-code", "*", "*", "claude.exe"))
            yield from sorted(found, key=_version_key, reverse=True)
        yield os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    elif tool == "codex":
        yield shutil.which("codex")
        yield shutil.which("codex.cmd")
        local = os.environ.get("LOCALAPPDATA", "")
        if local:     # o app Codex para Windows traz a CLI aqui
            found = glob.glob(os.path.join(local, "OpenAI", "Codex", "bin", "*", "codex.exe"))
            yield from sorted(found, key=lambda p: os.path.getmtime(p), reverse=True)


def _argv_for(path: str) -> list:
    if path.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", path]
    return [path]


def executable(tool: str, config: Optional[dict] = None) -> list:
    """argv da CLI (prefixo), ou [] se nao estiver instalada. `coding_agents.<tool>.exe` na
    configuracao (texto ou lista) tem prioridade sobre a descoberta."""
    if tool not in TOOLS:
        return []
    mine = ((config or {}).get(tool) or {}).get("exe")
    if isinstance(mine, (list, tuple)) and mine:
        head = str(mine[0])
        return [str(x) for x in mine] if (os.path.isfile(head) or shutil.which(head)) else []
    if isinstance(mine, str) and mine.strip():
        return _argv_for(mine.strip()) if os.path.exists(mine.strip()) else []
    for path in _candidates(tool):
        if path and os.path.isfile(path):
            return _argv_for(path)
    return []


def tool_in(text: str) -> Optional[str]:
    """'com o claude', 'pelo codex' -> claude | codex. None quando nao cita nenhum."""
    m = TOOL_WORD.search(text or "")
    if not m:
        return None
    return "claude" if m.group(0).lower().startswith("claude") else "codex"


# ── Pasta de trabalho ─────────────────────────────────────────────────────────

def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def is_app_repo(folder: str) -> bool:
    """A pasta do proprio AI Farm Agent (ou algo dentro dela)."""
    try:
        return _inside(Path(folder), REPO)
    except (TypeError, ValueError):
        return False


def folder_error(folder) -> str:
    """Por que esta pasta nao serve ('' = serve). Mesma regra no validador e no motor."""
    if not isinstance(folder, str) or not folder.strip():
        return "Pasta do projeto ausente."
    if not os.path.isdir(folder):
        return f"Pasta do projeto nao existe: {folder}"
    if is_app_repo(folder):
        return "O agente externo nao trabalha na pasta do proprio AI Farm Agent (use o modo Desenvolvedor)."
    return ""


def snapshot(folder: str) -> Optional[dict]:
    """{caminho relativo: (tamanho, mtime)} dos arquivos da pasta, ou None se for grande demais."""
    out = {}
    root = Path(folder)
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            p = Path(base) / name
            try:
                st = p.stat()
            except OSError:
                continue
            out[p.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns)
            if len(out) > SNAPSHOT_LIMIT:
                return None
    return out


def changed_files(before: Optional[dict], after: Optional[dict]) -> Optional[dict]:
    if before is None or after is None:
        return None
    return {"added": sorted(set(after) - set(before)),
            "removed": sorted(set(before) - set(after)),
            "modified": sorted(k for k in before if k in after and before[k] != after[k])}


# ── Comando e eventos ─────────────────────────────────────────────────────────

MCP_NAME = "aifarm"


def mcp_server_argv() -> list:
    """Como iniciar o servidor MCP de leitura do app (mcp_server.py) com o mesmo Python do app."""
    import sys
    return [sys.executable.replace("\\", "/"), str(APP / "mcp_server.py").replace("\\", "/")]


def build_command(tool: str, exe: list, folder: str, *, full_access: bool = False,
                  budget_usd: float = DEFAULT_BUDGET_USD, mcp: bool = False) -> list:
    """Linha de comando da CLI. O prompt vai pelo stdin (sem limite de argv nem aspas).
    mcp: liga o servidor MCP de leitura do app (Cerebro, tarefas, projetos) para a CLI consultar."""
    if tool == "claude":
        cmd = [*exe, "-p", "--output-format", "stream-json", "--verbose",
               "--permission-mode", "acceptEdits", "--max-budget-usd", f"{float(budget_usd):.2f}"]
        if not full_access:
            cmd.append("--restricted")
        if mcp:
            command, *args = mcp_server_argv()
            config = {"mcpServers": {MCP_NAME: {"type": "stdio", "command": command, "args": args}}}
            # so as ferramentas deste servidor (todas de leitura) sao liberadas sem pergunta
            cmd += ["--mcp-config", json.dumps(config), "--allowedTools", f"mcp__{MCP_NAME}"]
        return cmd
    if tool == "codex":
        cmd = [*exe, "exec", "--json", "--color", "never", "--skip-git-repo-check", "--cd", folder,
               "--sandbox", "danger-full-access" if full_access else "workspace-write"]
        if mcp:
            command, *args = mcp_server_argv()
            cmd += ["-c", f"mcp_servers.{MCP_NAME}.command={json.dumps(command)}",
                    "-c", f"mcp_servers.{MCP_NAME}.args={json.dumps(args)}"]
        return cmd
    raise ValueError(f"ferramenta desconhecida: {tool}")


def parse_event(tool: str, line: str) -> Optional[dict]:
    """Uma linha JSON da CLI -> {'kind': text|tool|file|result|error, 'text', 'path'?, 'ok'?}.
    None para linhas que nao interessam (ou que nao sao JSON)."""
    line = (line or "").strip()
    if not line.startswith("{"):
        return None
    try:
        ev = json.loads(line)
    except ValueError:
        return None
    if not isinstance(ev, dict):
        return None
    kind = ev.get("type")
    if tool == "claude":
        if kind == "assistant":
            out = []
            for block in ((ev.get("message") or {}).get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and str(block.get("text", "")).strip():
                    out.append({"kind": "text", "text": str(block["text"]).strip()})
                elif block.get("type") == "tool_use":
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    path = inp.get("file_path") or inp.get("notebook_path") or ""
                    if path:
                        out.append({"kind": "file", "text": f"{block.get('name', 'tool')}: {path}", "path": str(path)})
                    else:
                        out.append({"kind": "tool", "text": f"{block.get('name', 'tool')}"})
            return {"kind": "many", "events": out} if out else None
        if kind == "result":
            ok = not ev.get("is_error") and ev.get("subtype") == "success"
            text = str(ev.get("result") or "").strip()
            errors = ev.get("errors") if isinstance(ev.get("errors"), list) else []
            if not ok and not text:
                text = "; ".join(str(e) for e in errors) or str(ev.get("subtype") or "falhou")
            return {"kind": "result", "ok": ok, "text": text, "cost": ev.get("total_cost_usd")}
        return None
    if tool == "codex":
        if kind in ("item.completed", "item.started"):
            item = ev.get("item") if isinstance(ev.get("item"), dict) else {}
            it = item.get("type")
            if it == "agent_message" and kind == "item.completed" and str(item.get("text", "")).strip():
                return {"kind": "text", "text": str(item["text"]).strip()}
            if it == "mcp_tool_call" and kind == "item.started":
                return {"kind": "tool", "text": f"MCP {item.get('server', '')}.{item.get('tool', '')}"}
            if it == "command_execution" and kind == "item.started":
                return {"kind": "tool", "text": f"comando: {str(item.get('command', ''))[:160]}"}
            if it == "file_change" and kind == "item.completed":
                changes = item.get("changes") if isinstance(item.get("changes"), list) else []
                out = [{"kind": "file", "text": f"{c.get('kind', 'edit')}: {c.get('path')}", "path": str(c.get("path"))}
                       for c in changes if isinstance(c, dict) and c.get("path")]
                return {"kind": "many", "events": out} if out else None
            if it == "error":
                return {"kind": "error", "text": str(item.get("message") or "erro")}
            return None
        if kind == "turn.completed":
            return {"kind": "result", "ok": True, "text": ""}
        if kind == "turn.failed":
            err = ev.get("error") if isinstance(ev.get("error"), dict) else {}
            return {"kind": "result", "ok": False, "text": str(err.get("message") or "falhou")}
        if kind == "error":
            return {"kind": "error", "text": str(ev.get("message") or "erro")}
    return None


def _flatten(ev: Optional[dict]) -> list:
    if not ev:
        return []
    return ev["events"] if ev.get("kind") == "many" else [ev]


# ── Sessao ────────────────────────────────────────────────────────────────────

def session_status(tool: str, exe: list, cwd: str, runner=None) -> tuple:
    """(entrou?, detalhe). So pergunta a CLI; nenhum arquivo de credencial e lido pelo app."""
    from core.process_runner import stream_process
    run = runner or stream_process
    lines = []
    if tool == "claude":
        res = run([*exe, "auth", "status"], cwd=cwd, on_line=lines.append, timeout=30)
        try:
            data = json.loads("".join(lines))     # sai com codigo 1 quando nao entrou, mas o JSON vem do mesmo jeito
        except ValueError:
            data = None
        if not isinstance(data, dict):
            return False, (res.get("stderr") or res.get("result") or "").strip()[:300]
        return bool(data.get("loggedIn")), str(data.get("authMethod") or "")
    res = run([*exe, "login", "status"], cwd=cwd, on_line=lines.append, timeout=30)
    detail = (" ".join(lines) or res.get("stderr") or "").strip()[:300]
    return res.get("status") == "succeeded", detail


# ── Execucao ──────────────────────────────────────────────────────────────────

def _full_access_for(folder: str, config: dict) -> bool:
    """Pasta onde a pessoa ligou explicitamente o acesso total (config: coding_agents.full_access_projects)."""
    mine = config.get("full_access_projects") or []
    if not isinstance(mine, list):
        return False
    target = Path(folder)
    return any(isinstance(p, str) and p.strip() and _inside(target, Path(os.path.expandvars(os.path.expanduser(p))))
               and _inside(Path(os.path.expandvars(os.path.expanduser(p))), target) for p in mine)


def run(tool: str, prompt: str, folder: str, *, on_progress: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None, timeout: Optional[float] = None,
        config: Optional[dict] = None) -> dict:
    """Roda a CLI na pasta e devolve {'success','status','verified','result','changed','outside',...}.
    verified = terminou bem, mexeu so dentro da pasta e os arquivos citados existem."""
    cfg = config if config is not None else _config()
    say = on_progress or (lambda _m: None)
    tool = (tool or "").lower().strip()
    base = {"success": False, "status": "failed", "verified": False, "tool": tool, "folder": folder,
            "changed": None, "outside": [], "exit_code": None, "result": ""}
    if tool not in TOOLS:
        return {**base, "status": "rejected", "result": "Diga com qual agente: Claude Code ou Codex."}
    if not isinstance(prompt, str) or not prompt.strip():
        return {**base, "status": "rejected", "result": "Pedido vazio para o agente externo."}
    bad = folder_error(folder)
    if bad:
        return {**base, "status": "rejected", "result": bad}
    folder = os.path.normpath(folder)
    exe = executable(tool, cfg)
    if not exe:
        return {**base, "result": INSTALL_HELP[tool]}
    name = NAMES[tool]
    if cfg.get("check_session", True):
        ok, detail = session_status(tool, exe, folder)
        if not ok:
            say(f"{name}: sem sessao ({detail or 'nao entrou'})")
            return {**base, "status": "needs_login", "result": f"{name} ainda nao esta conectado. {LOGIN_HELP[tool]}"}
    full = _full_access_for(folder, cfg)
    if full:
        say(f"AVISO: acesso total ligado para esta pasta ({name} pode rodar comandos sem confirmar).")
    limit = min(MAX_TIMEOUT_S, float(timeout or cfg.get("timeout_s") or DEFAULT_TIMEOUT_S))
    cmd = build_command(tool, exe, folder, full_access=full,
                        budget_usd=float(cfg.get("budget_usd") or DEFAULT_BUDGET_USD), mcp=use_mcp(cfg))
    before = snapshot(folder)
    root = Path(folder)
    texts, files, outside, errors = [], [], [], []
    final = {"ok": None, "text": "", "cost": None}
    say(f"{name} comecou em {folder}")

    def on_line(line: str) -> None:
        for ev in _flatten(parse_event(tool, line)):
            k = ev.get("kind")
            if k == "text":
                texts.append(ev["text"])
                say(f"{name}: {ev['text'][:300]}")
            elif k == "file":
                path = Path(ev["path"]) if os.path.isabs(ev["path"]) else root / ev["path"]
                if not _inside(path, root):
                    outside.append(str(path))
                    say(f"{name} tocou fora da pasta: {path}")
                else:
                    files.append(str(path))
                    say(f"{name}: {ev['text'][:200]}")
            elif k == "tool":
                say(f"{name}: {ev['text'][:200]}")
            elif k == "error":
                errors.append(ev["text"])
                say(f"{name} erro: {ev['text'][:200]}")
            elif k == "result":
                final.update(ok=ev.get("ok"), text=ev.get("text") or "", cost=ev.get("cost"))

    from core.process_runner import stream_process
    started = time.monotonic()
    res = stream_process(cmd, cwd=folder, stdin_text=prompt, on_line=on_line, should_stop=should_stop,
                         timeout=limit)
    elapsed = time.monotonic() - started
    after = snapshot(folder)
    changed = changed_files(before, after)
    out = {**base, "folder": folder, "changed": changed, "outside": outside, "exit_code": res.get("exit_code"),
           "elapsed_s": round(elapsed, 1), "cost_usd": final.get("cost"), "status": res.get("status")}
    summary = (final.get("text") or (texts[-1] if texts else "")).strip()
    if res.get("status") in ("cancelled", "timeout"):
        out["result"] = f"{name} {'cancelado' if res['status'] == 'cancelled' else 'parou no tempo limite'} " \
                        f"depois de {elapsed:.0f} s." + (f"\nAlteracoes ate aqui: {_describe(changed)}" if changed else "")
        return out
    if outside:
        out.update(status="failed", success=False)
        out["result"] = (f"{name} tocou em arquivo fora da pasta do projeto, por isso a tarefa conta como falha: "
                         + ", ".join(outside[:5]))
        return out
    stderr = (res.get("stderr") or "").strip()
    ok = res.get("status") == "succeeded" and final.get("ok") is not False and not errors
    if not ok:
        why = summary or "; ".join(errors) or stderr[-600:] or f"saida {res.get('exit_code')}"
        if re.search(r"not logged in|login|unauthori[sz]ed|authentication|api key", why, re.I):
            out["status"] = "needs_login"
            why = f"{name} pediu login. {LOGIN_HELP[tool]}"
        out.update(success=False, result=f"{name} nao concluiu: {why[:800]}")
        return out
    # A CLI disse que gravou, mas o arquivo nao existe: falha (o resumo dela costuma admitir o erro, e antes
    # o app contava como sucesso)
    missing = sorted({f for f in files if not os.path.exists(f)})
    removed = {str(root / r) for r in ((changed or {}).get("removed") or [])}
    missing = [m for m in missing if os.path.normcase(m) not in {os.path.normcase(r) for r in removed}]
    if missing:
        out.update(success=False, status="failed",
                   result=f"{name} nao conseguiu gravar: " + ", ".join(os.path.basename(m) for m in missing[:5])
                          + ("\n" + summary[:600] if summary else ""))
        return out
    out.update(success=True, status="succeeded", verified=not missing)
    out["result"] = f"{name} concluiu em {os.path.basename(folder.rstrip(os.sep)) or folder}." \
                    + (f"\n{summary[:1500]}" if summary else "") + f"\nArquivos: {_describe(changed)}"
    return out


def status(cfg: Optional[dict] = None) -> dict:
    """Para a tela de Configuracoes: cada CLI instalada? versao? conectada? e o MCP do app responde?
    So pergunta as CLIs (nunca le arquivo de credencial) e nao gasta nada."""
    from core.process_runner import stream_process
    cfg = cfg if cfg is not None else _config()
    out = {"tools": [], "mcp": mcp_selftest()}
    for tool in TOOLS:
        exe = executable(tool, cfg)
        item = {"tool": tool, "name": NAMES[tool], "installed": bool(exe), "version": "", "logged_in": False,
                "detail": "", "login_help": LOGIN_HELP[tool], "install_help": INSTALL_HELP[tool]}
        if exe:
            lines = []
            stream_process([*exe, "--version"], cwd=str(Path.home()), on_line=lines.append, timeout=30)
            item["version"] = (lines[0] if lines else "").strip()[:60]
            item["logged_in"], item["detail"] = session_status(tool, exe, str(Path.home()))
            item["detail"] = re.sub(r"\s+", " ", item["detail"] or "")[:80]
        out["tools"].append(item)
    return out


def mcp_selftest(timeout: float = 30) -> dict:
    """Abre o servidor MCP do app como uma CLI faria (initialize + tools/list) e conta as ferramentas."""
    import subprocess
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    try:
        p = subprocess.run(mcp_server_argv(), input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True,
                           text=True, encoding="utf-8", timeout=timeout, cwd=str(APP),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        replies = [json.loads(line) for line in p.stdout.splitlines() if line.strip().startswith("{")]
        tools = next((r["result"]["tools"] for r in replies if r.get("id") == 2 and "result" in r), [])
        return {"ok": bool(tools), "tools": [t["name"] for t in tools]}
    except Exception as exc:
        return {"ok": False, "tools": [], "error": f"{type(exc).__name__}: {exc}"[:200]}


def use_mcp(cfg: dict) -> bool:
    """Servidor MCP de leitura ligado? Configuracoes do app (tela) vencem o config.yaml."""
    try:
        from core.user_settings import load
        mine = load().get("coding_mcp")
        if isinstance(mine, bool):
            return mine
    except Exception:
        pass
    return cfg.get("mcp", True) is not False


def _describe(changed: Optional[dict]) -> str:
    if changed is None:
        return "pasta grande demais para comparar"
    parts = []
    for key, label in (("added", "novos"), ("modified", "alterados"), ("removed", "removidos")):
        items = changed.get(key) or []
        if items:
            parts.append(f"{len(items)} {label} (" + ", ".join(items[:6]) + (", ..." if len(items) > 6 else "") + ")")
    return "; ".join(parts) or "nenhum arquivo mudou"


def _config() -> dict:
    try:
        from core.config import get_config
        data = get_config().get("coding_agents", {}) or {}
        return dict(data) if isinstance(data, dict) else {}
    except Exception:
        return {}
