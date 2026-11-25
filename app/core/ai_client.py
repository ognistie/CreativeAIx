"""
AI Client v3 — Cliente Anthropic centralizado.

Todas as chamadas ao modelo (agentes, visao, narrador, reparo de JSON)
passam por aqui. Isso garante:
- Custo REAL por modelo, incluindo leitura/escrita de prompt cache
- Prompt caching automatico do system prompt (prefixo estavel)
- `effort` por agente (Sonnet 5: adaptive thinking ligado por padrao)
- Streaming interno (evita timeout HTTP com max_tokens alto)
- Texto extraido so dos blocos `text` (Sonnet 5 devolve blocos `thinking`
  antes do texto — `content[0].text` quebraria)
- Singleton com metricas agregadas
"""

from __future__ import annotations

import copy
import os
import threading
import time
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional

from anthropic import Anthropic, APIError, Timeout

logger = logging.getLogger("ai_client")

_call_observation: ContextVar[Optional[list]] = ContextVar("ai_call_observation", default=None)


@contextmanager
def observe_calls():
    """Mede apenas chamadas do fluxo atual, inclusive reparos de JSON."""
    rows = []
    token = _call_observation.set(rows)
    try:
        yield rows
    finally:
        _call_observation.reset(token)


# Precos por modelo (USD por 1M tokens). Prefixo mais longo vence, entao cada versao nova precisa da
# propria linha: sem "claude-sonnet-5-5", o Sonnet 5.5 caia no preco do "claude-sonnet-5".
# "cache_read" (opcional) = preco proprio da leitura de cache, quando nao e 10% do input.
# Fonte: tabela de modelos da Anthropic (cache de 2026-11-03).
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-fable-5-2":  {"input": 8.00, "output": 40.00, "cache_read": 0.20},
    "claude-fable-5":    {"input": 10.00, "output": 50.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.10},
    "claude-sonnet-5":   {"input": 2.00, "output": 10.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4":   {"input": 3.00, "output": 15.00},
    "claude-haiku-5-5":  {"input": 0.10, "output": 0.50},
    "claude-haiku-4-5":  {"input": 1.00, "output": 5.00},
    "claude-opus-5-5":   {"input": 4.00, "output": 20.00, "cache_read": 0.20},
    "claude-opus-5":     {"input": 5.00, "output": 25.00},
    "claude-opus-4-8":   {"input": 5.00, "output": 25.00},
    "claude-opus-4-7":   {"input": 5.00, "output": 25.00},
    "claude-opus-4-6":   {"input": 5.00, "output": 25.00},
    "claude-opus-4":     {"input": 15.00, "output": 75.00},
}

# Busca na web do servidor (web_search): US$ 10 por 1.000 buscas, alem dos tokens dos resultados.
WEB_SEARCH_USD = 0.01

# Multiplicadores do prompt cache sobre o preco de input (TTL de 5 min).
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

# Modelos que aceitam `output_config.effort`. Em modelos fora desta lista
# o parametro e omitido (ex.: Haiku 4.5 devolve 400 com effort).
_EFFORT_MODELS = (
    "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-opus-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-fable", "claude-haiku-5-5",
)


def _pricing_for(model: str) -> dict[str, float]:
    """Pricing do modelo; se desconhecido, usa Sonnet 5."""
    m = (model or "").lower()
    matches = [k for k in MODEL_PRICING if m.startswith(k)]
    if matches:
        return MODEL_PRICING[max(matches, key=len)]
    return MODEL_PRICING["claude-sonnet-5"]


# Modelos que aceitam desligar o raciocinio (thinking disabled). Sonnet 5.5, Opus 5.5 e Fable
# recusam com 400: nesses o "off" vira so effort baixo.
_THINKING_OFF_MODELS = ("claude-opus-4-7", "claude-opus-4-8", "claude-haiku-5-5")


def can_disable_thinking(model: str) -> bool:
    m = (model or "").lower()
    return m == "claude-sonnet-5" or m.startswith(_THINKING_OFF_MODELS)


def thinking_off_for(agent: str) -> bool:
    """config.yaml > agent_thinking: <agente>: off -> resposta direta, sem raciocinio
    (rotas curtas e sensiveis a latencia: entender a fala, rotear, passo do piloto)."""
    if not agent:
        return False
    try:
        from core.config import get_config
        v = get_config().get(f"agent_thinking.{agent.lower()}")
    except Exception:
        return False
    return str(v).lower() in ("off", "false", "0", "no")


def _supports_effort(model: str) -> bool:
    return (model or "").lower().startswith(_EFFORT_MODELS)


