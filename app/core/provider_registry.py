"""Registro de provedores de modelo: qual endereço, qual chave e o que cada um suporta.

Um modelo é escolhido como "provedor:modelo" (ex.: "deepseek:deepseek-chat", "openrouter:qwen/qwen3-coder",
"ollama:qwen3"). Sem prefixo, continua sendo um modelo da Anthropic (o padrão do app). Os provedores
prontos falam o formato de chat compatível com OpenAI; outros entram por config.yaml em providers.custom
com o mesmo formato. Preços não são inventados: sem preço em providers.prices o custo fica desconhecido
e a chamada é recusada sob orçamento estrito.
"""
from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, replace
from typing import Optional
from urllib.parse import urlsplit

from core.model_provider import ModelCapabilities

_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,159}")
_NAME = re.compile(r"[a-z][a-z0-9_-]{1,31}")


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    kind: str                     # anthropic | ollama | openai_compat
    base_url: str = ""
    key_env: str = ""             # variável do .env aceita como alternativa à chave guardada
    capabilities: ModelCapabilities = ModelCapabilities()
    signup: str = ""              # onde a pessoa cria a chave / compra créditos
    example: str = ""             # modelo de exemplo para a tela

    @property
    def local(self) -> bool:
        """Servidor na própria máquina (loopback): não sai para a internet."""
        host = urlsplit(self.base_url).hostname or ""
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    @property
    def needs_key(self) -> bool:
        return self.kind != "ollama" and not self.local


_TEXT_TOOLS = ModelCapabilities(images=False, structured=False)
PRESETS: dict[str, Provider] = {p.name: p for p in (
    Provider("anthropic", "Anthropic (Claude)", "anthropic", key_env="ANTHROPIC_API_KEY",
             capabilities=ModelCapabilities(count_tokens=True, server_tools=True),
             signup="https://console.anthropic.com", example="claude-sonnet-5"),
    Provider("openai", "OpenAI", "openai_compat", "https://api.openai.com/v1", "OPENAI_API_KEY",
             ModelCapabilities(), "https://platform.openai.com/api-keys", "gpt-5-mini"),
    Provider("deepseek", "DeepSeek", "openai_compat", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY",
             _TEXT_TOOLS, "https://platform.deepseek.com/api_keys", "deepseek-chat"),
    Provider("openrouter", "OpenRouter (vários modelos com um crédito)", "openai_compat",
             "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", ModelCapabilities(structured=False),
             "https://openrouter.ai/keys", "qwen/qwen3-coder"),
    Provider("groq", "Groq", "openai_compat", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
             _TEXT_TOOLS, "https://console.groq.com/keys", "llama-3.3-70b-versatile"),
    Provider("mistral", "Mistral", "openai_compat", "https://api.mistral.ai/v1", "MISTRAL_API_KEY",
             ModelCapabilities(structured=False), "https://console.mistral.ai/api-keys", "mistral-large-latest"),
    Provider("together", "Together AI", "openai_compat", "https://api.together.xyz/v1", "TOGETHER_API_KEY",
             _TEXT_TOOLS, "https://api.together.ai/settings/api-keys", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    Provider("ollama", "Ollama (local)", "ollama", "http://127.0.0.1:11434",
             capabilities=ModelCapabilities(), signup="https://ollama.com/download", example="qwen3"),
    Provider("lmstudio", "LM Studio (local)", "openai_compat", "http://127.0.0.1:1234/v1",
             capabilities=ModelCapabilities(images=False, structured=False),
             signup="https://lmstudio.ai", example="qwen3-8b"),
)}


def custom_provider(name: str, row: dict) -> Optional[Provider]:
    """Um provedor personalizado válido, ou None. HTTPS; HTTP só no próprio computador (chave em texto puro
    pela internet é recusada). O nome não pode tomar o lugar de um provedor pronto."""
    if not isinstance(name, str) or not _NAME.fullmatch(name) or name in PRESETS or not isinstance(row, dict):
        return None
    base = str(row.get("base_url") or "").strip()
    parts = urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password \
            or parts.query or parts.fragment or len(base) > 300:
        return None
    key_env = str(row.get("key_env") or "")
    if key_env and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,59}", key_env):
        return None
    caps = ModelCapabilities(images=row.get("images") is True, structured=row.get("structured") is True,
                             tools=row.get("tools", True) is not False)
    provider = Provider(name, str(row.get("label") or name).strip()[:60] or name, "openai_compat",
                        base.rstrip("/"), key_env, caps, example=str(row.get("example") or "")[:80])
    if parts.scheme == "http" and not provider.local:
        return None
    return provider


