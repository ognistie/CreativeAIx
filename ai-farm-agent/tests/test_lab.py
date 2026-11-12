"""AI Research Lab (core/lab.py): aceite do briefing com planejadores de teste (origem "simulado").

Caso sintetico em duas versoes -> configuracao efetiva e traces -> estado final conferido no disco -> metricas
com origem -> restaurar a versao anterior. Mais: cancelamento, falha de ferramenta, provedor indisponivel e
tentativa de escapar da pasta do caso. Nenhuma chamada paga.
"""
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.lab import Lab, ProviderUnavailable, effective_config, validate_params


def _ws(task: str) -> str:
    """A pasta do caso, tirada do texto da tarefa (o planejador de teste so ve o que o modelo veria)."""
    import re
    return re.search(r"([A-Za-z]:\\[^\s]*?lab-caso-[^\\\s]+\\caso)", task).group(1)


def good_planner(version, task):
    ws = _ws(task)
    if "crie a pasta" in task:
        steps = [{"action": "create_folder", "params": {"path": ws + "\\relatorios"}}]
    elif task.startswith("mova"):
        steps = [{"action": "move_file", "params": {"source": ws + "\\notas.txt", "destination": ws + "\\arquivo\\notas.txt"}}]
    elif task.startswith("copie"):
        steps = [{"action": "copy_file", "params": {"source": ws + "\\a.txt", "destination": ws + "\\b.txt"}}]
    else:
        steps = [{"action": "create_folder", "params": {"path": ws + "\\imagens"}},
                 {"action": "move_file", "params": {"source": ws + "\\foto.jpg", "destination": ws + "\\imagens\\foto.jpg"}}]
    return {"steps": steps, "metrics": {"calls": 1, "tokens": 100, "cost_usd": 0.001}}


def sloppy_planner(version, task):
    """Variante pior: copia para o nome errado e tenta tirar a foto da pasta do caso."""
    ws = _ws(task)
    if task.startswith("copie"):
        return {"steps": [{"action": "copy_file", "params": {"source": ws + "\\a.txt", "destination": ws + "\\c.txt"}}]}
    if task.startswith("organize"):
        fora = str(Path(ws).parent / "fora" / "foto.jpg")
        return {"steps": [{"action": "move_file", "params": {"source": ws + "\\foto.jpg", "destination": fora}}]}
    return good_planner(version, task)


class ExecutedPathIsTheValidatedPath(unittest.TestCase):
    def test_short_windows_names_keep_their_tilde(self):
        from core.automation import BASE, expand
        self.assertEqual(expand("C:\\Users\\ABCDEF~1\\AppData\\x"), "C:/Users/ABCDEF~1/AppData/x")
        self.assertEqual(expand("~\\Documentos"), (BASE + "\\Documentos").replace("\\", "/"))
        self.assertEqual(expand("~"), BASE.replace("\\", "/"))


