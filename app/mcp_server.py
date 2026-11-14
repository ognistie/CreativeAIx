"""
Servidor MCP local (stdio) do Creative AIx: ferramentas SO DE LEITURA para o Claude Code e o Codex.

    python mcp_server.py            # o app passa isto as CLIs quando coding_agents.mcp = true

Ferramentas: buscar e ler notas do Cerebro, andamento das tarefas, tarefas recentes e projetos que o
app criou. Nenhuma executa acao no computador, grava arquivo ou devolve segredo. Protocolo MCP
(JSON-RPC 2.0, uma mensagem por linha no stdin/stdout), sem dependencias: a especificacao em
https://modelcontextprotocol.io/specification. Logs vao para o stderr (o stdout e do protocolo).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

PROTOCOL = "2025-06-18"
SERVER = {"name": "app", "version": "1.0.0"}
READ_LIMIT = 20000
_SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S{8,})", re.I)

TOOLS = [
    {"name": "brain_search", "title": "Buscar no Cérebro",
     "description": "Busca notas do segundo cérebro do Creative AIx (regras, playbooks, lições, preferências). "
                    "Devolve caminho, título e trecho. Só leitura.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "palavras a buscar"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8}},
         "required": ["query"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "brain_read", "title": "Ler nota do Cérebro",
     "description": "Lê uma nota do segundo cérebro pelo caminho devolvido em brain_search. Só leitura.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "caminho relativo da nota, ex.: '10 Agentes/Code/Code Agent.md'"}},
         "required": ["path"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "task_status", "title": "Andamento das tarefas",
     "description": "Resumo do que o Creative AIx está fazendo ou fez por último (registro de tarefas). Só leitura.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "recent_tasks", "title": "Tarefas recentes",
     "description": "Últimas execuções: pedido, sucesso, agentes e pasta criada. Só leitura.",
     "inputSchema": {"type": "object", "properties": {
         "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10}}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "list_projects", "title": "Projetos criados",
     "description": "Pastas de projetos que o Creative AIx criou ou alterou, mais recentes primeiro. Só leitura.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
]


def _clean(text: str) -> str:
    return _SECRET.sub("[omitido]", text or "")


def _brain():
    from core.brain import get_brain
    return get_brain()


def call_tool(name: str, args: dict) -> str:
    args = args if isinstance(args, dict) else {}
    if name == "brain_search":
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query vazia")
        limit = max(1, min(20, int(args.get("limit") or 8)))
        hits = _brain().store.search(query, limit=limit)
        if not hits:
            return "Nenhuma nota encontrada."
        return "\n".join(f"- {h['rel']} — {h['title']}: {_clean(h.get('snippet', ''))}" for h in hits)
    if name == "brain_read":
        rel = str(args.get("path") or "").replace("\\", "/").strip().lstrip("/")
        if not rel or ".." in rel.split("/") or not rel.lower().endswith(".md") or rel.startswith("."):
            raise ValueError("caminho invalido (use um caminho .md devolvido por brain_search)")
        text = _brain().store.read(rel)
        if not text:
            raise ValueError("nota nao encontrada")
        return _clean(text[:READ_LIMIT])
    if name == "task_status":
        from core.task_ledger import get_ledger
        from core.task_status import describe
        return _clean(describe(get_ledger()))
    if name in ("recent_tasks", "list_projects"):
        from desktop import history_store
        items = history_store.list_all(limit=200)
        if name == "recent_tasks":
            limit = max(1, min(30, int(args.get("limit") or 10)))
            rows = []
            for e in items[:limit]:
                agents = ", ".join(sorted({s.get("agent", "") for s in e.get("subtasks") or [] if s.get("agent")}))
                folder = (e.get("artifacts") or {}).get("folder") or ""
                rows.append(f"- {e.get('ended_at') or e.get('started_at', '')} | {'ok' if e.get('success') else 'falhou'} | "
                            f"{_clean(e.get('task', ''))[:120]}" + (f" | {agents}" if agents else "") + (f" | {folder}" if folder else ""))
            return "\n".join(rows) or "Nenhuma tarefa registrada."
        seen, rows = set(), []
        for e in items:
            folder = (e.get("artifacts") or {}).get("folder")
            if folder and folder not in seen and os.path.isdir(folder):
                seen.add(folder)
                rows.append(f"- {folder} ({_clean(e.get('task', ''))[:80]})")
        return "\n".join(rows[:30]) or "Nenhum projeto criado ainda."
    raise KeyError(name)


def handle(msg: dict):
    """Uma mensagem JSON-RPC -> resposta (ou None para notificacoes)."""
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:                       # notificacao (ex.: notifications/initialized): sem resposta
        return None
    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    def err(code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}
    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        return ok({"protocolVersion": asked if asked in ("2024-11-05", "2025-03-26", "2025-06-18") else PROTOCOL,
                   "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER,
                   "instructions": "Ferramentas só de leitura do Creative AIx: Cérebro, tarefas e projetos."})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        if name not in {t["name"] for t in TOOLS}:
            return err(-32602, f"ferramenta desconhecida: {name}")
        try:
            text = call_tool(name, params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as exc:              # erro da ferramenta volta como resultado, para o modelo corrigir
            return ok({"content": [{"type": "text", "text": f"Erro: {exc}"}], "isError": True})
    return err(-32601, f"metodo nao suportado: {method}")


def serve(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalido"}}
        else:
            reply = handle(msg) if isinstance(msg, dict) else {"jsonrpc": "2.0", "id": None,
                                                              "error": {"code": -32600, "message": "requisicao invalida"}}
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


def main() -> int:
    # stdout so carrega o protocolo: qualquer print do app vai para o stderr
    proto = sys.stdout
    sys.stdout = sys.stderr
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        proto.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    serve(sys.stdin, proto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
