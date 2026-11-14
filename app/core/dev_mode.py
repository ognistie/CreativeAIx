"""
Modo Desenvolvedor (E3): mudar a plataforma por dentro, com seguranca.

Nivel 1 e 2 vivem no Harness (core/harness.py, secao `dev`): saudacao e dica da tela inicial,
atalhos de tarefa e cartoes em JSON validado. Nada ali executa codigo novo.

Nivel 3 (este modulo): o Claude Code ou o Codex (core/coding_agents.py) muda codigo numa worktree
git separada, fora da pasta do app. Regras fixas em codigo, nao em prompt:
- so arquivos .qml/.js/.md dentro de ALLOWED; qualquer outro caminho tocado reprova a proposta
  inteira (FORBIDDEN nunca, nem por pedido da IA);
- antes de aplicar: diff mostrado, gate verde na worktree (smoke de QML + check_release --code-only)
  e clique explicito da pessoa;
- aplicar = commit na branch dev/<id> + merge local sem fast-forward; desfazer = git revert do merge.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
DEV_ROOT = REPO.parent / ".creative-aix-dev"
STATE = APP / "memory" / "dev_mode.json"
TOOLS = ("claude", "codex")
ALLOWED = ("app/desktop/qml/views/", "app/desktop/qml/components/", "app/desktop/qml/dev/")
ALLOWED_EXT = (".qml", ".js", ".md")
FORBIDDEN = ("app/core/action_risk.py", "app/core/action_policy.py",
             "app/core/plan_validator.py", "app/core/process_runner.py",
             "app/main.py", "app/desktop/bridge.py", "config.yaml")
_SECRET_NAME = re.compile(r"(?:^\.env|credential|secret|token|\.key$|\.pem$)", re.I)
GATE_TIMEOUT_S = 1200
MAX_DIFF = 200_000

PROMPT = (
    "Voce esta numa worktree do Creative AIx (app desktop em PySide6 + interface React em ui/). Faca SO a mudanca pedida.\n"
    "Pode editar apenas arquivos .qml, .js e .md dentro de: desktop/qml/views, desktop/qml/components e "
    "desktop/qml/dev (crie esta pasta para arquivos novos). Qualquer outro arquivo tocado reprova a proposta.\n"
    "Nao mexa em core/, main.py, desktop/bridge.py, config.yaml nem em arquivos de credencial. "
    "Use os tokens de desktop/qml/components/Theme.qml (nenhuma cor solta). Nao rode comandos nem instale nada.\n"
    "Ao terminar, resuma em ate 3 linhas o que mudou.\n\nPEDIDO: "
)


def path_violation(rel: str) -> str:
    """'' se o caminho (relativo a raiz do repo, com /) pode ser mudado pelo modo Desenvolvedor."""
    rel = rel.replace("\\", "/").lstrip("./")
    name = rel.rsplit("/", 1)[-1]
    if rel in FORBIDDEN or _SECRET_NAME.search(name):
        return f"arquivo proibido: {rel}"
    if not rel.startswith(ALLOWED):
        return f"fora das pastas permitidas: {rel}"
    if not rel.lower().endswith(ALLOWED_EXT):
        return f"tipo de arquivo nao permitido: {rel}"
    return ""


# APIs que tiram dados do app ou agem fora dele. Uma proposta que ACRESCENTA uma delas e reprovada antes do gate
# (segunda defesa: o gate ja roda em desktop/qml_sandbox.py, que bloqueia rede, abertura externa e escrita).
_RISKY = re.compile(r"XMLHttpRequest|openUrlExternally|LocalStorage|createQmlObject|Qt\.include|"
                    r"[\"'](?:https?|ftp|file):|\bWorkerScript\b")


def risky_lines(diff: str) -> list:
    """Linhas ACRESCENTADAS (+) de um diff unificado que usam rede, abertura externa ou armazenamento."""
    out = []
    for line in (diff or "").splitlines():
        if line.startswith("+") and not line.startswith("+++") and _RISKY.search(line):
            out.append(line[1:].strip()[:160])
    return out


def _git(repo, *args, check=True, timeout=120) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(out.stderr or out.stdout).strip()[:400]}")
    return out.stdout


def _changed_paths(worktree) -> list:
    rows = _git(worktree, "status", "--porcelain", "-z", "--no-renames", "--untracked-files=all")
    return [row[3:] for row in rows.split("\0") if row]


def _review_snapshot(worktree: Path) -> dict:
    """Bind the review to the staged tree and its original parent."""
    if (_git(worktree, "diff", "--name-only", "-z")
            or _git(worktree, "ls-files", "--others", "--exclude-standard", "-z")):
        raise ValueError("A worktree mudou desde a proposta. Gere uma nova proposta para revisar.")
    return {"parent": _git(worktree, "rev-parse", "HEAD").strip(),
            "tree": _git(worktree, "write-tree").strip()}


def run_gate(worktree: Path, on_progress: Callable[[str], None]) -> dict:
    """Gate na worktree pelo mesmo interpretador do app, num Job Object. {'ok', 'detail'}."""
    from core.process_runner import stream_process
    app = Path(worktree) / "app"
    lines = []

    def on_line(line):
        lines.append(line)
        if line.startswith("{") or "READY" in line or "FAIL" in line:
            on_progress(line[:200])

    for script, args in (("smoke_ui.py", []), ("check_release.py", ["--code-only"])):
        on_progress(f"gate: {script}")
        res = stream_process([sys.executable, str(app / "scripts" / script), *args], cwd=str(app),
                             on_line=on_line, timeout=GATE_TIMEOUT_S)
        if res.get("status") != "succeeded":
            tail = "\n".join(lines[-12:])
            return {"ok": False, "detail": f"{script}: {res.get('status')} ({res.get('result') or res.get('stderr', '')[-300:]})\n{tail}"}
    ready = any("CODE_READY True" in line for line in lines)
    return {"ok": ready, "detail": "CODE_READY True" if ready else "gate sem CODE_READY True"}


class DevMode:
    def __init__(self, repo: Path = REPO, root: Path = DEV_ROOT, state: Path = STATE,
                 runner=None, gate=run_gate):
        self.repo, self.root, self.state_file = Path(repo), Path(root), Path(state)
        self.runner, self.gate = runner, gate

    # ── estado ──
    def _load(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"proposals": []}

    def _save(self, data: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def list(self) -> list:
        return [{k: v for k, v in p.items() if k != "diff"} | {"diff_size": len(p.get("diff", ""))}
                for p in self._load()["proposals"]]

    def get(self, pid: str) -> dict:
        for p in self._load()["proposals"]:
            if p["id"] == pid:
                return p
        raise KeyError("proposta desconhecida")

    def _update(self, pid: str, **fields) -> dict:
        data = self._load()
        for p in data["proposals"]:
            if p["id"] == pid:
                p.update(fields)
                self._save(data)
                return p
        raise KeyError("proposta desconhecida")

    # ── fluxo ──
    def propose(self, request: str, tool: str, on_progress: Optional[Callable[[str], None]] = None) -> dict:
        say = on_progress or (lambda _m: None)
        request = (request or "").strip()
        if tool not in TOOLS:
            raise ValueError("escolha Claude Code ou Codex")
        if len(request) < 8:
            raise ValueError("descreva a mudanca com mais detalhe")
        pid = time.strftime("%Y%m%d-%H%M%S")
        branch, worktree = f"dev/{pid}", self.root / pid
        self.root.mkdir(parents=True, exist_ok=True)
        say(f"criando worktree {worktree}")
        _git(self.repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")
        record = {"id": pid, "branch": branch, "worktree": str(worktree), "tool": tool, "request": request[:300],
                  "status": "running", "summary": "", "diff": "", "files": [], "violations": [], "gate": None,
                  "merge": "", "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        data = self._load()
        data["proposals"].insert(0, record)
        self._save(data)
        runner = self.runner
        if runner is None:
            from core.coding_agents import run as runner
        res = runner(tool, PROMPT + request, str(worktree / "app"), on_progress=say)
        changed = _changed_paths(worktree)
        violations = [v for v in (path_violation(p) for p in changed) if v]
        if not res.get("success"):
            self._remove_worktree(branch, worktree)
            return self._update(pid, status="failed", summary=str(res.get("result", ""))[:800], files=changed)
        if violations:
            self._remove_worktree(branch, worktree)
            return self._update(pid, status="rejected", files=changed, violations=violations,
                                summary="Proposta recusada: " + "; ".join(violations[:5]))
        if not changed:
            self._remove_worktree(branch, worktree)
            return self._update(pid, status="failed", summary="Nenhum arquivo mudou.")
        _git(worktree, "add", "-A")
        snapshot = _review_snapshot(worktree)
        parent, tree = snapshot["parent"], snapshot["tree"]
        changed = _git(worktree, "diff", "--name-only", "--no-renames", "-z", parent, tree).split("\0")
        changed = [path for path in changed if path]
        violations = [error for path in changed if (error := path_violation(path))]
        diff = (_git(worktree, "diff", "--stat", parent, tree) + "\n"
                + _git(worktree, "diff", "--binary", parent, tree))
        if not changed or violations or len(diff) > MAX_DIFF:
            self._remove_worktree(branch, worktree)
            return self._update(pid, status="rejected", files=changed, violations=violations,
                                summary="A proposta não pode ser revisada integralmente ou contém caminhos proibidos.")
        return self._update(pid, status="proposed", files=changed, diff=diff, snapshot=snapshot,
                            summary=str(res.get("result", ""))[:800])

    def check(self, pid: str, on_progress: Optional[Callable[[str], None]] = None) -> dict:
        p = self.get(pid)
        if p["status"] not in ("proposed", "gate_failed"):
            raise ValueError("esta proposta nao esta esperando verificacao")
        worktree = Path(p["worktree"])
        snapshot = p.get("snapshot")
        if _review_snapshot(worktree) != snapshot:
            raise ValueError("O conteúdo mudou desde a proposta. Gere uma nova proposta para revisar.")
        risky = risky_lines(_git(worktree, "diff", "--unified=0", snapshot["parent"], snapshot["tree"]))
        if risky:
            result = {"ok": False, "detail": "A proposta usa rede, abertura externa ou armazenamento local, o que o "
                                             "modo Desenvolvedor não permite:\n" + "\n".join(risky[:5])}
            return self._update(pid, gate=result, verified_snapshot=None, status="gate_failed")
        result = self.gate(worktree, on_progress or (lambda _m: None))
        if _review_snapshot(worktree) != snapshot:
            raise ValueError("O conteúdo mudou durante a verificação. Gere uma nova proposta para revisar.")
        return self._update(pid, gate=result, verified_snapshot=snapshot if result.get("ok") else None,
                            status="checked" if result.get("ok") else "gate_failed")

    def apply(self, pid: str) -> dict:
        p = self.get(pid)
        if p["status"] != "checked" or not (p.get("gate") or {}).get("ok"):
            raise ValueError("so uma proposta verificada (gate verde) pode ser aplicada")
        worktree = Path(p["worktree"])
        snapshot = p.get("verified_snapshot")
        if snapshot != p.get("snapshot") or _review_snapshot(worktree) != snapshot:
            raise ValueError("O conteúdo mudou desde a verificação. Gere uma nova proposta para revisar.")
        # Commit the immutable reviewed tree. Neither a concurrent index update nor a
        # moving branch can change the contents passed to merge.
        commit = _git(worktree, "-c", "user.name=Creative AIx", "-c", "user.email=dev@localhost",
                      "commit-tree", snapshot["tree"], "-p", snapshot["parent"],
                      "-m", f"dev: {p['request'][:72]}").strip()
        _git(self.repo, "merge", "--no-ff", "--no-edit", commit)
        sha = _git(self.repo, "rev-parse", "HEAD").strip()
        parents = _git(self.repo, "show", "-s", "--format=%P", sha).split()
        if len(parents) != 2 or parents[1] != commit:
            raise ValueError("A proposta não criou um merge. Nenhuma reversão foi habilitada.")
        self._remove_worktree(p["branch"], worktree, keep_branch=True)
        _git(self.repo, "update-ref", f"refs/heads/{p['branch']}", commit, snapshot["parent"], check=False)
        return self._update(pid, status="applied", merge=sha, worktree="")

    def undo(self, pid: str) -> dict:
        p = self.get(pid)
        if p["status"] != "applied" or not p.get("merge"):
            raise ValueError("so uma proposta aplicada pode ser desfeita")
        _git(self.repo, "revert", "-m", "1", "--no-edit", p["merge"])
        return self._update(pid, status="reverted", revert=_git(self.repo, "rev-parse", "HEAD").strip())

    def discard(self, pid: str) -> dict:
        p = self.get(pid)
        if p["status"] in ("applied", "reverted"):
            raise ValueError("proposta ja aplicada: use desfazer")
        if p.get("worktree"):
            self._remove_worktree(p["branch"], Path(p["worktree"]))
        return self._update(pid, status="discarded", worktree="")

    def _remove_worktree(self, branch: str, worktree: Path, keep_branch: bool = False) -> None:
        if worktree.exists():
            _git(self.repo, "worktree", "remove", "--force", str(worktree), check=False)
        _git(self.repo, "worktree", "prune", check=False)
        if not keep_branch:
            _git(self.repo, "branch", "-D", branch, check=False)