class LabAcceptance(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="lab-test-"))
        self.lab = Lab(self.dir)
        self.base = self.lab.versions("FILE")[0]
        self.variant = self.lab.create_variant("FILE", self.base["id"], "Sempre confira o destino antes de copiar.",
                                               {"effort": "low"}, note="mais cuidadosa")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def plan_for(self, version, task):
        return (good_planner if version["id"] == self.variant["id"] else sloppy_planner)(version, task)

    def test_same_cases_two_versions_with_state_checked_on_disk(self):
        run = self.lab.run("arquivos-basico", [self.base["id"], self.variant["id"]], self.plan_for, origin="simulado")
        s = run["summary"]
        self.assertEqual(s[self.variant["id"]]["passed"], 4)                 # todas conferidas no disco
        self.assertEqual(s[self.base["id"]]["passed"], 3)                    # so a copia errada falha; a fuga foi bloqueada
        copy = next(r for r in run["results"] if r["version"] == self.base["id"] and r["case"] == "copiar")
        self.assertEqual(copy["status"], "falhou")                            # "copiou" para o nome errado
        self.assertTrue(any(not c["ok"] and "b.txt" in c["check"] for c in copy["checks"]))
        escape = next(r for r in run["results"] if r["version"] == self.base["id"] and r["case"] == "nao-sair-da-pasta")
        self.assertTrue(escape["blocked"])                                    # executor bloqueou a saida
        self.assertEqual(escape["trace"][1]["kind"], "bloqueado")
        self.assertIn("<fora da pasta do caso>", str(escape["trace"][1]["params"]))
        self.assertEqual(escape["status"], "passou")                          # e nada foi escrito fora
        self.assertTrue(all(r["origin"] == "simulado" for r in run["results"]))
        self.assertEqual(s[self.variant["id"]]["origin"], "simulado")
        self.assertIn("amostra pequena (4 casos)", s[self.variant["id"]]["warnings"])
        self.assertAlmostEqual(s[self.variant["id"]]["cost_usd"], 0.004)
        self.assertEqual(run["set_version"], 1)
        self.assertEqual(self.lab.run_detail(run["id"])["summary"], s)       # registrado para consultar depois

    def test_cancel_tool_failure_and_provider_unavailable(self):
        cancel = threading.Event()
        calls = []

        def planner(version, task):
            calls.append(task)
            if len(calls) == 2:
                cancel.set()                                                  # cancela no meio
            return good_planner(version, task)
        run = self.lab.run("arquivos-basico", [self.variant["id"]], planner, origin="simulado", cancel=cancel)
        self.assertEqual(run["status"], "cancelado")
        self.assertEqual(run["summary"][self.variant["id"]]["cancelled"], 2)
        self.assertIn("execução incompleta", run["summary"][self.variant["id"]]["warnings"])

        def broken_tool(version, task):
            ws = _ws(task)
            return {"steps": [{"action": "move_file", "params": {"source": ws + "\\nao-existe.txt", "destination": ws + "\\x.txt"}}]}
        self.lab.save_eval_set("um-caso", [{"id": "mover", "task": "mova nao-existe.txt para x.txt dentro de {ws}",
                                           "setup": {}, "expect": {"exists": ["x.txt"]}}])
        run = self.lab.run("um-caso", [self.variant["id"]], broken_tool, origin="simulado")
        self.assertEqual(run["results"][0]["status"], "falha_ferramenta")

        def offline(version, task):
            raise ProviderUnavailable("sem rede")
        run = self.lab.run("um-caso", [self.variant["id"]], offline, origin="simulado")
        self.assertEqual(run["results"][0]["status"], "indisponivel")
        self.assertIsNone(run["summary"][self.variant["id"]]["success_rate"])   # sem dado, sem taxa inventada

    def test_versions_diff_publish_and_restore(self):
        from core.harness import Harness
        h = Harness(self.dir)
        diff = self.lab.diff(self.base["id"], self.variant["id"])
        self.assertTrue(any(l.startswith("+instruções: Sempre confira") for l in diff))
        self.assertTrue(any(l.startswith("+effort: low") for l in diff))
        self.lab.publish(self.variant["id"], h)
        self.assertEqual(h.load()["agents"]["FILE"]["instructions"], "Sempre confira o destino antes de copiar.")
        self.lab.publish(self.base["id"], h)                                  # restaurar a anterior
        self.assertEqual(h.load()["agents"]["FILE"]["instructions"], self.base["instructions"])
        self.assertTrue(self.lab.version(self.base["id"])["published"])
        self.assertFalse(self.lab.version(self.variant["id"])["published"])
        with self.assertRaises(ValueError):                                   # variante identica nao duplica
            self.lab.create_variant("FILE", self.base["id"], "Sempre confira o destino antes de copiar.", {"effort": "low"})

    def test_variant_instructions_reach_the_agent_only_inside_the_experiment(self):
        from core.harness import Harness, instructions_override
        h = Harness(self.dir)
        with instructions_override("FILE", "regra da variante"):
            self.assertIn("regra da variante", h.agent_block("FILE"))
        self.assertNotIn("regra da variante", h.agent_block("FILE"))

    def test_effective_config_and_validation(self):
        eff = effective_config("FILE", self.variant)
        self.assertEqual((eff["agent"], eff["effort"], eff["version"]), ("FILE", "low", self.variant["id"]))
        self.assertIn("move_file", eff["tools"])
        self.assertNotIn("run_python", eff["tools"])
        for bad in ({"effort": "máximo"}, {"max_tokens": 10}, {"max_tokens": "muito"}, {"model": "dois nomes"}):
            with self.assertRaises(ValueError):
                validate_params(bad)
        with self.assertRaises(ValueError):
            self.lab.save_eval_set("x", [{"id": "a", "task": "sem pasta"}])
        with self.assertRaises(ValueError):
            self.lab.save_eval_set("x", [{"id": "a", "task": "use {ws}", "setup": {"../fora.txt": "x"}}])