def estimate_cost(model: str, input_tokens: int, output_tokens: int,
                  cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float:
    """Custo em USD de uma chamada, contando o prompt cache."""
    p = _pricing_for(model)
    cache_read_price = p.get("cache_read", p["input"] * CACHE_READ_MULTIPLIER)
    return (
        input_tokens * p["input"]
        + cache_write_tokens * p["input"] * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * cache_read_price
        + output_tokens * p["output"]
    ) / 1_000_000


# ─────────────────────────────────────────────────────────────────────
#  Singleton
# ─────────────────────────────────────────────────────────────────────

_instance: Optional["AIClient"] = None


def get_client() -> "AIClient":
    global _instance
    if _instance is None:
        _instance = AIClient()
    return _instance


class LLMCancelled(RuntimeError):
    """A tarefa que pediu a chamada foi cancelada, ou a chamada passou do prazo total."""


# Cancelamento por thread: so a thread da tarefa e interrompida; a voz e a resposta final (outras threads) nao
_scope = threading.local()


def bind_cancel(should_stop) -> None:
    """A thread atual passa a abortar chamadas ao modelo quando should_stop() for verdadeiro (None desliga)."""
    _scope.should_stop = should_stop


def call_limit_s() -> float:
    try:
        from core.config import get_config
        return max(30.0, float(get_config().get("limits.llm_call_s", 300)))
    except Exception:
        return 300.0


class AIClient:
    """Cliente centralizado para a API Anthropic."""

    on_progress = None   # callback de andamento (ver __init__)

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY nao configurada no .env")

        # O SDK ja faz retry com backoff em 408/409/429/5xx e erros de rede.
        # Timeout de leitura curto: em streaming ele vale ENTRE pedacos da
        # resposta. Sem ele, uma conexao engasgada deixava a tarefa parada
        # em "Analisando" por ate 10 minutos (default do SDK).
        self._client = Anthropic(
            api_key=api_key, max_retries=2,
            timeout=Timeout(180.0, connect=10.0, read=60.0),
        )
        self._metrics: dict[str, Any] = {
            "total_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cache_read_tokens": 0,
            "total_cache_write_tokens": 0,
            "total_cost_usd": 0.0,
            "total_llm_ms": 0,      # tempo esperando o modelo (latencia percebida)
            "calls_by_model": {},   # {model_short: {calls, in_tokens, out_tokens, cost_usd}}
            "calls_by_agent": {},   # {agent: {calls, cost_usd}}
            "errors": 0,
            "truncated": 0,
        }
        # A tarefa, a resposta final (thread propria) e a voz chamam o modelo ao mesmo tempo: sem trava,
        # dois `+=` simultaneos perdiam chamadas e custo no total mostrado na tela.
        self._metrics_lock = threading.Lock()
        # Andamento de respostas longas (quem usa: a UI). Chamado com
        # (agente, "thinking"|"writing", caracteres de texto ja gerados).
        self.on_progress = None
        logger.info("AIClient v3 inicializado (cache + effort + custo real)")

    # ─── API publica ───────────────────────────────────────────────

    @property
    def metrics(self) -> dict[str, Any]:
        """Copia profunda — quem guarda um snapshot nao ve alteracoes futuras."""
        with self._lock_for_metrics():
            snapshot = copy.deepcopy(self._metrics)
        snapshot["total_cost_usd"] = round(snapshot["total_cost_usd"], 6)
        return snapshot

    def message(self, model: str, system: str, user_content,
                max_tokens: int = 8000, images=None,
                effort: Optional[str] = None, agent: str = "", json_schema: Optional[dict] = None) -> str:
        """Wrapper que retorna apenas o texto."""
        return self.message_with_meta(
            model=model, system=system, user_content=user_content,
            max_tokens=max_tokens, images=images, effort=effort, agent=agent, json_schema=json_schema,
        )["text"]

    def message_with_meta(self, model: str, system: str, user_content,
                          max_tokens: int = 8000, images=None,
                          effort: Optional[str] = None,
                          agent: str = "", json_schema: Optional[dict] = None) -> dict[str, Any]:
        """
        Envia mensagem e retorna {text, model_used, input_tokens,
        output_tokens, cache_read_tokens, cache_write_tokens, cost_usd,
        duration_ms, stop_reason}.
        """
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user",
                          "content": self._build_content(user_content, images)}],
        }
        if system:
            # System prompt e o prefixo estavel de cada agente: marcado para
            # cache. Abaixo do minimo cacheavel (1024 tokens no Sonnet 5) a
            # API simplesmente nao cacheia — sem custo extra.
            params["system"] = [{"type": "text", "text": system,
                                 "cache_control": {"type": "ephemeral"}}]
        if effort and _supports_effort(model):
            params["output_config"] = {"effort": effort}
        if json_schema is not None:
            params.setdefault('output_config', {})['format'] = {'type': 'json_schema', 'schema': json_schema}
        if thinking_off_for(agent) and can_disable_thinking(model) and not images:
            # Sem raciocinio: a resposta sai direto (rotas curtas). Com imagem fica o padrao.
            params["thinking"] = {"type": "disabled"}

        start = time.time()
        from core.lab_budget import current
        budget = current.get()
        client = self._client
        if budget is not None:
            client = client.with_options(max_retries=0)
            reserved = budget.start(client, params)
            params["timeout"] = budget.time_left()
        try:
            with client.messages.stream(**params) as stream:
                if budget is not None:
                    for _ in stream:
                        budget.time_left()
                elif self.on_progress or callable(getattr(_scope, "should_stop", None)):
                    # Consome o stream aqui: entre um pedaco e outro confere o cancelamento da tarefa desta
                    # thread e o prazo total (antes o Parar so valia depois da resposta inteira)
                    self._relay_progress(stream, agent, start)
                resp = stream.get_final_message()
        except APIError as e:
            self._count("errors")
            logger.error(f"API erro ({agent or 'sem agente'}): {e}")
            raise

        duration_ms = round((time.time() - start) * 1000)

        if resp.stop_reason == "refusal":
            self._count("errors")
            if budget is not None:
                budget.settle(reserved, self._record_success(resp, model, duration_ms, agent))
            details = getattr(resp, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise RuntimeError(f"Modelo recusou a tarefa (categoria: {category})")
        if resp.stop_reason == "max_tokens":
            self._count("truncated")
            logger.warning(f"Resposta truncada em max_tokens={max_tokens} "
                           f"({agent or model})")

        meta = self._record_success(resp, model, duration_ms, agent)
        if budget is not None:
            budget.settle(reserved, meta)
        observer = _call_observation.get()
        if observer is not None:
            observer.append({
                "agent": agent, "model": getattr(resp, "model", None) or model, "max_tokens": max_tokens,
                "effort": params.get("output_config", {}).get("effort"),
                "tokens": sum(meta[key] for key in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")),
                "cost_usd": meta["cost_usd"],
            })
        return meta

    def converse(self, model: str, system: str, messages: list, tools: Optional[list] = None,
                 max_tokens: int = 16000, effort: Optional[str] = None, agent: str = "",
                 on_text=None, should_stop=None):
        """Uma volta de conversa com historico e ferramentas (o laco de ferramentas fica com quem chama).

        Diferente de `message`: recebe a lista de mensagens inteira (multi-turno) e devolve a Message
        final da API (blocos text/tool_use), para o chamador executar as ferramentas e continuar.
        on_text(trecho) recebe o texto conforme chega; should_stop() True interrompe o streaming (a
        resposta parcial ainda volta, com stop_reason "cancelled").
        Cache: system marcado e cache automatico no fim do historico (o prefixo cresce a cada volta)."""
        params: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages,
                                  "cache_control": {"type": "ephemeral"}}
        if system:
            params["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        if tools:
            params["tools"] = tools
        if effort and _supports_effort(model):
            params["output_config"] = {"effort": effort}
        start = time.time()
        cancelled = False
        # Mesmo cancelamento da thread da tarefa (bind_cancel) e o mesmo prazo total das outras chamadas
        thread_stop = getattr(_scope, "should_stop", None)
        limit = call_limit_s()
        try:
            with self._client.messages.stream(**params) as stream:
                for event in stream:
                    if (should_stop is not None and should_stop()) or (callable(thread_stop) and thread_stop()):
                        cancelled = True
                        break
                    if time.time() - start > limit:
                        raise LLMCancelled(f"O modelo passou de {limit:.0f} s sem terminar; parei para não travar.")
                    if on_text is not None and getattr(event, "type", "") == "text":
                        try:
                            on_text(event.text)
                        except Exception:
                            pass                         # a tela nunca derruba a resposta
                resp = None if cancelled else stream.get_final_message()
        except APIError as e:
            self._count("errors")
            logger.error(f"API erro ({agent or 'sem agente'}): {e}")
            raise
        if resp is None:
            return None
        duration_ms = round((time.time() - start) * 1000)
        if resp.stop_reason == "max_tokens":
            self._count("truncated")
        elif resp.stop_reason == "refusal":
            self._count("errors")
        self._record_success(resp, model, duration_ms, agent)
        return resp

    # ─── Helpers internos ──────────────────────────────────────────

    def _lock_for_metrics(self) -> threading.Lock:
        lock = getattr(self, "_metrics_lock", None)
        if lock is None:                      # testes montam o cliente com __new__
            lock = self._metrics_lock = threading.Lock()
        return lock

    def _count(self, key: str) -> None:
        with self._lock_for_metrics():
            self._metrics[key] = self._metrics.get(key, 0) + 1

    def _relay_progress(self, stream, agent: str, start: float) -> None:
        """Repassa o andamento do streaming (no maximo ~1x/s, so em respostas
        que passam de 1,5 s). Erro no callback nunca afeta a resposta."""
        chars, thinking, last = 0, False, 0.0
        stop = getattr(_scope, "should_stop", None)
        limit = call_limit_s()
        for event in stream:
            if callable(stop) and stop():
                raise LLMCancelled("Chamada ao modelo interrompida: a tarefa foi cancelada.")
            if time.time() - start > limit:
                raise LLMCancelled(f"O modelo passou de {limit:.0f} s sem terminar; parei para não travar.")
            if not self.on_progress or getattr(event, "type", "") != "content_block_delta":
                continue
            kind = getattr(event.delta, "type", "")
            if kind == "thinking_delta":
                thinking = True
            elif kind == "text_delta":
                chars += len(event.delta.text or "")
                thinking = False
            else:
                continue
            now = time.time()
            if now - last >= 0.9 and now - start >= 1.5:
                last = now
                try:
                    self.on_progress(agent, "thinking" if thinking else "writing", chars)
                except Exception:
                    pass

    def _build_content(self, user_content, images) -> list:
        """Monta content blocks (imagens opcionais + texto)."""
        if not isinstance(user_content, str):
            return user_content
        content: list = []
        for img in images or []:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("media_type", "image/png"),
                    "data": img["base64"],
                },
            })
        content.append({"type": "text", "text": user_content})
        return content

    def _record_success(self, resp, model: str, duration_ms: int,
                        agent: str) -> dict[str, Any]:
        """Registra metricas e retorna meta-dict."""
        usage = resp.usage
        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        cost = estimate_cost(model, input_tokens, output_tokens,
                             cache_read, cache_write)
        # Busca na web (ferramenta do servidor, usada pela conversa): cobrada por busca, fora dos tokens
        server_use = getattr(usage, "server_tool_use", None)
        searches = getattr(server_use, "web_search_requests", 0) if server_use is not None else 0
        if isinstance(searches, int) and searches > 0:
            cost += searches * WEB_SEARCH_USD

        short = self._short_name(model)
        with self._lock_for_metrics():
            m = self._metrics
            m["total_calls"] += 1
            m["total_input_tokens"] += input_tokens
            m["total_output_tokens"] += output_tokens
            m["total_cache_read_tokens"] += cache_read
            m["total_cache_write_tokens"] += cache_write
            m["total_cost_usd"] += cost
            m["total_llm_ms"] = m.get("total_llm_ms", 0) + duration_ms

            per = m["calls_by_model"].setdefault(
                short, {"calls": 0, "in_tokens": 0, "out_tokens": 0, "cost_usd": 0.0}
            )
            per["calls"] += 1
            per["in_tokens"] += input_tokens
            per["out_tokens"] += output_tokens
            per["cost_usd"] = round(per["cost_usd"] + cost, 6)

            if agent:
                per_agent = m["calls_by_agent"].setdefault(
                    agent, {"calls": 0, "cost_usd": 0.0, "ms": 0}
                )
                per_agent["calls"] += 1
                per_agent["ms"] = per_agent.get("ms", 0) + duration_ms
                per_agent["cost_usd"] = round(per_agent["cost_usd"] + cost, 6)

        # Sonnet 5 devolve blocos `thinking` antes do texto — so o texto importa.
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        ).strip()
        logger.debug(
            f"API {short} [{agent}] | in={input_tokens} cache_r={cache_read} "
            f"cache_w={cache_write} out={output_tokens} ${cost:.5f} | {duration_ms}ms"
        )

        return {
            "text": text,
            "model_used": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "cost_usd": round(cost, 6),
            "duration_ms": duration_ms,
            "stop_reason": resp.stop_reason,
        }

    @staticmethod
    def _short_name(model: str) -> str:
        """claude-sonnet-5 -> sonnet-5 ; claude-haiku-4-5-20251001 -> haiku-4-5"""
        parts = model.split("-")
        if len(parts) >= 4 and parts[3].isdigit() and len(parts[3]) <= 2:
            return "-".join(parts[1:4])
        if len(parts) >= 3:
            return "-".join(parts[1:3])
        return model
