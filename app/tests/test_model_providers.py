"""Provedores de modelo além da Anthropic: DeepSeek, OpenAI, OpenRouter, Groq, Ollama, LM Studio e personalizados.

Contrato do adaptador compatível com OpenAI (streaming, ferramentas, JSON, uso, erros, cancelamento), roteamento
pelo prefixo "provedor:modelo", modo offline, chave protegida pelo DPAPI e a Bridge que nunca devolve a chave.
Transportes simulados (httpx.MockTransport): nenhuma chamada sai da máquina.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import provider_registry as R
from core import secret_store
from core.ai_client import AIClient
from core.lab_budget import Budget, RequestLimit, budget_scope
from core.model_provider import ModelCapabilities, OpenAICompatProvider, ProviderError

FAKE_KEY = "sk-test-1234567890abcdef"


def sse(*chunks, done=True):
    lines = [f"data: {json.dumps(c)}" for c in chunks] + (["data: [DONE]"] if done else [])
    return "\n\n".join(lines) + "\n\n"


class Server:
    """Provedor simulado: guarda as requisições e responde o corpo SSE configurado."""

    def __init__(self, body="", status=200):
        self.body, self.status, self.requests = body, status, []

    def __call__(self, request):
        self.requests.append(request)
        return httpx.Response(self.status, content=self.body.encode("utf-8"),
                              headers={"content-type": "text/event-stream"})

    @property
    def payload(self):
        return json.loads(self.requests[-1].content)


def generate(server, *, caps=ModelCapabilities(), **kw):
    provider = OpenAICompatProvider(httpx.MockTransport(server))
    defaults = dict(base_url="https://api.exemplo.com/v1", api_key=FAKE_KEY, capabilities=caps, max_tokens=500)
    return provider.generate(kw.pop("model", "modelo-x"), kw.pop("system", "S"),
                             kw.pop("messages", [{"role": "user", "content": "oi"}]), **{**defaults, **kw})


class Registry(unittest.TestCase):
    def test_prefix_routes_to_the_provider(self):
        self.assertEqual(R.split("deepseek:deepseek-chat")[0].name, "deepseek")
        self.assertEqual(R.split("deepseek:deepseek-chat")[1], "deepseek-chat")
        self.assertEqual(R.split("openrouter:qwen/qwen3-coder")[1], "qwen/qwen3-coder")
        self.assertEqual(R.split("claude-sonnet-5")[0].name, "anthropic")
        self.assertEqual(R.split("ollama:qwen3")[0].kind, "ollama")

    def test_valid_model_names(self):
        for ok in ("claude-sonnet-5", "deepseek:deepseek-chat", "ollama:qwen3:8b", "openrouter:meta-llama/llama-3.3"):
            self.assertTrue(R.valid_model(ok), ok)
        for bad in ("", "deepseek:", "deepseek:../x", "gpt-5", "deepseek:a b", "x" * 200):
            self.assertFalse(R.valid_model(bad), bad)

    def test_local_means_loopback_only(self):
        self.assertTrue(R.PRESETS["ollama"].local)
        self.assertTrue(R.PRESETS["lmstudio"].local)
        self.assertFalse(R.PRESETS["deepseek"].local)
        self.assertFalse(R.PRESETS["lmstudio"].needs_key)
        self.assertTrue(R.PRESETS["deepseek"].needs_key)

    def test_custom_provider_from_config(self):
        rows = {"meu": {"base_url": "https://llm.empresa.com/v1", "key_env": "MEU_KEY", "images": True},
                "inseguro": {"base_url": "http://llm.empresa.com/v1"},             # chave em texto puro
                "local": {"base_url": "http://127.0.0.1:8080/v1"},
                "deepseek": {"base_url": "https://outro.com/v1"},                  # nao sobrescreve preset
                "Ruim!": {"base_url": "https://x.com"}}
        cfg = Mock(get=lambda k, d=None: rows if k == "providers.custom" else d)
        with patch("core.config.get_config", return_value=cfg):
            found = R.providers()
            self.assertEqual(found["meu"].kind, "openai_compat")
            self.assertTrue(found["meu"].capabilities.images)
            self.assertNotIn("inseguro", found)
            self.assertTrue(found["local"].local)
            self.assertEqual(found["deepseek"].base_url, R.PRESETS["deepseek"].base_url)
            self.assertNotIn("Ruim!", found)
            self.assertEqual(R.split("meu:modelo-1")[0].name, "meu")


class OpenAICompatContract(unittest.TestCase):
    def test_incomplete_stream_never_releases_tools(self):
        chunk = {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c",
                 "function": {"name": "ler", "arguments": "{}"}}]}}]}
        for done in (False, True):
            with self.subTest(done=done), self.assertRaises(ProviderError):
                generate(Server(sse(chunk, done=done)), tools=[{"name": "ler", "input_schema": {"type": "object"}}])
        chunk["choices"][0]["finish_reason"] = "tool_calls"
        with self.assertRaises(ProviderError):
            generate(Server(sse(chunk, done=False)), tools=[{"name": "ler", "input_schema": {"type": "object"}}])
    def test_streams_text_and_reports_usage(self):
        server = Server(sse({"choices": [{"delta": {"content": "Olá"}}]},
                            {"choices": [{"delta": {"content": ", tudo bem?"}, "finish_reason": "stop"}]},
                            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 5}}))
        pieces = []
        resp = generate(server, on_text=pieces.append)
        self.assertEqual(pieces, ["Olá", ", tudo bem?"])
        self.assertEqual(resp.content[0].text, "Olá, tudo bem?")
        self.assertEqual((resp.usage.input_tokens, resp.usage.output_tokens, resp.stop_reason), (12, 5, "end_turn"))
        req = server.requests[0]
        self.assertEqual(str(req.url), "https://api.exemplo.com/v1/chat/completions")
        self.assertEqual(req.headers["authorization"], f"Bearer {FAKE_KEY}")
        self.assertEqual(server.payload["messages"][0], {"role": "system", "content": "S"})
        self.assertTrue(server.payload["stream"])

    def test_tool_call_arguments_arrive_in_pieces(self):
        server = Server(sse(
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "ler_arquivo",
                                                                                      "arguments": '{"cami'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'nho": "a.txt"}'}}]},
                          "finish_reason": "tool_calls"}]}))
        tools = [{"name": "ler_arquivo", "description": "lê", "input_schema": {"type": "object"}}]
        resp = generate(server, tools=tools)
        call = resp.content[-1]
        self.assertEqual((resp.stop_reason, call.type, call.id, call.name, call.input),
                         ("tool_use", "tool_use", "c1", "ler_arquivo", {"caminho": "a.txt"}))
        self.assertEqual(server.payload["tools"][0]["function"]["parameters"], {"type": "object"})

    def test_tool_round_trip_uses_openai_shapes(self):
        server = Server(sse({"choices": [{"delta": {"content": "Pronto."}, "finish_reason": "stop"}]}))
        messages = [{"role": "user", "content": "lê a.txt"},
                    {"role": "assistant", "content": [{"type": "text", "text": "Vou ler."},
                                                      {"type": "tool_use", "id": "c1", "name": "ler", "input": {"x": 1}}]},
                    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "conteúdo"}]}]
        generate(server, messages=messages, tools=[{"name": "ler", "input_schema": {"type": "object"}}])
        rows = server.payload["messages"]
        self.assertEqual(rows[2]["tool_calls"][0]["function"], {"name": "ler", "arguments": '{"x": 1}'})
        self.assertEqual(rows[3], {"role": "tool", "tool_call_id": "c1", "content": "conteúdo"})

    def test_truncated_tool_call_is_never_executed(self):
        server = Server(sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {
            "name": "apagar", "arguments": '{"caminho": "C:/'}}]}, "finish_reason": "length"}]}))
        resp = generate(server, tools=[{"name": "apagar", "input_schema": {"type": "object"}}])
        self.assertEqual(resp.stop_reason, "max_tokens")
        self.assertFalse([b for b in resp.content if b.type == "tool_use"])

    def test_unoffered_tool_and_bad_arguments_are_refused(self):
        server = Server(sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {
            "name": "executar_comando", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]}))
        with self.assertRaises(ProviderError):
            generate(server, tools=[{"name": "ler", "input_schema": {"type": "object"}}])
        server = Server(sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {
            "name": "ler", "arguments": "[1]"}}]}, "finish_reason": "tool_calls"}]}))
        with self.assertRaises(ProviderError):
            generate(server, tools=[{"name": "ler", "input_schema": {"type": "object"}}])

    def test_json_mode_without_native_schema(self):
        server = Server(sse({"choices": [{"delta": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}))
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        generate(server, schema=schema, caps=ModelCapabilities(structured=False))
        self.assertEqual(server.payload["response_format"], {"type": "json_object"})
        self.assertIn("JSON", server.payload["messages"][0]["content"])
        generate(server, schema=schema)
        self.assertEqual(server.payload["response_format"]["json_schema"]["schema"], schema)

    def test_friendly_errors_never_carry_the_key(self):
        for status, words in ((401, "Chave recusada"), (402, "créditos"), (429, "Limite"), (404, "não encontrado")):
            with self.assertRaises(ProviderError) as ctx:
                generate(Server("", status=status))
            self.assertIn(words, str(ctx.exception))
            self.assertNotIn(FAKE_KEY, str(ctx.exception))

    def test_cancel_stops_mid_stream(self):
        server = Server(sse(*[{"choices": [{"delta": {"content": str(i)}}]} for i in range(5)]))
        seen = []
        resp = generate(server, on_text=seen.append, cancelled=lambda: len(seen) >= 2)
        self.assertIsNone(resp)
        self.assertEqual(seen, ["0", "1"])

    def test_images_and_server_tools_need_capability(self):
        image = [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                                             "data": "AAAA"}}]}]
        with self.assertRaises(ProviderError):
            generate(Server(sse()), messages=image, caps=ModelCapabilities(images=False))
        server = Server(sse({"choices": [{"delta": {"content": "vi"}, "finish_reason": "stop"}]}))
        generate(server, messages=image)
        self.assertEqual(server.payload["messages"][1]["content"][0]["image_url"]["url"], "data:image/png;base64,AAAA")
        with self.assertRaises(ProviderError):
            generate(Server(sse()), tools=[{"type": "web_search_20260209", "name": "web_search"}])

    def test_list_models_confirms_the_key(self):
        server = Mock(side_effect=lambda r: httpx.Response(200, json={"data": [{"id": "deepseek-chat"},
                                                                                {"id": "deepseek-reasoner"}]}))
        models = OpenAICompatProvider(httpx.MockTransport(server)).list_models(
            base_url="https://api.deepseek.com/v1", api_key=FAKE_KEY)
        self.assertEqual(models, ["deepseek-chat", "deepseek-reasoner"])
        refused = OpenAICompatProvider(httpx.MockTransport(lambda r: httpx.Response(401)))
        with self.assertRaises(ProviderError):
            refused.list_models(base_url="https://api.deepseek.com/v1", api_key="errada-123456")


class ClientRouting(unittest.TestCase):
    def client(self, server):
        return AIClient(transport=Mock(), compat_provider=OpenAICompatProvider(httpx.MockTransport(server)))

    def setUp(self):
        keys = patch.object(secret_store, "load", return_value="")
        keys.start()
        self.addCleanup(keys.stop)
        env = patch.dict(os.environ, {"DEEPSEEK_API_KEY": FAKE_KEY})
        env.start()
        self.addCleanup(env.stop)

    def reply(self):
        return Server(sse({"choices": [{"delta": {"content": "feito"}, "finish_reason": "stop"}]},
                          {"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}))

    def test_message_goes_to_the_chosen_provider(self):
        server = self.reply()
        meta = self.client(server).message_with_meta("deepseek:deepseek-chat", "S", "pedido", agent="TESTE")
        self.assertEqual(meta["text"], "feito")
        self.assertEqual(str(server.requests[0].url), "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(server.payload["model"], "deepseek-chat")
        self.assertEqual(meta["cost_usd"], 0.0)                     # sem preco informado: desconhecido
        self.assertFalse(meta["cost_known"])
        self.assertEqual(meta["cost_status"], "unknown")

    def test_price_from_config(self):
        prices = {"deepseek:deepseek-chat": [0.3, 1.2]}
        real_get = __import__("core.config", fromlist=["get_config"]).get_config().get
        cfg = Mock(get=lambda k, d=None: prices if k == "providers.prices" else real_get(k, d))
        with patch("core.config.get_config", return_value=cfg):
            meta = self.client(self.reply()).message_with_meta("deepseek:deepseek-chat", "S", "pedido")
        self.assertAlmostEqual(meta["cost_usd"], (1000 * 0.3 + 500 * 1.2) / 1_000_000)

    def test_missing_key_is_explicit(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            with self.assertRaises(ProviderError) as ctx:
                self.client(self.reply()).message_with_meta("deepseek:deepseek-chat", "S", "pedido")
        self.assertIn("Configurações > Modelos", str(ctx.exception))

    def test_offline_blocks_everything_unless_local_models_are_allowed(self):
        from core.config import get_config
        from core.egress import EgressDenied
        real_get = get_config().get
        allow = Mock(get=lambda k, d=None: True if k == "privacy.allow_local_models" else real_get(k, d))
        with patch("core.egress.offline", return_value=True):
            with self.assertRaises(EgressDenied):
                self.client(self.reply()).message_with_meta("lmstudio:qwen3-8b", "S", "pedido")
        with patch("core.egress.offline", return_value=True), patch("core.config.get_config", return_value=allow):
            with self.assertRaises(EgressDenied):
                self.client(self.reply()).message_with_meta("deepseek:deepseek-chat", "S", "pedido")
            server = self.reply()
            meta = self.client(server).message_with_meta("lmstudio:qwen3-8b", "S", "pedido")
            self.assertEqual(meta["text"], "feito")
            self.assertTrue(str(server.requests[0].url).startswith("http://127.0.0.1:1234/v1/"))
            self.assertNotIn("authorization", server.requests[0].headers)

    def test_strict_budget_refuses_unmetered_provider(self):
        import threading
        budget = Budget(usd=1, seconds=60, calls=5, tokens=10000, cancel=threading.Event())
        with budget_scope(budget), self.assertRaises(RequestLimit):
            self.client(self.reply()).message_with_meta("deepseek:deepseek-chat", "S", "pedido")

    def test_conversation_with_tools(self):
        server = Server(sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "t1", "function": {
            "name": "listar_pasta", "arguments": '{"caminho": "."}'}}]}, "finish_reason": "tool_calls"}]}))
        resp = self.client(server).converse("deepseek:deepseek-chat", "S", [{"role": "user", "content": "lista"}],
                                            [{"name": "listar_pasta", "input_schema": {"type": "object"}}])
        self.assertEqual((resp.stop_reason, resp.content[-1].name), ("tool_use", "listar_pasta"))

    def test_chat_agent_drops_anthropic_web_search_for_other_providers(self):
        from agents.chat_agent import ChatAgent
        cfg = Mock(get=lambda k, d=None: d, get_model=lambda n: "deepseek:deepseek-chat", get_effort=lambda n: None)
        names = [t["name"] for t in ChatAgent(client=Mock(), config=cfg).tools()]
        self.assertNotIn("web_search", names)
        cfg.get_model = lambda n: "claude-sonnet-5"
        self.assertIn("web_search", [t["name"] for t in ChatAgent(client=Mock(), config=cfg).tools()])


class BrainForEveryProvider(unittest.TestCase):
    """Modelos de outros provedores consultam o Cérebro igual ao Claude: as ferramentas são do app."""

    def test_deepseek_searches_the_brain_and_answers_from_the_note(self):
        from agents.chat_agent import ChatAgent
        replies = iter([
            sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "b1", "function": {
                "name": "buscar_no_cerebro", "arguments": '{"consulta": "formato de planilha"}'}}]},
                "finish_reason": "tool_calls"}]}),
            sse({"choices": [{"delta": {"content": "Pelas suas regras, planilhas em R$."}, "finish_reason": "stop"}]}),
        ])
        sent = []

        def respond(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, content=next(replies).encode("utf-8"))
        client = AIClient(transport=Mock(), compat_provider=OpenAICompatProvider(httpx.MockTransport(respond)))
        cfg = Mock(get=lambda k, d=None: {"chat.web_search": True}.get(k, d),
                   get_model=lambda n: "deepseek:deepseek-chat", get_effort=lambda n: None)
        agent = ChatAgent(client=client, config=cfg)
        agent.system_prompt = lambda: "S"
        with patch.object(secret_store, "load", return_value=""), patch.dict(os.environ, {"DEEPSEEK_API_KEY": FAKE_KEY}),                 patch("mcp_server.call_tool", return_value="Regra: planilhas sempre em R$.") as brain:
            result = agent.respond("como formato a planilha?", None)
        brain.assert_called_once_with("brain_search", {"query": "formato de planilha"})
        self.assertIn("R$", result.text)
        offered = [t["function"]["name"] for t in sent[0]["tools"]]
        self.assertIn("buscar_no_cerebro", offered)
        self.assertNotIn("web_search", offered)                     # ferramenta do servidor da Anthropic
        self.assertEqual(sent[1]["messages"][-1], {"role": "tool", "tool_call_id": "b1",
                                                   "content": "Regra: planilhas sempre em R$."})

    def test_agent_planning_prompt_carries_the_brain_for_any_model(self):
        server = Server(sse({"choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}]}))
        client = AIClient(transport=Mock(), compat_provider=OpenAICompatProvider(httpx.MockTransport(server)))
        from agents.base_agent import brain_guide
        with patch("core.brain.get_brain") as get_brain, patch.object(secret_store, "load", return_value=""),                 patch.dict(os.environ, {"GROQ_API_KEY": FAKE_KEY}):
            get_brain.return_value.context_for.return_value = "Regra do DATA: datas em dd/mm/aaaa."
            system = "Você monta planilhas." + brain_guide("DATA", "planilha de gastos")
            client.message_with_meta("groq:llama-3.3-70b-versatile", system, "planilha de gastos")
        self.assertIn("dd/mm/aaaa", server.payload["messages"][0]["content"])


@unittest.skipUnless(secret_store.available(), "DPAPI só existe no Windows")
class KeyStorage(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "keys.json"

    def test_round_trip_is_encrypted_at_rest(self):
        secret_store.save("deepseek", FAKE_KEY, self.path)
        self.assertNotIn(FAKE_KEY, self.path.read_text(encoding="utf-8"))
        self.assertTrue(secret_store.has("deepseek", self.path))
        self.assertEqual(secret_store.load("deepseek", self.path), FAKE_KEY)
        self.assertTrue(secret_store.delete("deepseek", self.path))
        self.assertEqual(secret_store.load("deepseek", self.path), "")

    def test_invalid_input(self):
        for name, key in (("DeepSeek", FAKE_KEY), ("../x", FAKE_KEY), ("deepseek", "curta"),
                          ("deepseek", "tem espaco no meio 123")):
            with self.assertRaises(secret_store.SecretStoreError):
                secret_store.save(name, key, self.path)

    def test_tampered_blob_reads_as_missing(self):
        self.path.write_text(json.dumps({"deepseek": "AAAA"}), encoding="utf-8")
        self.assertEqual(secret_store.load("deepseek", self.path), "")


class ModelChoice(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "settings.json"

    def test_settings_validate_and_override_the_yaml(self):
        from core import user_settings
        saved = user_settings.save({"models": {"strong": "deepseek:deepseek-chat"}}, self.path)
        self.assertEqual(saved["models"], {"strong": "deepseek:deepseek-chat"})
        for bad in ({"strong": "gpt-5"}, {"enorme": "deepseek:x"}, {"strong": 3}):
            with self.assertRaises(ValueError):
                user_settings.save({"models": bad}, self.path)
        cleared = user_settings.save({"models": {"strong": ""}}, self.path)
        self.assertEqual(cleared["models"], {})

    def test_config_uses_the_choice(self):
        from core import user_settings
        from core.config import get_config
        user_settings.save({"models": {"strong": "ollama:qwen3"}}, self.path)
        with patch.object(user_settings, "PATH", self.path), patch.object(user_settings, "_cache", (None, {})):
            tier = get_config().get("agent_models.maestro", "fast")
            if tier == "strong":
                self.assertEqual(get_config().get_model("MAESTRO"), "ollama:qwen3")
            self.assertEqual(user_settings.model_override("strong"), "ollama:qwen3")


class CustomProviderFromTheScreen(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        from core import user_settings
        self.path = Path(tmp.name) / "settings.json"
        p = patch.object(user_settings, "PATH", self.path)
        p.start()
        self.addCleanup(p.stop)

    def test_create_route_and_remove(self):
        from core import user_settings
        user_settings.save({"custom_providers": {"minhaia": {"label": "Minha IA", "base_url": "https://api.minha.ai/v1"}}},
                           self.path)
        provider, name = R.split("minhaia:modelo-7b")
        self.assertEqual((provider.name, provider.base_url, name), ("minhaia", "https://api.minha.ai/v1", "modelo-7b"))
        self.assertTrue(R.valid_model("minhaia:modelo-7b"))
        for bad in ({"deepseek": {"base_url": "https://x.com/v1"}},          # nao toma o lugar de um pronto
                    {"remota": {"base_url": "http://x.com/v1"}},             # chave em texto puro
                    {"Errado": {"base_url": "https://x.com/v1"}},
                    {"comquery": {"base_url": "https://x.com/v1?k=1"}}):
            with self.assertRaises(ValueError):
                user_settings.save({"custom_providers": bad}, self.path)
        user_settings.save({"custom_providers": {"minhaia": None}}, self.path)
        self.assertNotIn("minhaia", R.providers())

    def test_bridge_saves_custom_with_key_in_dpapi(self):
        from desktop.bridge_core import BridgeCore
        bridge = BridgeCore.__new__(BridgeCore)
        with patch.object(secret_store, "save") as save_key, patch.object(secret_store, "has", return_value=False),                 patch.object(secret_store, "load", return_value=""):
            out = json.loads(bridge.providerCustomSave(json.dumps({"name": "minhaia", "label": "Minha IA",
                                                                   "base_url": "https://api.minha.ai/v1", "key": FAKE_KEY})))
            self.assertTrue(out["ok"])
            self.assertNotIn(FAKE_KEY, json.dumps(out))
            save_key.assert_called_once_with("minhaia", FAKE_KEY)
            entry = next(p for p in out["catalog"] if p["name"] == "minhaia")
            self.assertTrue(entry["custom"])
            self.assertFalse(json.loads(bridge.providerCustomRemove("deepseek"))["ok"])
            with patch.object(secret_store, "delete"):
                self.assertTrue(json.loads(bridge.providerCustomRemove("minhaia"))["ok"])
            bad = json.loads(bridge.providerCustomSave(json.dumps({"name": "x!", "base_url": "ftp://a"})))
            self.assertFalse(bad["ok"])


class BridgeNeverReturnsTheKey(unittest.TestCase):
    def test_save_status_and_models(self):
        from desktop.bridge_core import BridgeCore
        bridge = BridgeCore.__new__(BridgeCore)
        stored = {}
        with patch.object(secret_store, "save", side_effect=lambda n, k: stored.update({n: k})), \
                patch.object(secret_store, "has", side_effect=lambda n: n in stored), \
                patch.object(secret_store, "load", side_effect=lambda n: stored.get(n, "")):
            out = json.loads(bridge.providerKeySave("deepseek", FAKE_KEY))
            status = bridge.providerStatus()
            self.assertTrue(out["ok"])
            self.assertNotIn(FAKE_KEY, json.dumps(out))
            self.assertNotIn(FAKE_KEY, status)
            deepseek = next(p for p in out["catalog"] if p["name"] == "deepseek")
            self.assertTrue(deepseek["configured"] and deepseek["stored"])
            self.assertFalse(json.loads(bridge.providerKeySave("ollama", FAKE_KEY))["ok"])   # local nao usa chave
            self.assertFalse(json.loads(bridge.providerKeySave("inexistente", FAKE_KEY))["ok"])
            with patch("core.model_provider.OpenAICompatProvider.list_models", return_value=["deepseek-chat"]):
                listed = json.loads(bridge.providerModels("deepseek"))
            self.assertEqual(listed["models"], ["deepseek:deepseek-chat"])


if __name__ == "__main__":
    unittest.main()
