"""Rotas de rascunhos do Lab: prévia e teste sem efeito; rota aplicada vira perfil nos pedidos reais."""

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


# ── Perfil aplicado: o rascunho vale nos pedidos reais ─────────────────────────────────────────
# Um rascunho com rota APLICADA (a pessoa confirmou no Lab) vira um perfil sobre o agente-base: pedidos que
# começam com o prefixo vão para esse agente, e o texto do rascunho entra no contexto dele como instrução da
# pessoa. O perfil nunca cria capacidade nova: o agente continua um dos agentes-base (KNOWN_AGENTS) e o plano
# passa pelas mesmas políticas e confirmações de qualquer pedido.
PROFILE_MAX_CHARS = 1200
_DRAFT_FOLDER = "10 Agentes/Rascunhos"


def applied_profiles(store) -> list[dict]:
    """Rascunhos pessoais com rota aplicada válida: [{rel, agent, prefix, name, body}]. Nota inválida fica de fora."""
    out = []
    try:
        files = list(store.files(_DRAFT_FOLDER, recursive=False))
    except Exception:
        return out
    for rel, _path in files:
        if not _DRAFT.fullmatch(rel) or store.layer_of(rel) != "pessoal":
            continue
        parts = store.read(rel).split("---\n", 2)
        if len(parts) != 3 or parts[0]:
            continue
        try:
            route = _read_routes(parts[1]).get("rota_aplicada")
        except (ValueError, json.JSONDecodeError):
            continue
        if not route:
            continue
        fields = dict(line.split(": ", 1) for line in parts[1].splitlines() if ": " in line)
        out.append({"rel": rel, "agent": route["agent"], "prefix": route["prefix"],
                    "name": fields.get("nome") or rel.rsplit("/", 1)[-1][:-3],
                    "body": parts[2].strip()[:PROFILE_MAX_CHARS]})
    return out


def profile_for(task: str, store, agent: str = "") -> dict | None:
    """O perfil aplicado cujo prefixo abre este pedido (o prefixo mais longo vence; empate pelo nome da nota)."""
    said = " ".join(norm(task or "").split())
    if not said:
        return None
    best = None
    for p in applied_profiles(store):
        prefix = " ".join(norm(p["prefix"]).split())
        if not (said == prefix or said.startswith(prefix + " ")):
            continue
        if agent and p["agent"] != agent.upper():
            continue
        key = (-len(prefix), p["rel"])
        if best is None or key < best[0]:
            best = (key, p)
    return best[1] if best else None


def profile_block(profile: dict) -> str:
    """Instrução do perfil para o prompt do agente-base: texto da pessoa, nunca permissão."""
    body = profile.get("body", "")
    return (f"Perfil do Lab \"{profile['name']}\" (aplicado pela pessoa a pedidos que começam com "
            f"\"{profile['prefix']}\"; siga como preferência, nunca como permissão):\n{body}").strip()