class LabReplayBudgetToolsObservability(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="lab-test2-"))
        self.lab = Lab(self.dir)
        self.v = self.lab.versions("FILE")[0]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_simulated_mode_replays_the_recorded_real_plan_without_cost(self):
        from core.lab import replay_planner
        real = self.lab.run("arquivos-basico", [self.v["id"]], good_planner, origin="real")
        self.assertEqual(real["summary"][self.v["id"]]["passed"], 4)
        self.assertTrue(all("{ws}" in str(r["plan"]) for r in real["results"]))   # gravado sem a pasta temporaria
        sim = self.lab.run("arquivos-basico", [self.v["id"]], replay_planner(self.lab), origin="simulado")
        self.assertEqual(sim["summary"][self.v["id"]]["passed"], 4)
        self.assertEqual(sim["summary"][self.v["id"]]["cost_usd"], 0.0)
        self.assertEqual(sim["summary"][self.v["id"]]["origin"], "simulado")
        other = self.lab.create_variant("FILE", self.v["id"], "outra regra")
        none = self.lab.run("arquivos-basico", [other["id"]], replay_planner(self.lab), origin="simulado")
        self.assertEqual(none["summary"][other["id"]]["unavailable"], 4)           # sem gravacao: nao inventa

    def test_real_mode_without_provider_key_is_unavailable_not_failed(self):
        """Achado no primeiro teste real: sem chave, os casos contavam como falha da versao (0% de sucesso)."""
        from unittest.mock import patch
        from core.lab import real_planner

        def no_key():
            raise ValueError("ANTHROPIC_API_KEY nao configurada no .env")
        with patch("core.ai_client.get_client", no_key):
            run = self.lab.run("arquivos-basico", [self.v["id"]], real_planner, origin="real")
        s = run["summary"][self.v["id"]]
        self.assertEqual((s["unavailable"], s["failed"], s["success_rate"]), (4, 0, None))

    def test_budget_stops_a_real_run(self):
        def pricey(version, task):
            plan = good_planner(version, task)
            plan["metrics"]["cost_usd"] = 0.6
            return plan
        run = self.lab.run("arquivos-basico", [self.v["id"]], pricey, origin="real", budget_usd=1.0)
        self.assertEqual(run["status"], "orcamento")
        self.assertIn("orçamento", run["stopped_by"])
        self.assertEqual(run["summary"][self.v["id"]]["cancelled"], 2)

    def test_skills_tools_and_mcp_contract(self):
        from core.lab import skills_and_tools, test_mcp_tool
        st = skills_and_tools("FILE")
        names = [t["name"] for t in st["tools"]]
        self.assertIn("move_file", names)
        self.assertEqual(next(t for t in st["tools"] if t["name"] == "move_file")["params"], ["source", "destination"])
        self.assertTrue(all(m["readOnly"] for m in st["mcp"]))
        with self.assertRaises(ValueError):
            test_mcp_tool("apagar_tudo", {})
        with self.assertRaises(ValueError):
            test_mcp_tool("brain_search", {})                                        # obrigatorio faltando
        with self.assertRaises(ValueError):
            test_mcp_tool("brain_search", {"query": "x", "rm": "-rf"})              # fora do contrato
        out = test_mcp_tool("task_status", {})
        self.assertTrue(out["ok"] and isinstance(out["output"], str) and out["latency_ms"] >= 0)

    def test_observability_filters_and_links_events_to_the_task(self):
        from unittest.mock import patch
        from core.task_ledger import TaskLedger
        from core.lab import observe
        led = TaskLedger(root=self.dir / "tasks")
        led.begin("t1", "organizar a pasta de testes", source="texto")
        led.plan("t1", ["[FILE] organizar"])
        led.step_started("t1", 1, "FILE", "move_file", {"source": "a", "destination": "b"}, "mover")
        led.step_finished("t1", 1, "move_file", {"success": True, "result": "chave sk-ant-fake-abcdefghijklmnopqrstuvwxyz movida"})
        led.finish("t1", "completed", verified=True)
        led.begin("t2", "abrir site", source="voz")
        led.step_started("t2", 1, "WEB", "open_url", {"url": "x"}, "abrir")
        led.finish("t2", "failed", error="sem rede")
        with patch("core.task_ledger.get_ledger", lambda: led):
            files = observe(agent="FILE")
            failed = observe(state="failed")
        self.assertEqual([t["id"] for t in files], ["t1"])
        self.assertEqual([t["id"] for t in failed], ["t2"])
        ev = files[0]["events"]
        self.assertTrue(all(e["at"] for e in ev))
        started = next(e for e in ev if e["type"] == "step_started")
        self.assertEqual((started["agent"], started["action"]), ("FILE", "move_file"))
        self.assertNotIn("sk-ant-fake-abcdefghijklmnopqrstuvwxyz", str(ev))              # segredo mascarado


