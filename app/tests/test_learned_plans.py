"""Planos aprendidos (auto-aperfeiçoamento): aprende o roteamento que se repete, deixa de chamar o modelo, desaprende
na falha e nunca pula as políticas. Sem rede, sem modelo, sem tela; a loja vai para uma pasta temporária."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import learned_plans as L


def search_plan(query: str) -> dict:
    """O plano que o Maestro devolve para 'pesquisa X no google' (formato real dos testes do Maestro)."""
    from urllib.parse import quote_plus
    return {"analysis": "pesquisar no Google", "skills": [], "subtasks": [{
        "agent": "WEB", "task": f"pesquisar {query} no Google",
        "params": {"query": query, "url": f"https://www.google.com/search?q={quote_plus(query)}"}}]}


class Templates(unittest.TestCase):
    def test_slots_come_from_what_the_person_said(self):
        self.assertEqual(L.extract("pesquisa receita de bolo no google"),
                         ("pesquisa ⟨consulta1⟩ no google", {"consulta1": "receita de bolo"}))
        self.assertEqual(L.extract('escreve "lista do mercado" no bloco de notas')[0],
                         "escreve ⟨texto1⟩ no bloco de notas")
        self.assertEqual(L.extract("abre o site g1.globo.com")[0], "abre o site ⟨site1⟩")
        self.assertEqual(L.extract("cria uma planilha com 12 meses")[0], "cria uma planilha com ⟨numero1⟩ meses")

    def test_same_kind_of_request_shares_the_template(self):
        a = L.extract("Pesquisa preço do dólar no Google")[0]
        b = L.extract("pesquisa horário do jogo no google")[0]
        self.assertEqual(a, b)

    def test_plan_with_invented_content_is_not_learnable(self):
        plan = {"subtasks": [{"agent": "DESKTOP", "task": "escrever um poema no bloco de notas",
                              "params": {"app": "notepad", "text": "Rosas são vermelhas, violetas azuis"}}]}
        self.assertIsNone(L.plan_template("escreve um poema no bloco de notas", plan))

    def test_shortcut_and_clarification_plans_are_not_learned(self):
        self.assertIsNone(L.plan_template("abre o youtube", {"fast_path": "abrir", "subtasks": [{"agent": "WEB"}]}))
        self.assertIsNone(L.plan_template("abre aquilo", {"needs_clarification": True}))

    def test_encoded_query_in_url_becomes_a_slot(self):
        shaped = L.plan_template("pesquisa receita de bolo no google", search_plan("receita de bolo"))
        self.assertIn("⟨consulta1|url⟩", shaped["subtasks"][0]["params"]["url"])
        self.assertEqual(shaped["subtasks"][0]["params"]["query"], "⟨consulta1⟩")

    def test_model_dropping_accents_still_matches_the_slot(self):
        # Medido com o Maestro real: "tênis de corrida" voltou como "tenis de corrida"
        plan = {"subtasks": [{"agent": "WEB", "task": "pesquisar tenis de corrida",
                              "params": {"url": "https://www.mercadolivre.com.br", "query": "tenis de corrida"}}]}
        shaped = L.plan_template("pesquisa tênis de corrida no mercado livre", plan)
        self.assertEqual(shaped["subtasks"][0]["params"]["query"], "⟨consulta1⟩")

    def test_context_dependent_requests_never_use_templates(self):
        self.assertTrue(L.depends_on_context("pesquisa isso de novo no google"))
        self.assertFalse(L.depends_on_context("pesquisa receita de bolo no google"))


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = L.LearnedPlans(Path(self.tmp.name) / "learned.json")

    def tearDown(self):
        self.tmp.cleanup()

    def teach(self, queries):
        return [self.store.observe(f"pesquisa {q} no google", search_plan(q), True) for q in queries]

    def test_promotes_after_three_identical_successes(self):
        self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))
        self.assertEqual(self.teach(["receita de bolo", "preço do dólar", "horário do jogo"]),
                         ["candidate", "candidate", "promoted"])
        plan = self.store.plan_for("pesquisa previsão do tempo no google")
        self.assertEqual(plan["fast_path"], "aprendido")
        params = plan["subtasks"][0]["params"]
        self.assertEqual(params["query"], "previsão do tempo")
        self.assertEqual(params["url"], "https://www.google.com/search?q=previs%C3%A3o+do+tempo")
        self.assertIn("sem IA", plan["analysis"])

    def test_a_failure_resets_the_streak(self):
        self.teach(["receita de bolo", "preço do dólar"])
        self.store.observe("pesquisa horário do jogo no google", search_plan("horário do jogo"), False)
        self.teach(["previsão do tempo"])
        self.assertIsNone(self.store.plan_for("pesquisa cotação do euro no google"))

    def test_failed_replay_demotes_and_two_failures_block(self):
        self.teach(["receita de bolo", "preço do dólar", "horário do jogo"])
        plan = self.store.plan_for("pesquisa cotação do euro no google")
        self.assertEqual(self.store.observe("pesquisa cotação do euro no google", plan, False), "candidate")
        self.assertIsNone(self.store.plan_for("pesquisa cotação do euro no google"))
        self.teach(["a", "b", "c"])
        plan = self.store.plan_for("pesquisa cotação do euro no google")
        self.assertEqual(self.store.observe("pesquisa cotação do euro no google", plan, False), "blocked")
        self.assertEqual(self.teach(["d", "e", "f"])[-1], "blocked")
        self.assertIsNone(self.store.plan_for("pesquisa cotação do euro no google"))

    def test_successful_replay_keeps_counting(self):
        self.teach(["receita de bolo", "preço do dólar", "horário do jogo"])
        plan = self.store.plan_for("pesquisa cotação do euro no google")
        self.assertEqual(self.store.observe("pesquisa cotação do euro no google", plan, True), "promoted")
        self.assertEqual(self.store.entries()[0]["replays"], 1)

    def test_wording_and_skills_do_not_split_the_same_plan(self):
        # Medido com o Maestro real: mesmo plano, task com "Mercado Livre" ou "mercado livre" e skills variando
        for i, q in enumerate(["receita de bolo", "preço do dólar", "horário do jogo"]):
            plan = search_plan(q)
            plan["skills"] = ["web"] if i % 2 else []
            plan["subtasks"][0]["task"] = plan["subtasks"][0]["task"].upper() if i == 1 else plan["subtasks"][0]["task"]
            status = self.store.observe(f"pesquisa {q} no google", plan, True)
        self.assertEqual(status, "promoted")

    def test_a_different_plan_restarts_learning(self):
        self.teach(["receita de bolo", "preço do dólar"])
        other = search_plan("horário do jogo")
        other["subtasks"][0]["agent"] = "DESKTOP"
        other["subtasks"][0]["params"] = {"app": "chrome"}
        self.store.observe("pesquisa horário do jogo no google", other, True)
        self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))

    def test_planner_change_makes_templates_stale(self):
        self.teach(["receita de bolo", "preço do dólar", "horário do jogo"])
        with patch.object(L, "planner_version", return_value="outro-prompt"):
            self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))

    def test_replayed_plan_still_passes_the_plan_policies(self):
        self.teach(["receita de bolo", "preço do dólar", "horário do jogo"])
        with patch("core.plan_validator.validate_plan") as validate:
            validate.return_value.approved = False
            self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))

    def test_switch_off_and_forget(self):
        self.teach(["receita de bolo", "preço do dólar", "horário do jogo"])
        with patch.object(L, "_enabled", return_value=False):
            self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))
        key = self.store.entries()[0]["key"]
        self.assertTrue(self.store.forget(key))
        self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))

    def test_personal_data_is_redacted_in_the_store(self):
        plan = {"subtasks": [{"agent": "WEB", "task": "abrir o site", "params": {"url": "https://ze@x.com"}}]}
        self.store.observe("abre o email ze@x.com", plan, True)
        raw = (Path(self.tmp.name) / "learned.json").read_text(encoding="utf-8")
        self.assertNotIn("ze@x.com", json.loads(raw)["entries"][next(iter(json.loads(raw)["entries"]))]["template"])

    def test_corrupt_store_is_ignored(self):
        (Path(self.tmp.name) / "learned.json").write_text("{lixo", encoding="utf-8")
        self.assertIsNone(self.store.plan_for("pesquisa previsão do tempo no google"))
        self.assertEqual(self.teach(["a"]), ["candidate"])


if __name__ == "__main__":
    unittest.main()
