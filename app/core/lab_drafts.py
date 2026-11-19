"""Rotas de rascunhos restritas às simulações do laboratório."""

import hashlib
import json
import re

from core.agent_studio import AGENTS
from core.lexicon import norm

_DRAFT = re.compile(r"10 Agentes/Rascunhos/[a-z0-9][a-z0-9-]{0,79}\.md")
_ROUTE_FIELDS = ("rota_salva", "rota_aplicada")


def _route(data: object) -> dict:
    if not isinstance(data, dict) or data.get("agent") not in AGENTS[1:]:
        raise ValueError("escolha um agente-base válido")
    prefix = data.get("prefix")
    if not isinstance(prefix, str) or not 2 <= len(prefix.strip()) <= 80 or "\n" in prefix or "\r" in prefix:
        raise ValueError("a rota precisa de um início de pedido com 2 a 80 caracteres")
    if not norm(prefix).strip():
        raise ValueError("informe um início de pedido válido")
    return {"agent": data["agent"], "prefix": " ".join(prefix.split())}


def _read_routes(header: str) -> dict:
    fields = dict(line.split(": ", 1) for line in header.splitlines() if ": " in line)
    if fields.get("tipo") != "agente-rascunho":
        raise ValueError("a nota não é um rascunho de agente")
    routes = {"base": fields.get("base")}
    for field in _ROUTE_FIELDS:
        if field in fields:
            routes[field] = _route(json.loads(fields[field]))
    return routes


def _trial(rel: str, body: str, route: dict, request: str) -> dict:
    from core.lab import ProviderUnavailable, fixture_planner

    task = " ".join(norm(request).split())
    prefix = " ".join(norm(route["prefix"]).split())
    matched = task == prefix or task.startswith(prefix + " ")
    digest = hashlib.sha256(json.dumps([rel, body, route], ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    if matched:
        return {"matched": True, "agent": route["agent"], "revision": digest, "rule": route["prefix"]}
    try:
        original = fixture_planner({"agent": "MAESTRO"}, request)["routing"]
        agents = [item["agent"] for item in original.get("subtasks", [])]
    except ProviderUnavailable:
        agents = []
    return {"matched": False, "original": agents, "revision": digest, "rule": route["prefix"]}


def draft_route(store, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("solicitação de rota inválida")
    rel = payload.get("note")
    if not isinstance(rel, str) or not _DRAFT.fullmatch(rel) or store.layer_of(rel) != "pessoal":
        raise FileNotFoundError(rel)
    parts = store.read(rel).split("---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError("o rascunho precisa conter seus metadados")
    _, header, body = parts
    routes = _read_routes(header)
    action = payload.get("action")
    if action == "load":
        return routes
    if action == "test":
        request = payload.get("request")
        if not isinstance(request, str) or not request.strip() or len(request) > 1000:
            raise ValueError("digite um pedido de teste de até 1000 caracteres")
        route = _route(routes.get("rota_aplicada") if payload.get("applied") is True else payload.get("route"))
        return {"trial": _trial(rel, body, route, request)}
    if action == "save":
        routes["rota_salva"] = _route(payload.get("route"))
    elif action == "apply" and payload.get("confirmed") is True:
        routes["rota_aplicada"] = _route(routes.get("rota_salva"))
    else:
        raise ValueError("ação de rota inválida")

    lines = [line for line in header.splitlines() if line.split(":", 1)[0] not in _ROUTE_FIELDS]
    lines.extend(f"{key}: {json.dumps(routes[key], ensure_ascii=False)}" for key in _ROUTE_FIELDS if key in routes)
    store.write(rel, "---\n" + "\n".join(lines) + "\n---\n" + body)
    return routes
