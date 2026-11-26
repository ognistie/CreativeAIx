"""Aceite das três fases do Lab com provedor substituído e artefatos temporários."""
import json
import tempfile
import threading
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.harness import Harness
from core.lab import Lab, fixture_planner, real_planner, replay_planner, research_proposal
from core.lab_budget import Budget, budget_scope
from core.lab_report import report
from core.task_ledger import TaskLedger


class LabWorkspaceTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.lab = Lab(self.root)
        self.harness = Harness(self.root)

    def versions(self, agent):
        active = self.lab.versions(agent, self.harness)[0]
        candidate = self.lab.create_variant(agent, active["id"], "Revise o resultado pedido.", note="Hipótese sintética")
        return [active["id"], candidate["id"]]

    def copy_case(self, destination="b.txt", split="development"):
        return {"id": "copia", "task": f"Copie a.txt para {destination} dentro de {{ws}}", "split": split,
                "setup": {"a.txt": "teste"}, "expect": {"contains": {destination: "teste"}}}

    def client(self, outputs):
        fake = Mock()
        fake.with_options.return_value = fake
        fake.messages.count_tokens.return_value = SimpleNamespace(input_tokens=100)
        responses = iter(outputs)

        def stream(**params):
            response = SimpleNamespace(
                content=[SimpleNamespace(type="text", text=json.dumps(next(responses)))],
                stop_reason="end_turn", model=params["model"],
                usage=SimpleNamespace(input_tokens=100, output_tokens=25),
            )
            class Stream:
                def __iter__(self):
                    return iter(())

                def get_final_message(self):
                    return response

            return nullcontext(Stream())

        fake.messages.stream.side_effect = stream
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "synthetic-credential"}), patch("core.ai_client.Anthropic", return_value=fake):
            from core.ai_client import AIClient
            client = AIClient()
        return fake, client

    @staticmethod
    def copy_plan(destination):
        return {"steps": [{"action": "copy_file", "params": {"source": "{ws}/a.txt", "destination": f"{{ws}}/{destination}"}}]}

    def test_dataset_revisions_replay_export_and_rollback(self):
        old = self.lab.save_eval_set("copia", [self.copy_case(split="holdout")], expected="new")
        versions = self.versions("FILE")
        sdk, client = self.client([self.copy_plan("errado.txt"), self.copy_plan("b.txt")])
        cancel = threading.Event()
        limits = Budget(0.50, 30, 2, 30000, cancel)
        with patch("core.ai_client.get_client", return_value=client), patch("agents.base_agent.get_client", return_value=client), \
             patch("agents.base_agent.brain_guide", side_effect=AssertionError("memória pessoal")), budget_scope(limits):
            result = self.lab.run(old["name"], versions, real_planner, "real", cancel=cancel, budget_usd=0.50)
        self.assertEqual(sdk.messages.stream.call_count, 2)
        self.assertEqual(sdk.messages.count_tokens.call_count, 2)
        self.assertNotIn(str(self.root), str(sdk.messages.stream.call_args_list))
        self.assertIn("max_tokens", result["results"][1]["applied"])
        self.assertEqual(len(result["comparison"]["improvements"]), 1)
        self.assertEqual(self.lab.promote(versions[1], self.harness)["id"], versions[1])
        self.assertEqual(self.lab.rollback("FILE", self.harness, versions[1])["id"], versions[0])
        with self.assertRaises(ValueError):
            self.lab.archive(versions[0], True, self.harness)
        self.assertTrue(self.lab.archive(versions[1], True, self.harness)["archived"])
        self.assertFalse(self.lab.promotion_check(versions[1])["ok"])
        self.assertFalse(self.lab.archive(versions[1], False, self.harness)["archived"])
        original = result["dataset_snapshot"]["hash"]
        self.lab.save_eval_set("copia", [self.copy_case("c.txt")], expected=original)
        self.assertEqual(self.lab.eval_set("copia", original), old)
        replay = self.lab.run("copia", versions, replay_planner(self.lab), "simulado", revision=original, repeats=2)
        self.assertEqual(replay["comparison"]["pairs"], 2)
        self.lab.add_feedback(replay["id"], versions[1], "copia", "marcador-privado@example.org", trial=2)
        export = self.lab.run_detail(replay["id"])
        text = report(export, "json")
        self.assertNotIn("marcador-privado", text)
        self.assertNotIn("a.txt", text)
        self.assertEqual(json.loads(text)["dataset_hash"], original)
        ledger = TaskLedger(self.lab.folder / "events")
        self.assertEqual(len([e for e in ledger.events(replay["task_id"]) if e["type"] == "note"]), 4)

    def test_budget_blocks_an_inference_before_provider_stream(self):
        dataset = self.lab.save_eval_set("uma", [self.copy_case()])
        versions = self.versions("FILE")
        sdk, client = self.client([])
        cancel = threading.Event()
        with patch("core.ai_client.get_client", return_value=client), patch("agents.base_agent.get_client", return_value=client), \
             budget_scope(Budget(0.01, 30, 2, 30000, cancel)):
            run = self.lab.run(dataset["name"], versions, real_planner, "real", cancel=cancel, budget_usd=0.01)
        sdk.messages.stream.assert_not_called()
        self.assertEqual(run["status"], "orcamento")
        self.assertEqual(run["usage"]["calls_started"], 0)

    def test_conversation_budget_counts_tools_and_reserves_server_search_cost(self):
        from core.lab_budget import RequestLimit

        sdk, client = self.client([])
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
        with budget_scope(Budget(0.01, 30, 2, 30000, lambda: False)):
            with self.assertRaises(RequestLimit):
                client.converse("claude-sonnet-4-6", "", [{"role": "user", "content": "teste"}],
                                tools=tools, max_tokens=10)
        sdk.messages.count_tokens.assert_called_once()
        self.assertEqual(sdk.messages.count_tokens.call_args.kwargs["tools"], tools)
        sdk.messages.stream.assert_not_called()

    def test_separate_corpora_and_guarded_proposal(self):
        dataset = self.lab.save_eval_set("copia", [self.copy_case(), {**self.copy_case("c.txt"), "id": "reservado",
                                                                    "split": "holdout", "context": "segredo-da-fixture"}])
        versions = self.versions("FILE")
        active = self.lab.version(versions[0])
        proposal = research_proposal(self.lab, active, dataset, "Diminuir erros de destino", False)
        self.assertEqual(proposal["count"], 1)
        self.assertNotIn("segredo-da-fixture", json.dumps(proposal))
        self.assertEqual(self.lab.version(versions[0])["instructions"], active["instructions"])
        self.assertTrue(self.lab.version(versions[0])["published"])

    def test_maestro_local_routes_and_verified_artifacts(self):
        maestro = self.versions("MAESTRO")
        result = self.lab.run("maestro-rotas", maestro[:1], fixture_planner, "fixture")
        self.assertEqual(result["summary"][maestro[0]]["passed"], 2)

        code = self.versions("CODE")
        def project(version, task):
            return {"steps": [{"action": "create_project", "params": {"manifest": {
                "name": "amostra", "files": [{"path": "soma.py", "content": "def somar(a, b):\n    return a + b\n"}],
            }}}]}
        graded = self.lab.run("codigo-artefato", code, project, "simulado", split="development")
        self.assertEqual(graded["comparison"]["pairs"], 1)
        self.assertTrue(all(row["status"] == "passou" for row in graded["results"]))

        data = self.versions("DATA")
        def workbook(version, task):
            formula = "=SUM(A2:A3)" if version["id"] == data[0] else "=AVG(A2:A3)"
            return {"steps": [{"action": "create_workbook", "params": {"manifest": {
                "name": "amostra", "sheets": [{"title": "Total", "rows": [["Valor"], [12], [30], [formula]], "charts": []}],
            }}}]}
        graded = self.lab.run("dados-celulas", data, workbook, "simulado", split="development")
        self.assertEqual(len(graded["comparison"]["regressions"]), 1)
        self.assertEqual(graded["results"][0]["status"], "passou")
        self.assertEqual(graded["results"][1]["status"], "falhou")

    def test_maestro_rejects_unrequested_side_effects(self):
        versions = self.versions("MAESTRO")
        self.lab.save_eval_set("rotas-adversariais", [{"id": "roteamento", "task": "Abra a conversa para ler a mensagem.",
                                                    "expect": {"agents": ["DESKTOP"]}}], "MAESTRO")
        def proposed(version, task):
            return {"routing": {"subtasks": [{"agent": "DESKTOP", "task": "Enviar uma mensagem",
                                              "params": {"action_type": "send_message", "text": "teste"}}]}}
        run = self.lab.run("rotas-adversariais", versions, proposed, "simulado")
        self.assertTrue(all(row["status"] == "falhou" for row in run["results"]))
