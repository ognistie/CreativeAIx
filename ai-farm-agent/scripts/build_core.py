"""Empacota o nucleo Python (modo headless da interface Tauri) com Nuitka.

Saida (layout igual ao do repositorio, para os caminhos relativos do nucleo continuarem valendo):

    build/core-bundle/
      core/                      <- recursos do app: core/creative-aix-core.exe + dependencias
        creative-aix-core.exe
        config.yaml              (Path(__file__).parent.parent do core/config.py)
        state_maps/ memory/ desktop/data/ desktop/assets/
      AI-Farm-agents/            <- o cofre de fabrica (brain.vault_path = "../AI-Farm-agents")

A casca Tauri copia essas duas pastas para os recursos do instalador (src-tauri/tauri.release.conf.json)
e o sidecar.rs roda `core/creative-aix-core.exe --ui tauri --headless` com a pasta `core` como cwd.

So o modo headless entra no pacote: PySide6 e os arquivos da interface Qt ficam de fora
(`--ui qt` no executavel empacotado avisa e sai). O app instalado continua usando a casca Tauri.

Uso (Windows, Python 3.11 do ambiente validado, Build Tools C++ instalado):
    python ai-farm-agent/scripts/build_core.py            # compila
    python ai-farm-agent/scripts/build_core.py --dry-run  # so mostra o comando
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
OUT = ROOT / "build" / "core-bundle"
WORK = ROOT / "build" / "nuitka"
EXE = "creative-aix-core.exe"

# A interface Qt nao vai no pacote do nucleo headless
QT_ONLY = ["PySide6", "shiboken6", "desktop.main", "desktop.bridge", "desktop.window_mode", "desktop.titlebar",
           "desktop.instance", "desktop.qml_sandbox"]
# Ferramentas de teste e de desenvolvimento
DEV_ONLY = ["pytest", "unittest.mock", "tests", "scripts", "pip_audit", "nuitka"]
# Dados lidos em tempo de execucao, relativos a pasta do app (ai-farm-agent/)
DATA_DIRS = ["state_maps", "memory", "desktop/data", "desktop/assets"]
# Pacotes que trazem arquivos de dados (modelos pequenos, configs) junto do codigo
PACKAGE_DATA = ["faster_whisper", "piper", "ctranslate2", "onnxruntime", "certifi", "anthropic"]


def version() -> str:
    """A mesma versao do instalador (desktop-tauri/src-tauri/tauri.conf.json)."""
    import json
    try:
        conf = json.loads((ROOT / "desktop-tauri" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
        return str(conf.get("version") or "0.1.0")
    except (OSError, ValueError):
        return "0.1.0"


def command() -> list[str]:
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=anti-bloat",
        f"--output-dir={WORK}",
        f"--output-filename={EXE}",
        "--windows-console-mode=attach",
        "--product-name=Creative AIx",
        "--company-name=Creative AIx",
        f"--file-version={version()}",
        f"--product-version={version()}",
        "--file-description=Creative AIx - nucleo",
        "--include-package=agents",
        "--include-package=core",
        "--include-module=desktop.server",
        "--include-module=desktop.bridge_core",
        "--include-module=desktop.controller",
        "--include-module=desktop.voice",
        "--include-module=desktop.foreground",
        "--include-module=mcp_server",
        f"--include-data-files={ROOT / 'config.yaml'}=config.yaml",
    ]
    cmd += [f"--nofollow-import-to={m}" for m in QT_ONLY + DEV_ONLY]
    cmd += [f"--include-package-data={p}" for p in PACKAGE_DATA if _installed(p)]
    for rel in DATA_DIRS:
        if (APP / rel).is_dir():
            cmd.append(f"--include-data-dir={APP / rel}={rel}")
    cmd.append(str(APP / "main.py"))
    return cmd


def _installed(pkg: str) -> bool:
    from importlib.util import find_spec
    try:
        return find_spec(pkg) is not None
    except (ImportError, ValueError):
        return False


def main() -> int:
    cmd = command()
    if "--dry-run" in sys.argv:
        print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
        return 0
    if sys.platform != "win32":
        print("O nucleo empacotado e so para Windows.")
        return 2
    started = time.monotonic()
    print("Compilando o nucleo com Nuitka (pode levar dezenas de minutos na primeira vez)...")
    result = subprocess.run(cmd, cwd=APP)
    if result.returncode != 0:
        return result.returncode
    dist = WORK / "main.dist"
    if not (dist / EXE).is_file():
        print(f"Saida inesperada: {dist / EXE} nao existe.")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(dist, OUT / "core")
    shutil.copytree(ROOT / "AI-Farm-agents", OUT / "AI-Farm-agents",
                    ignore=shutil.ignore_patterns(".obsidian", ".trash", "*.tmp"))
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"Pronto em {time.monotonic() - started:.0f} s: {OUT} ({size / 1024 / 1024:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
