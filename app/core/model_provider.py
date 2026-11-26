"""Contrato dos blocos que agentes consomem e transporte local do Ollama."""
from dataclasses import dataclass, field
import json
import re
from uuid import uuid4

import httpx


class ProviderError(RuntimeError):
    """Falha no transporte ou no protocolo, sem conteúdo do pedido."""


@dataclass(frozen=True)
class ModelCapabilities:
    streaming: bool = True
    tools: bool = True
    structured: bool = True
    images: bool = True
    count_tokens: bool = False
    server_tools: bool = False


ANTHROPIC_CAPABILITIES = ModelCapabilities(count_tokens=True, server_tools=True)


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ModelBlock:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    model: str
    content: list[ModelBlock]
    usage: ModelUsage
    stop_reason: str


def local_model(model: str) -> bool:
    return model.startswith("ollama:")


def _field(block, key, default=None):
    return block.get(key, default) if isinstance(block, dict) else getattr(block, key, default)


def _messages(system, messages):
    rows = [{"role": "system", "content": system}] if system else []
    names = {}
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            rows.append({"role": message["role"], "content": content})
            continue
        row = {"role": message["role"], "content": ""}
        results = []
        for block in content:
            kind = _field(block, "type")
            if kind == "text":
                row["content"] += _field(block, "text", "")
            elif kind == "image":
                source = _field(block, "source", {})
                if source.get("type") != "base64":
                    raise ProviderError("O adaptador local exige imagens incorporadas.")
                row.setdefault("images", []).append(source["data"])
            elif kind == "tool_use":
                name = _field(block, "name")
                names[_field(block, "id")] = name
                row.setdefault("tool_calls", []).append({"type": "function",
                    "function": {"name": name, "arguments": _field(block, "input", {})}})
            elif kind == "tool_result":
                name = names.get(_field(block, "tool_use_id"))
                value = _field(block, "content", "")
                if name is None or not isinstance(value, str):
                    raise ProviderError("Resultado de ferramenta local sem chamada ou texto associado.")
                results.append({"role": "tool", "tool_name": name, "content": value})
            elif kind != "thinking":
                raise ProviderError("Bloco incompatível com o modelo local.")
        if row["content"] or "images" in row or "tool_calls" in row or not results:
            rows.append(row)
        rows.extend(results)
    return rows


