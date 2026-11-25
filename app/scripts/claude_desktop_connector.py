"""
Conector do Creative AIx no app Claude (Claude Desktop), via o servidor MCP so de leitura do app (mcp_server.py).

    python app/scripts/claude_desktop_connector.py bundle   # gera "Creative AIx.mcpb" (extensao)
    python app/scripts/claude_desktop_connector.py config   # mostra a entrada para claude_desktop_config.json
    python app/scripts/claude_desktop_connector.py check    # testa o servidor como o Claude o abriria

Extensao (.mcpb, recomendado): no app Claude, Configuracoes > Extensoes (ou Desktop app > Extensions > Manage) >
Configuracoes avancadas > Instalar extensao... e escolha o arquivo. Ela aparece em "Local MCP servers" com nome,
icone, ferramentas, status de conexao e logs. O pacote e gerado para ESTA maquina: o lancador aponta para o
Python e a pasta do app daqui (o servidor precisa das dependencias do .venv do app).

Nada aqui altera o app Claude: este script so gera arquivos e imprime a configuracao. Instalar e decisao da pessoa.
Ferramentas expostas: buscar/ler notas do Cerebro, andamento e historico de tarefas, projetos criados. Nenhuma
age no computador, grava arquivo ou devolve segredo.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
sys.path.insert(0, str(APP))
NAME = "creative-aix"
DISPLAY = "Creative AIx"
SERVER_KEY = "creative-aix"
VERSION = "0.1.0"
OUT_DIR = APP / "memory" / "claude-desktop"          # ignorado pelo git


def venv_python() -> Path:
    """O Python do app (com as dependencias travadas); pythonw nao serve: o protocolo usa stdin/stdout."""
    exe = REPO / ".venv" / "Scripts" / "python.exe"
    return exe if exe.is_file() else Path(sys.executable)


def launcher_source() -> str:
    """Lancador dentro do pacote: roda o mcp_server.py do app instalado nesta maquina."""
    return (
        '"""Creative AIx: abre o servidor MCP so de leitura do app instalado nesta maquina."""\n'
        "import runpy\nimport sys\nfrom pathlib import Path\n\n"
        f"APP = Path({str(APP)!r})\n"
        "if not (APP / 'mcp_server.py').is_file():\n"
        "    sys.stderr.write(f'Creative AIx nao encontrado em {APP}. Gere o pacote de novo pelo app.\\n')\n"
        "    raise SystemExit(1)\n"
        "sys.path.insert(0, str(APP))\n"
        "runpy.run_path(str(APP / 'mcp_server.py'), run_name='__main__')\n"
    )


def manifest() -> dict:
    """manifest.json da especificacao MCPB (github.com/modelcontextprotocol/mcpb, MANIFEST.md, versao 0.3)."""
    import mcp_server
    return {
        "manifest_version": "0.3",
        "name": NAME,
        "display_name": DISPLAY,
        "version": VERSION,
        "description": "Cérebro, tarefas e projetos do Creative AIx dentro do Claude (somente leitura).",
        "long_description": ("Conecta o Claude ao Creative AIx instalado neste computador: buscar e ler notas do "
                             "segundo cérebro (regras, playbooks, lições, preferências), ver o que o app está fazendo, "
                             "as últimas tarefas e os projetos criados. Nenhuma ferramenta age no computador, grava "
                             "arquivos ou devolve chaves. Pacote gerado para esta máquina."),
        "author": {"name": "Creative AIx"},
        "icon": "icon.png",
        "server": {
            "type": "python",
            "entry_point": "server/launch.py",
            "mcp_config": {
                "command": str(venv_python()),
                "args": ["${__dirname}/server/launch.py"],
                "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            },
        },
        "tools": [{"name": t["name"], "description": t["description"]} for t in mcp_server.TOOLS],
        "keywords": ["creative-aix", "segundo-cerebro", "tarefas", "somente-leitura"],
        "license": "MIT",
        "compatibility": {"platforms": ["win32"], "runtimes": {"python": ">=3.11"}},
    }


def _icon_png() -> bytes:
    """Icone 256x256 a partir da imagem do README (PNG, como o manifesto pede)."""
    from PIL import Image
    src = REPO / "docs" / "images" / "creative-aix.jpg"
    img = Image.open(src).convert("RGB")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((256, 256))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def build_bundle(out_dir: Path = OUT_DIR) -> Path:
    """Gera o .mcpb (zip com manifest.json na raiz) e devolve o caminho."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{DISPLAY}.mcpb"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest(), ensure_ascii=False, indent=2))
        z.writestr("server/launch.py", launcher_source())
        try:
            z.writestr("icon.png", _icon_png())
        except Exception as exc:                 # sem icone o pacote continua valido (campo opcional)
            print(f"aviso: icone nao gerado ({type(exc).__name__})", file=sys.stderr)
    return target


def desktop_config_path() -> Path:
    """Onde o app Claude guarda claude_desktop_config.json. App MSIX (instalador novo/Store): nos dados do pacote;
    instalador classico: %APPDATA%\\Claude."""
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    for found in sorted(local.glob("Claude-Data/claude_*/claude_desktop_config.json")):
        return found
    msix = sorted(local.glob("Claude-Data/claude_*"))
    if msix:
        return msix[0] / "claude_desktop_config.json"
    return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"


def config_entry() -> dict:
    """Entrada para o metodo classico (mcpServers)."""
    return {SERVER_KEY: {"command": str(venv_python()), "args": [str(APP / "mcp_server.py")],
                         "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}}}


def check(timeout: float = 60) -> dict:
    """Abre o servidor como o Claude abriria (pasta de trabalho qualquer) e faz initialize + tools/list."""
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "claude-desktop-check", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "task_status", "arguments": {}}}]
    with zipfile.ZipFile(build_bundle()) as z:
        launcher = z.read("server/launch.py").decode("utf-8")
    tmp = OUT_DIR / "_check_launch.py"
    tmp.write_text(launcher, encoding="utf-8")
    try:
        p = subprocess.run([str(venv_python()), str(tmp)], input="".join(json.dumps(m) + "\n" for m in msgs),
                           capture_output=True, text=True, encoding="utf-8", timeout=timeout, cwd=str(Path.home()),
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        tmp.unlink(missing_ok=True)
    replies = {}
    for line in p.stdout.splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            return {"ok": False, "error": f"saida que nao e JSON no stdout: {line[:120]}"}
        replies[msg.get("id")] = msg
    tools = [t["name"] for t in (replies.get(2, {}).get("result") or {}).get("tools", [])]
    call = replies.get(3, {}).get("result") or {}
    return {"ok": bool(tools) and not call.get("isError"), "protocol": (replies.get(1, {}).get("result") or {}).get("protocolVersion"),
            "tools": tools, "task_status_ok": not call.get("isError", True), "stderr_tail": p.stderr[-300:]}


def main(argv: list) -> int:
    cmd = argv[1] if len(argv) > 1 else "bundle"
    if cmd == "bundle":
        path = build_bundle()
        print(f"Pacote gerado: {path}")
        print("Instale no app Claude: Configuracoes > Extensoes > Configuracoes avancadas > Instalar extensao...")
        return 0
    if cmd == "config":
        print(f"Arquivo do app Claude: {desktop_config_path()}")
        print("Acrescente em \"mcpServers\" (e reinicie o app Claude por completo):")
        print(json.dumps({"mcpServers": config_entry()}, ensure_ascii=False, indent=2))
        return 0
    if cmd == "check":
        result = check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