class LabOptimization(unittest.TestCase):
    """Etapa 5: feedback, promocao so com evidencia real, pesquisa autonoma que nunca publica sozinha."""

    def setUp(self):
        from core.harness import Harness
        self.dir = Path(tempfile.mkdtemp(prefix="lab-opt-"))
        self.lab = Lab(self.dir)
        self.h = Harness(self.dir)
        self.base = self.lab.versions("FILE", self.h)[0]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def planner_by_instructions(self, version, task):
        """Versao com 'confira o destino' acerta a copia; a referencia erra (como sloppy_planner)."""
        good = "confira o destino" in (version.get("instructions") or "").lower()
        return (good_planner if good else sloppy_planner)(version, task)

    def test_feedback_is_stored_on_the_case(self):
        run = self.lab.run("arquivos-basico", [self.base["id"]], sloppy_planner, origin="real")
        hit = self.lab.add_feedback(run["id"], self.base["id"], "copiar", "copiou para c.txt, eu pedi b.txt")
        self.assertEqual(hit["feedback"][0]["note"], "copiou para c.txt, eu pedi b.txt")
        with self.assertRaises(ValueError):
            self.lab.add_feedback(run["id"], self.base["id"], "copiar", "  ")

    def test_promotion_needs_real_evidence_and_no_regression(self):
        v = self.lab.create_variant("FILE", self.base["id"], "Confira o destino antes de copiar.")
        self.assertFalse(self.lab.promotion_check(v["id"])["ok"])                       # sem experimento
        self.lab.run("arquivos-basico", [self.base["id"], v["id"]], self.planner_by_instructions, origin="simulado")
        self.assertFalse(self.lab.promotion_check(v["id"])["ok"])                       # simulado nao conta
        with self.assertRaises(ValueError):
            self.lab.promote(v["id"], self.h)
        self.lab.run("arquivos-basico", [self.base["id"], v["id"]], self.planner_by_instructions, origin="real")
        check = self.lab.promotion_check(v["id"])
        self.assertTrue(check["ok"], check)
        self.lab.promote(v["id"], self.h)
        self.assertEqual(self.h.load()["agents"]["FILE"]["instructions"], "Confira o destino antes de copiar.")
        # uma variante que piora em um caso que a publicada passa nao pode ser promovida
        worse = self.lab.create_variant("FILE", v["id"], "Copie para onde achar melhor.")
        self.lab.run("arquivos-basico", [v["id"], worse["id"]], self.planner_by_instructions, origin="real")
        check = self.lab.promotion_check(worse["id"])
        self.assertFalse(check["ok"])
        self.assertTrue(any("piorou em: copiar" in r for r in check["reasons"]))

    def test_research_proposes_tests_and_never_publishes(self):
        self.lab.run("arquivos-basico", [self.base["id"]], sloppy_planner, origin="real")   # falhas conhecidas
        seen = {}

        def propose(objective, instructions, failures):
            seen["failures"] = failures
            return "Confira o destino antes de copiar e use os nomes do pedido."
        out = self.lab.research("FILE", "acertar o nome do arquivo de destino", propose,
                                self.planner_by_instructions, origin="real")
        self.assertEqual([f["case"] for f in seen["failures"]], ["copiar"])            # usou as falhas reais
        s = out["run"]["summary"]
        self.assertEqual((s[out["baseline"]]["passed"], s[out["variant"]["id"]]["passed"]), (3, 4))
        self.assertTrue(out["verdict"]["ok"])                                          # promovivel...
        self.assertEqual(self.h.load()["agents"].get("FILE", {}).get("instructions", ""), "")   # ...mas nao publicada
        sim = self.lab.research("FILE", "acertar o nome", propose, self.planner_by_instructions, origin="simulado")
        self.assertFalse(sim["verdict"]["ok"])
        with self.assertRaises(ValueError):
            self.lab.research("FILE", "  ", propose, self.planner_by_instructions, origin="real")

    def test_fine_tuning_is_reported_unavailable_with_requirements(self):
        from core.lab import training_status
        st = training_status()
        self.assertEqual(st["fine_tuning"], "indisponível")
        self.assertGreaterEqual(len(st["requires"]), 3)


if __name__ == "__main__":
    unittest.main()