def _custom() -> dict[str, Provider]:
    """providers.custom no config.yaml e os criados em Configurações > Modelos (settings.json)."""
    from core.config import get_config
    from core.user_settings import PATH, load
    rows = dict(get_config().get("providers.custom", {}) or {})
    try:
        rows.update(load(PATH).get("custom_providers", {}))
    except Exception:
        pass
    out = {}
    for name, row in rows.items():
        provider = custom_provider(name, row)
        if provider is not None:
            out[name] = provider
    return out


def providers() -> dict[str, Provider]:
    return {**PRESETS, **_custom()}


def split(model: str) -> tuple[Provider, str]:
    """'deepseek:deepseek-chat' -> (DeepSeek, 'deepseek-chat'); sem prefixo conhecido -> Anthropic."""
    model = (model or "").strip()
    head, sep, rest = model.partition(":")
    known = providers()
    if sep and head in known and head != "anthropic":
        if not _MODEL_ID.fullmatch(rest):
            raise ValueError("Nome de modelo inválido.")
        return known[head], rest
    if sep and head == "anthropic":
        return known["anthropic"], rest
    return known["anthropic"], model


def provider_of(model: str) -> Provider:
    try:
        return split(model)[0]
    except ValueError:
        return PRESETS["anthropic"]


def valid_model(model: str) -> bool:
    try:
        provider, name = split(model)
    except ValueError:
        return False
    return bool(_MODEL_ID.fullmatch(name)) and (provider.name != "anthropic" or name.startswith("claude"))


def api_key(provider: Provider) -> str:
    """Chave guardada pelo app (DPAPI) ou, se não houver, a do .env. Nunca é registrada."""
    if not provider.needs_key and provider.kind != "anthropic":
        return ""
    from core import secret_store
    try:
        stored = secret_store.load(provider.name)
    except secret_store.SecretStoreError:
        stored = ""
    return stored or (os.getenv(provider.key_env, "").strip() if provider.key_env else "")


def configured(provider: Provider) -> bool:
    if not provider.needs_key and provider.kind != "anthropic":
        return True
    from core import secret_store
    try:
        if secret_store.has(provider.name):
            return True
    except secret_store.SecretStoreError:
        pass
    return bool(provider.key_env and os.getenv(provider.key_env, "").strip())


def price(model: str) -> Optional[tuple[float, float]]:
    """(US$ por milhão de tokens de entrada, de saída) informado pela pessoa em providers.prices."""
    from core.config import get_config
    row = (get_config().get("providers.prices", {}) or {}).get(model)
    if (isinstance(row, (list, tuple)) and len(row) == 2
            and all(isinstance(v, (int, float)) and v >= 0 for v in row)):
        return float(row[0]), float(row[1])
    return None


def capabilities(model: str) -> ModelCapabilities:
    from core.config import get_config
    provider = provider_of(model)
    record = (get_config().get("providers.model_capabilities", {}) or {}).get(model)
    if record is None:
        return replace(provider.capabilities)
    fields = ModelCapabilities.__dataclass_fields__
    if not isinstance(record, dict) or set(record) - set(fields) or any(type(v) is not bool for v in record.values()):
        raise ValueError("Registro de capacidades do modelo inválido.")
    return replace(provider.capabilities, **record)
