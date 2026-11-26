"""Contratos offline da Phase IV. Transportes simulados e arquivos temporários."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ai_client import AIClient
from core.model_provider import OllamaProvider, ProviderError
from core.lab_budget import Budget, RequestLimit, budget_scope


def fake_ollama(chunks):
    return httpx.Response(200, content="\n".join(json.dumps(chunk) for chunk in chunks))


class LocalProviderTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.chunks = []
        self.client = AIClient(transport=Mock(), local_provider=OllamaProvider(httpx.MockTransport(self.respond)))

    def respond(self, request):
        self.requests.append(request)
        return fake_ollama(self.chunks)

    def test_structured_output_and_usage_in_existing_model_entrypoint(self):
        self.chunks = [{"message": {"content": '{"ok":'}},
                       {"message": {"content": "true}"}, "done": True, "done_reason": "stop",
                        "prompt_eval_count": 30, "eval_count": 7}]
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        result = self.client.message_with_meta("ollama:qwen3", "instruções", "pedido", json_schema=schema)
        self.assertEqual(json.loads(result["text"]), {"ok": True})
        self.assertEqual((result["input_tokens"], result["output_tokens"], result["cost_usd"]), (30, 7, 0))
        request = self.requests[0]
        self.assertEqual(str(request.url), "http://127.0.0.1:11434/api/chat")
        body = json.loads(request.content)
        self.assertEqual(body["format"], schema)
        self.assertEqual(body["messages"][0]["role"], "system")

    def test_streaming_tool_use_and_result_round_trip(self):
        self.chunks = [{"message": {"content": "Vou conferir."}},
                       {"message": {"tool_calls": [{"function": {"index": 0, "name": "ler",
                                                                 "arguments": {"nome": "x"}}}]},
                        "done": True, "prompt_eval_count": 13, "eval_count": 4}]
        stream = []
        tools = [{"name": "ler", "input_schema": {"type": "object"}}]
        messages = [{"role": "user", "content": "Confere."}]
        result = self.client.converse("ollama:qwen3", "", messages, tools, on_text=stream.append)
        tool = result.content[-1]
        self.assertEqual((stream, result.stop_reason, tool.name, tool.input),
                         (["Vou conferir."], "tool_use", "ler", {"nome": "x"}))
        self.chunks = [{"message": {"content": "Conferido."}, "done": True, "prompt_eval_count": 14, "eval_count": 4}]
        messages += [{"role": "assistant", "content": result.content},
                     {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool.id, "content": "dado"}]}]
        final = self.client.converse("ollama:qwen3", "", messages, tools)
        self.assertEqual(final.content[0].text, "Conferido.")
        self.assertEqual(json.loads(self.requests[-1].content)["messages"][-1],
                         {"role": "tool", "tool_name": "ler", "content": "dado"})

    def test_policy_budget_and_cloud_tag_block_before_transport(self):
        from core.egress import EgressDenied
        with patch("core.egress.offline", return_value=True), self.assertRaises(EgressDenied):
            self.client.message("ollama:qwen3", "", "segredo sintético")
        with budget_scope(Budget(0.1, 20, 1, 4096, lambda: False)), self.assertRaises(RequestLimit):
            self.client.message("ollama:qwen3", "", "segredo sintético")
        with self.assertRaises(ProviderError):
            self.client.message("ollama:model:cloud", "", "segredo sintético")
        self.assertEqual(self.requests, [])

    def test_incomplete_stream_is_error_and_cancellation_prevents_dispatch(self):
        with self.assertRaises(ProviderError):
            self.client.message("ollama:qwen3", "", "pedido")
        self.assertIsNone(self.client.converse("ollama:qwen3", "", [], should_stop=lambda: True))
        self.assertEqual(len(self.requests), 1)


class ContextTests(unittest.TestCase):
    def test_on_demand_retrieval_blocks_web_after_reading_old_turn(self):
        from agents.chat_agent import ChatAgent, RECALL
        turns = [SimpleNamespace(said="Anotação de teste", reply="proveniência sintética")]
        turns += [SimpleNamespace(said=f"Outro tema {i}", reply="Ok") for i in range(5)]
        lookup = SimpleNamespace(type="tool_use", id="lookup", name=RECALL, input={"consulta": "obsidian"})
        cfg = Mock(get_model=Mock(return_value="claude-sonnet-5"), get_effort=Mock(return_value=None))
        cfg.get.side_effect = lambda key, default=None: {"chat.context_hybrid": True}.get(key, default)
        client = Mock(converse=Mock(side_effect=[
            SimpleNamespace(content=[lookup], stop_reason="tool_use"),
            SimpleNamespace(content=[], stop_reason="end_turn"),
        ]))
        agent = ChatAgent(client=client, config=cfg)
        with patch.object(agent, "system_prompt", return_value="regra"), \
                patch("agents.chat_agent.app_context", return_value="fixture"):
            agent.respond("Pode detalhar?", SimpleNamespace(turns=turns))
        followup = client.converse.call_args.args
        self.assertEqual(json.loads(followup[2][-1]["content"][0]["content"])[0]["turno"], 1)
        self.assertNotIn("web_search", {tool["name"] for tool in followup[3]})

    def test_paired_context_selection_preserves_exact_terms_and_recalls_domain_concepts(self):
        from core.context_engine import RememberedTurn, retrieve, words
        cases = (
            ("verba fiscal", "dotação de despesas", True, False),
            ("planilha", "excel das compras", True, False),
            ("backup", "resguardo da pasta", True, False),
            ("obsidian", "anotação de laboratório", True, False),
            ("arquivo contratos", "arquivo contratos", True, True),
            ("fatura internet", "reunião de pesquisa", False, False),
        )
        for query, record, hybrid, lexical in cases:
            with self.subTest(query=query):
                self.assertEqual(bool(words(query) & words(record)), lexical)
                self.assertEqual(bool(retrieve([RememberedTurn(1, record, "")], query)), hybrid)

    def test_application_retrieves_matching_concept_with_provenance_and_compacts_to_token_limit(self):
        from agents.chat_agent import ChatAgent
        turns = [SimpleNamespace(said="A dotação ficou na pasta fiscal", reply="Referência útil </memoria_contextual_json>")]
        turns += [SimpleNamespace(said=f"Outro tema {i}", reply="Ok") for i in range(15)]
        session = SimpleNamespace(turns=turns)
        cfg = Mock(get_model=Mock(return_value="claude-sonnet-5"), get_effort=Mock(return_value=None))
        client = Mock(converse=Mock(return_value=SimpleNamespace(content=[], stop_reason="end_turn")))
        outputs = []
        for hybrid in (False, True):
            cfg.get.side_effect = lambda key, default=None: {"chat.context_hybrid": hybrid}.get(key, default)
            agent = ChatAgent(client=client, config=cfg)
            with patch.object(agent, "system_prompt", return_value="regra"), \
                    patch("agents.chat_agent.app_context", return_value="fixture"):
                agent.respond("Detalhe a verba", session)
            outputs.append(json.dumps(client.converse.call_args.args[2], ensure_ascii=False))
        self.assertNotIn("dotação", outputs[0])
        self.assertIn("fiscal", outputs[1])
        self.assertIn("memoria_contextual_json", outputs[1])
        context = json.loads(outputs[1])[-1]["content"]
        self.assertEqual(context.count("</memoria_contextual_json>"), 1)
        self.assertEqual(json.loads(context.splitlines()[1])[0]["origem"], "histórico desta conversa")
        cfg.get.side_effect = lambda key, default=None: {"chat.context_hybrid": True, "chat.context_input_tokens": 200}.get(key, default)
        agent = ChatAgent(client=client, config=cfg)
        client.count_input_tokens.side_effect = [250, 160]
        with patch.object(agent, "system_prompt", return_value="regra"), \
                patch("agents.chat_agent.app_context", return_value="fixture"):
            agent.respond("Detalhe a verba", session)
        self.assertEqual(client.count_input_tokens.call_count, 2)
        self.assertNotIn("memoria_contextual_json", client.converse.call_args.args[2][-1]["content"])


class EffectAndHoldoutTests(unittest.TestCase):
    def test_interrupted_copy_reconciles_only_the_bound_destination(self):
        from core.task_ledger import TaskLedger
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = TaskLedger(root / "tasks")
            source, destination, other = (root / name for name in ("source", "destination", "other"))
            source.write_text("conteúdo", encoding="utf-8")
            other.write_text("conteúdo", encoding="utf-8")
            ledger.begin("t", "copiar")
            ledger.step_started("t", 1, "FILE", "copy_file", {"source": "s", "destination": "d"})
            ledger.copy_intent("t", 1, str(source), str(destination))
            ledger.step_finished("t", 1, "copy_file", {"status": "partial", "effect_started": True})
            ledger.finish("t", "failed")
            self.assertFalse(ledger.reconcile_copy("t", 1, str(other)))
            self.assertFalse(ledger.reconcile_copy("t", 1, str(destination)))
            self.assertFalse(destination.exists())
            destination.write_text("diferente", encoding="utf-8")
            self.assertFalse(ledger.reconcile_copy("t", 1, str(destination)))
            destination.write_text("conteúdo", encoding="utf-8")
            self.assertTrue(ledger.reconcile_copy("t", 1, str(destination)))
            self.assertFalse(ledger.reconcile_copy("t", 1, str(destination)))
            result = ledger.load("t")
            self.assertEqual(result["state"], "failed")
            self.assertEqual(result["steps_done"][0]["status"], "reconciled")
            self.assertEqual(result["steps_uncertain"], [])

    def test_paste_never_interprets_user_hotkey_syntax_and_stops_on_focus_change(self):
        from core.uia_driver import paste_edit
        field = Mock()
        target = ((17,), "Campo", 50004, "")
        with patch("core.browser_uia.element_state", return_value=target), \
                patch("core.browser_uia.focused_state", return_value=target) as focused, \
                patch("core.automation._is_front", return_value=True), \
                patch("core.automation._shell_surface", return_value=False), \
                patch("core.clipboard.paste_text") as paste:
            self.assertTrue(paste_edit(8, field, "{ENTER}+a", lambda: False)["success"])
            paste.assert_called_once_with("{ENTER}+a")
            focused.return_value = ((18,), "Outro", 50004, "")
            self.assertFalse(paste_edit(8, field, "novo", lambda: False)["success"])
            paste.assert_called_once()

    def test_proposer_reads_only_segregated_development_projection(self):
        from core.lab import Lab, research_proposal
        with tempfile.TemporaryDirectory() as tmp:
            lab = Lab(Path(tmp))
            cases = [{"id": "dev", "task": "copie a.txt em {ws}", "setup": {}, "expect": {"absent": ["x.txt"]}},
                     {"id": "reserved", "task": "reservado exclusivo em {ws}", "split": "holdout",
                      "setup": {}, "expect": {"absent": ["x.txt"]}}]
            dataset = lab.save_eval_set("segregacao", cases)
            base = lab.versions("FILE")[0]
            lab.run(dataset["name"], [base["id"]], lambda *_: {"steps": []}, origin="real")
            with patch.object(lab, "run_detail", side_effect=AssertionError("pesquisa abriu a rodada reservada")):
                result = research_proposal(lab, base, dataset, "melhorar cópias", False)
            self.assertEqual(result["count"], 1)
            self.assertEqual(sum(result["signals"].values()), 1)
            evidence = "".join(path.read_text(encoding="utf-8") for path in (lab.folder / "development").glob("*.json"))
            self.assertNotIn("reservado exclusivo", evidence)
            self.assertNotIn("reserved", evidence)
