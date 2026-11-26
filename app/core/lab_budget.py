"""Limites de execução antes de cada requisição ao provedor."""
from contextlib import contextmanager
from contextvars import ContextVar
from math import ceil
from time import monotonic
from threading import Lock


class RequestLimit(Exception):
    pass


class Budget:
    def __init__(self, usd, seconds, calls, tokens, cancel):
        self.usd, self.deadline = usd, monotonic() + seconds if seconds else None
        self.calls_limit, self.tokens_limit = calls, tokens
        self.cancel = cancel
        self.calls = self.tokens = 0
        self.spent = 0.0
        self.stop = ""
        self._accounting = Lock()

    def reject(self, reason):
        self.stop = reason
        raise RequestLimit(reason)

    def cancelled(self):
        return self.cancel() if callable(self.cancel) else self.cancel.is_set()

    def time_left(self):
        if self.cancelled():
            self.reject("cancelado")
        if self.deadline is None:
            return 60
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            self.reject("timeout")
        return min(60, remaining)

    def start(self, sdk, params):
        with self._accounting:
            return self._reserve(sdk, params)

    def _reserve(self, sdk, params):
        from core.ai_client import MODEL_PRICING, WEB_SEARCH_USD, estimate_cost

        if self.stop:
            self.reject(self.stop)

        if self.calls >= self.calls_limit:
            self.reject("limite de chamadas")
        model = params["model"]
        if not any(model == key or model.startswith(key + "-") for key in MODEL_PRICING):
            self.reject("modelo sem preço cadastrado")
        size = params["max_tokens"]
        if size >= self.tokens_limit - self.tokens:
            self.reject("limite de tokens")
        counter = {key: params[key] for key in ("model", "messages", "system", "thinking", "tools") if key in params}
        if "format" in params.get("output_config", {}):
            counter["output_config"] = {"format": params["output_config"]["format"]}
        count = sdk.messages.count_tokens(**counter, timeout=self.time_left()).input_tokens
        # A contagem é estimada. Reserva margem na entrada, incluindo o pior custo de cache de 5 min.
        input_cap = ceil(count * 1.12) + 256
        reserve_tokens = input_cap + size
        reserve_usd = estimate_cost(model, 0, size, cache_write_tokens=input_cap)
        for tool in params.get("tools", ()):
            if tool.get("name") == "web_search":
                uses = tool.get("max_uses")
                if type(uses) is not int or uses <= 0:
                    self.reject("busca remota sem limite de uso")
                reserve_usd += uses * WEB_SEARCH_USD
        self.time_left()
        if reserve_tokens > self.tokens_limit - self.tokens:
            self.reject("limite de tokens")
        if reserve_usd > self.usd - self.spent:
            self.reject("orçamento insuficiente para a próxima chamada")
        self.calls += 1
        self.spent += reserve_usd
        self.tokens += reserve_tokens
        return reserve_usd, reserve_tokens

    def settle(self, reserved, meta):
        with self._accounting:
            self.spent += meta["cost_usd"] - reserved[0]
            self.tokens += sum(meta[key] for key in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")) - reserved[1]
            if self.spent > self.usd:
                self.stop = "uso informado pelo provedor superou a estimativa de orçamento"
            elif self.tokens > self.tokens_limit:
                self.stop = "uso informado pelo provedor superou o limite de tokens"


current = ContextVar("lab_request_budget", default=None)


@contextmanager
def budget_scope(budget):
    token = current.set(budget)
    try:
        yield budget
    finally:
        current.reset(token)