class OllamaProvider:
    capabilities = ModelCapabilities()
    url = "http://127.0.0.1:11434/api/chat"

    def __init__(self, transport=None):
        self.transport = transport

    def generate(self, model, system, messages, *, max_tokens, tools=(), schema=None, timeout=60,
                 on_text=None, cancelled=lambda: False) -> ModelResponse | None:
        tag = model.removeprefix("ollama:")
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]+", tag) or "cloud" in tag.casefold():
            raise ProviderError("Informe uma tag local do Ollama.")
        payload = {"model": tag, "messages": _messages(system, messages), "stream": True,
                   "options": {"num_predict": max_tokens}}
        if schema is not None:
            payload["format"] = schema
        names = set()
        if tools:
            if any("input_schema" not in tool for tool in tools):
                raise ProviderError("O modelo local aceita somente ferramentas executadas pelo aplicativo.")
            payload["tools"] = [{"type": "function", "function": {
                "name": tool["name"], "description": tool.get("description", ""),
                "parameters": tool["input_schema"]}} for tool in tools]
            names = {tool["name"] for tool in tools}
        text, calls = [], {}
        if cancelled():
            return None
        try:
            with httpx.Client(transport=self.transport, timeout=timeout, trust_env=False,
                              follow_redirects=False) as client:
                with client.stream("POST", self.url, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if cancelled():
                            return None
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise ProviderError("O modelo local recusou a chamada.")
                        message = chunk.get("message", {})
                        piece = message.get("content", "")
                        if piece:
                            text.append(piece)
                            if on_text is not None:
                                on_text(piece)
                        for i, tool in enumerate(message.get("tool_calls", ())):
                            fn = tool["function"]
                            if fn["name"] not in names or not isinstance(fn["arguments"], dict):
                                raise ProviderError("Chamada de ferramenta local incompatível com o contrato.")
                            index = fn.get("index")
                            key = index if type(index) is int else len(calls) + i
                            calls[key] = ModelBlock("tool_use", id=uuid4().hex,
                                                    name=fn["name"], input=fn["arguments"])
                        if chunk.get("done") is True:
                            if chunk.get("done_reason") == "length":
                                calls.clear()
                            reason = ("max_tokens" if chunk.get("done_reason") == "length"
                                      else "tool_use" if calls else "end_turn")
                            blocks = ([ModelBlock("text", text="".join(text))] if text else []) + list(calls.values())
                            usage = ModelUsage(int(chunk["prompt_eval_count"]), int(chunk["eval_count"]))
                            return ModelResponse(model, blocks, usage, reason)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ProviderError(f"Falha no provedor local ({type(error).__name__}).") from error
        raise ProviderError("Fluxo local encerrado sem resultado final.")


# ── Provedores com chat compatível com OpenAI (DeepSeek, OpenAI, OpenRouter, Groq, LM Studio...) ──
def _openai_messages(system, messages, images: bool):
    """Mensagens no formato Anthropic (o que os agentes montam) -> formato chat/completions."""
    rows = [{"role": "system", "content": system}] if system else []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            rows.append({"role": message["role"], "content": content})
            continue
        parts, calls, results = [], [], []
        for block in content:
            kind = _field(block, "type")
            if kind == "text":
                parts.append({"type": "text", "text": _field(block, "text", "")})
            elif kind == "image":
                source = _field(block, "source", {})
                if not images:
                    raise ProviderError("Este modelo não aceita imagens; escolha um modelo com visão.")
                if source.get("type") != "base64":
                    raise ProviderError("O adaptador exige imagens incorporadas.")
                parts.append({"type": "image_url", "image_url": {
                    "url": f"data:{source.get('media_type', 'image/png')};base64,{source['data']}"}})
            elif kind == "tool_use":
                calls.append({"id": _field(block, "id"), "type": "function", "function": {
                    "name": _field(block, "name"),
                    "arguments": json.dumps(_field(block, "input", {}), ensure_ascii=False)}})
            elif kind == "tool_result":
                value = _field(block, "content", "")
                if not isinstance(value, str):
                    value = "".join(_field(b, "text", "") for b in value if _field(b, "type") == "text")
                results.append({"role": "tool", "tool_call_id": _field(block, "tool_use_id"), "content": value})
            elif kind not in ("thinking", "redacted_thinking"):
                raise ProviderError("Bloco incompatível com este provedor (ferramenta do servidor da Anthropic).")
        if message["role"] == "assistant":
            row = {"role": "assistant", "content": "".join(p.get("text", "") for p in parts) or None}
            if calls:
                row["tool_calls"] = calls
            rows.append(row)
        else:
            rows.extend(results)
            if parts:
                only_text = all(p["type"] == "text" for p in parts)
                rows.append({"role": "user", "content": "".join(p["text"] for p in parts) if only_text else parts})
    return rows


def _status_error(code: int) -> str:
    if code in (401, 403):
        return "Chave recusada pelo provedor (confira a chave e os créditos)."
    if code == 402:
        return "O provedor recusou por falta de créditos."
    if code == 404:
        return "Modelo ou endereço não encontrado nesse provedor."
    if code == 429:
        return "Limite de uso do provedor atingido; tente de novo em instantes."
    return ""


class OpenAICompatProvider:
    """Chat/completions em streaming (SSE) com ferramentas do app, JSON, uso de tokens e cancelamento.

    Ferramentas do servidor da Anthropic (busca na web) não existem aqui: quem chama precisa retirá-las.
    """

    def __init__(self, transport=None):
        self.transport = transport

    def _client(self, timeout):
        return httpx.Client(transport=self.transport, timeout=timeout, trust_env=False, follow_redirects=False)

    def generate(self, model, system, messages, *, base_url, api_key, capabilities, max_tokens, tools=(),
                 schema=None, timeout=60, on_text=None, cancelled=lambda: False) -> ModelResponse | None:
        rows = _openai_messages(system, messages, capabilities.images)
        payload = {"model": model, "messages": rows, "stream": True, "max_tokens": max_tokens,
                   "stream_options": {"include_usage": True}}
        if schema is not None:
            if capabilities.structured:
                payload["response_format"] = {"type": "json_schema",
                                              "json_schema": {"name": "saida", "schema": schema}}
            else:
                payload["response_format"] = {"type": "json_object"}
                rows.insert(0, {"role": "system", "content":
                                "Responda somente com um objeto JSON válido neste esquema: " + json.dumps(schema)})
        names = set()
        if tools:
            if not capabilities.tools:
                raise ProviderError("Este modelo não aceita ferramentas; escolha outro para esta função.")
            if any("input_schema" not in tool for tool in tools):
                raise ProviderError("Este provedor aceita somente ferramentas executadas pelo aplicativo.")
            payload["tools"] = [{"type": "function", "function": {
                "name": tool["name"], "description": tool.get("description", ""),
                "parameters": tool["input_schema"]}} for tool in tools]
            names = {tool["name"] for tool in tools}
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        text, calls, usage, finish = [], {}, None, ""
        completed = False
        if cancelled():
            return None
        try:
            with self._client(timeout) as client:
                with client.stream("POST", base_url.rstrip("/") + "/chat/completions", json=payload,
                                   headers=headers) as response:
                    known = _status_error(response.status_code)
                    if known:
                        raise ProviderError(known)
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if cancelled():
                            return None
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            completed = True
                            break
                        chunk = json.loads(data)
                        if chunk.get("error"):
                            raise ProviderError("O provedor recusou a chamada.")
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        for choice in chunk.get("choices") or ():
                            delta = choice.get("delta") or {}
                            piece = delta.get("content") or ""
                            if piece:
                                text.append(piece)
                                if on_text is not None:
                                    on_text(piece)
                            for call in delta.get("tool_calls") or ():
                                slot = calls.setdefault(call.get("index", len(calls)),
                                                        {"id": "", "name": "", "arguments": ""})
                                fn = call.get("function") or {}
                                slot["id"] = call.get("id") or slot["id"]
                                slot["name"] += fn.get("name") or ""
                                slot["arguments"] += fn.get("arguments") or ""
                            finish = choice.get("finish_reason") or finish
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ProviderError(f"Falha no provedor ({type(error).__name__}).") from error
        if not completed or finish not in ("stop", "tool_calls", "length", "content_filter"):
            raise ProviderError("Fluxo do provedor encerrado sem confirmação de conclusão.")
        if calls and finish not in ("tool_calls", "length"):
            raise ProviderError("Fluxo terminou sem confirmar a chamada de ferramenta.")
        if finish == "content_filter":
            return ModelResponse(model, [], ModelUsage(0, 0), "refusal")
        blocks = [ModelBlock("text", text="".join(text))] if text else []
        if finish != "length":                     # chamada cortada pelo limite nunca é executada
            for slot in calls.values():
                if slot["name"] not in names:
                    raise ProviderError("O modelo chamou uma ferramenta que não foi oferecida.")
                try:
                    arguments = json.loads(slot["arguments"] or "{}")
                except ValueError as error:
                    raise ProviderError("Argumentos de ferramenta inválidos vindos do modelo.") from error
                if not isinstance(arguments, dict):
                    raise ProviderError("Argumentos de ferramenta inválidos vindos do modelo.")
                blocks.append(ModelBlock("tool_use", id=slot["id"] or uuid4().hex, name=slot["name"],
                                         input=arguments))
        reason = ("max_tokens" if finish == "length" else "tool_use"
                  if any(b.type == "tool_use" for b in blocks) else "end_turn")
        usage = usage or {}
        return ModelResponse(model, blocks, ModelUsage(int(usage.get("prompt_tokens") or 0),
                                                       int(usage.get("completion_tokens") or 0)), reason)

    def list_models(self, *, base_url, api_key, timeout=15) -> list[str]:
        """GET /models (gratuito na maioria dos provedores): confirma a chave e lista os modelos."""
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with self._client(timeout) as client:
                response = client.get(base_url.rstrip("/") + "/models", headers=headers)
                known = _status_error(response.status_code)
                if known:
                    raise ProviderError(known)
                response.raise_for_status()
                rows = response.json().get("data") or []
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            raise ProviderError(f"Não deu para falar com o provedor ({type(error).__name__}).") from error
        return sorted({str(r.get("id")) for r in rows if isinstance(r, dict) and r.get("id")})[:300]
