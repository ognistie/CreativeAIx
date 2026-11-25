import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.brain_store import BrainStore
from core.lab_drafts import draft_route


class LabDraftRoutes(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.store = BrainStore(root / "base", root / "personal")
        self.note = "10 Agentes/Rascunhos/conferencia.md"
        self.store.create(self.note, "---\ntipo: agente-rascunho\nbase: FILE\n---\n# Conferência\n")

    def call(self, action, **values):
        return draft_route(self.store, {"note": self.note, "action": action, **values})

    def test_preview_save_apply_and_original_route(self):
        route = {"agent": "DATA", "prefix": "conferir planilha"}
        case = {"request": "Conferir planilha de teste"}
        before = self.store.read(self.note)
        preview = self.call("test", route=route, **case)["trial"]
        self.assertEqual(preview["agent"], "DATA")
        self.assertEqual(self.store.read(self.note), before)
        self.assertNotIn("rota_aplicada", self.call("save", route=route))
        self.call("apply", confirmed=True)
        self.assertEqual(self.call("test", applied=True, **case)["trial"], preview)
        with patch("core.lab.fixture_planner", return_value={"routing": {"subtasks": [{"agent": "FILE"}]}}):
            original = self.call("test", applied=True, request="Abra a pasta de teste")["trial"]
        self.assertFalse(original["matched"])
        self.assertEqual(original["original"], ["FILE"])

    def test_invalid_agent_and_unconfirmed_apply_leave_note_intact(self):
        before = self.store.read(self.note)
        with self.assertRaises(ValueError):
            self.call("save", route={"agent": "MAESTRO", "prefix": "rodar código"})
        with self.assertRaises(ValueError):
            self.call("apply")
        with self.assertRaises(FileNotFoundError):
            draft_route(self.store, {"note": "../conferencia.md", "action": "load"})
        self.assertEqual(self.store.read(self.note), before)


class AppliedProfileReachesRealRequests(unittest.TestCase):
    """Rota aplicada no Lab vale nos pedidos reais: perfil sobre um agente-base, sem capacidade nova."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.store = BrainStore(root / "base", root / "personal")
        self.note = "10 Agentes/Rascunhos/conferencia.md"
        self.store.create(self.note, "---\ntipo: agente-rascunho\nbase: DATA\nnome: Conferente\n---\n"
                                     "Sempre destaque divergências em vermelho.\n")

    def apply(self, prefix="conferir planilha", agent="DATA"):
        call = lambda action, **v: draft_route(self.store, {"note": self.note, "action": action, **v})
        call("save", route={"agent": agent, "prefix": prefix})
        call("apply", confirmed=True)

    def test_saved_but_not_applied_has_no_effect(self):
        from core.lab_drafts import profile_for
        draft_route(self.store, {"note": self.note, "action": "save",
                                 "route": {"agent": "DATA", "prefix": "conferir planilha"}})
        self.assertIsNone(profile_for("conferir planilha de vendas", self.store))

    def test_applied_route_routes_the_request_to_the_base_agent(self):
        from agents.maestro import profile_plan
        self.apply()
        plan = profile_plan("Conferir planilha de vendas de março", store=self.store)
        self.assertEqual([s["agent"] for s in plan["subtasks"]], ["DATA"])
        self.assertEqual(plan["profile"]["note"], self.note)
        self.assertTrue(plan["validation"]["approved"])
        self.assertIsNone(profile_plan("abrir a planilha de vendas", store=self.store))   # prefixo é inicio
        self.assertIsNone(profile_plan("conferir planilhas", store=self.store))            # palavra inteira

    def test_profile_text_reaches_the_agent_as_preference(self):
        from core.lab_drafts import profile_block, profile_for
        self.apply()
        profile = profile_for("conferir planilha de vendas", self.store, agent="DATA")
        block = profile_block(profile)
        self.assertIn("destaque divergências", block)
        self.assertIn("nunca como permissão", block)
        self.assertIsNone(profile_for("conferir planilha de vendas", self.store, agent="WEB"))

    def test_factory_note_is_never_a_profile(self):
        from core.lab_drafts import applied_profiles
        base = Path(self.store.base) / "10 Agentes" / "Rascunhos"
        base.mkdir(parents=True, exist_ok=True)
        (base / "fabrica.md").write_text('---\ntipo: agente-rascunho\nbase: WEB\nrota_aplicada: '
                                         '{"agent": "WEB", "prefix": "comprar"}\n---\nx\n', encoding="utf-8")
        self.assertEqual(applied_profiles(self.store), [])

    def test_plan_rejected_by_policy_falls_back_to_the_maestro(self):
        from agents.maestro import profile_plan
        from core.plan_validator import Validation
        self.apply()
        refused = Validation()
        refused.add("POL-000", "teste")
        with patch("core.plan_validator.validate_plan", return_value=refused):
            self.assertIsNone(profile_plan("conferir planilha de vendas", store=self.store))


class NoteWriteSurvivesTransientLock(unittest.TestCase):
    def test_replace_retries_a_short_windows_lock(self):
        from core import brain_store
        calls = []

        def flaky(src, dst):
            calls.append(src)
            if len(calls) < 3:
                raise PermissionError(5, "Acesso negado")
        with patch.object(brain_store.os, "replace", side_effect=flaky), patch.object(brain_store.time, "sleep"):
            brain_store._replace("a.tmp", "a.md")
        self.assertEqual(len(calls), 3)
        with patch.object(brain_store.os, "replace", side_effect=PermissionError(5, "x")), \
                patch.object(brain_store.time, "sleep"), self.assertRaises(PermissionError):
            brain_store._replace("a.tmp", "a.md")
