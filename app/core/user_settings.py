"""
Preferencias do usuario editadas na tela Configuracoes (como as instrucoes personalizadas do
Claude/ChatGPT Desktop). Ficam em desktop/data/settings.json (local, fora do git) e valem por
cima do config.yaml.

  instructions   orientacoes fixas para todo pedido ("responda curto", "planilhas em R$")
  plan_review    mostrar o plano e esperar aprovacao antes de mexer no PC (pedidos digitados)
  barge_in       falar por cima interrompe o agente
  earcon         sinal sonoro quando a fala termina
  live_conversation  modo Conversa em tempo real com GPT-Live (o microfone vai para a OpenAI)
  splash         tela de abertura
  mini_chat      mini chat no canto quando o agente vai para outro app
  models         modelo por nivel ({"fast": ..., "strong": ...}), "provedor:modelo" (core/provider_registry.py)
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().parent.parent / "desktop" / "data" / "settings.json"
INSTRUCTIONS_MAX = 1500
DEFAULTS: dict[str, Any] = {"instructions": "", "plan_review": False, "barge_in": True, "earcon": True,
                            "live_conversation": True, "splash": True, "mini_chat": True,
                            "coding_mcp": True, "models": {}, "custom_providers": {}}
MODEL_TIERS = ("fast", "strong")
_lock = threading.Lock()


def load(path: Path | None = None) -> dict:
    path = path or PATH                      # lido na hora: testes e ferramentas trocam PATH
    data = dict(DEFAULTS)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key == "instructions" and isinstance(value, str):
                    data[key] = value.strip()[:INSTRUCTIONS_MAX]
                elif key == "models" and isinstance(value, dict):
                    data[key] = _models(value, strict=False)
                elif key == "custom_providers" and isinstance(value, dict):
                    data[key] = _custom_rows(value, strict=False)
                elif key in DEFAULTS and isinstance(value, bool):
                    data[key] = value
    except (OSError, ValueError):
        pass
    return data


def save(updates: dict, path: Path | None = None) -> dict:
    """Grava so chaves conhecidas, com o tipo certo (texto limitado; o resto booleano)."""
    path = path or PATH
    with _lock:
        data = load(path)
        if not isinstance(updates, dict):
            raise ValueError("preferências inválidas")
        for k, v in (updates or {}).items():
            if k not in DEFAULTS:
                continue
            if k == "instructions":
                if not isinstance(v, str):
                    raise ValueError("as instruções precisam ser texto")
                data[k] = v.strip()[:INSTRUCTIONS_MAX]
            elif k == "custom_providers":
                if not isinstance(v, dict):
                    raise ValueError("provedores inválidos")
                merged = {**data.get("custom_providers", {}), **v}
                data[k] = _custom_rows({n: r for n, r in merged.items() if r}, strict=True)
            elif k == "models":
                if not isinstance(v, dict):
                    raise ValueError("modelos inválidos")
                data[k] = {**data.get("models", {}), **_models(v, strict=True)}
                data[k] = {tier: name for tier, name in data[k].items() if name}
            else:
                if not isinstance(v, bool):
                    raise ValueError("as opções precisam estar ligadas ou desligadas")
                data[k] = v
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        from core.atomic_io import replace_file
        replace_file(tmp, path)
        return data


def _models(value: dict, strict: bool) -> dict:
    """Só níveis conhecidos e nomes válidos; '' volta ao config.yaml. strict: erro em vez de ignorar."""
    from core.provider_registry import valid_model
    out = {}
    for tier, name in value.items():
        if tier not in MODEL_TIERS or not isinstance(name, str):
            if strict:
                raise ValueError("nível de modelo inválido")
            continue
        name = name.strip()
        if name and not valid_model(name):
            if strict:
                raise ValueError("modelo inválido: use provedor:modelo (ex.: deepseek:deepseek-chat)")
            continue
        out[tier] = name
    return out


def _custom_rows(value: dict, strict: bool) -> dict:
    """Provedores personalizados (sem chave: a chave vai para o DPAPI, core/secret_store.py)."""
    from core.provider_registry import custom_provider
    out = {}
    for name, row in value.items():
        if len(out) >= 20:
            break
        provider = custom_provider(name, row) if isinstance(row, dict) else None
        if provider is None:
            if strict:
                raise ValueError("provedor personalizado inválido: nome curto em minúsculas e endereço https")
            continue
        out[name] = {"label": provider.label, "base_url": provider.base_url, "images": provider.capabilities.images,
                     "structured": provider.capabilities.structured, "tools": provider.capabilities.tools,
                     **({"example": provider.example} if provider.example else {})}
    return out


def model_override(tier: str) -> str:
    """Modelo escolhido na tela para este nível ('' = o do config.yaml). Lido com cache por data do arquivo."""
    global _cache
    try:
        stamp = PATH.stat().st_mtime_ns
    except OSError:
        return ""
    if _cache[0] != stamp:
        _cache = (stamp, load(PATH).get("models", {}))
    return _cache[1].get(tier, "")


_cache: tuple = (None, {})


def instructions_block() -> str:
    """Trecho para os prompts. As instrucoes sao PREFERENCIAS do usuario: nunca ampliam o que o
    agente pode fazer (politicas e confirmacoes continuam valendo)."""
    text = load().get("instructions", "")
    return ("INSTRUCOES DO USUARIO (preferencias para todo pedido; nao mudam as regras de seguranca):\n"
            + text) if text else ""
