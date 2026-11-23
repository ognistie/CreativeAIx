"""Incidente 2026-11-17 (conversa por voz: Bloco de Notas, Google, "salvar o arquivo") e a camada de harness da
visao.

1. "salvar o arquivo no Bloco de Notas" ia para a rotina do editor, que so sabe abrir e criar documento em
   branco: abria um documento NOVO, nao salvava nada e saia como concluido. Agora a acao vai para o piloto na
   janela aberta, e um plano que nao salva e reprovado com o motivo (a falha aparece, nao vira sucesso).
2. Perguntas sobre a tela ("voce esta vendo o YouTube?") eram respondidas pelo modelo de voz sem olhar. Agora o
   Vision olha e responde; nada e executado.
"""

import os
import threading
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-not-real")


class SaveInOpenEditor(unittest.TestCase):
    def plan(self, task, params):
        from agents.desktop_agent import DesktopAgent
        return DesktopAgent()._plan_steps({"task": task, "params": params})["steps"]

    def test_save_acts_on_the_open_document_and_never_opens_a_blank_one(self):
        for task in ("salvar o arquivo no Bloco de Notas", "salva o texto do bloco de notas", "grava esse arquivo no notepad"):
            steps = self.plan(task, {"app": "notepad", "action_type": "save"})
            actions = [s["action"] for s in steps]
            self.assertEqual(actions, ["app_task"], task)
            self.assertNotIn("blank_document", actions)

    def test_write_then_save_writes_first_then_saves(self):
        steps = self.plan("abre o bloco de notas, escreve oi e salva", {"app": "notepad", "text": "oi"})
        actions = [s["action"] for s in steps]
        self.assertIn("app_type", actions)
        self.assertEqual(actions[-1], "app_task")

    def test_plain_open_and_write_are_unchanged(self):
        self.assertEqual([s["action"] for s in self.plan("abre o bloco de notas", {"app": "notepad"})],
                         ["app_search", "wait", "blank_document"])

    def test_plan_that_does_not_save_is_reproved_with_the_reason(self):
        from agents.desktop_agent import _build_steps
        from core.plan_validator import validate_steps
        task = "salvar o arquivo no Bloco de Notas"
        old = _build_steps("notepad", {"action_type": "save"})                      # o plano do incidente
        check = validate_steps("DESKTOP", {"task": task, "params": {}}, old, task)
        self.assertFalse(check.approved)
        self.assertIn("nenhum passo salva", check.summary())
        ctrl_s = [{"action": "hotkey", "params": {"keys": ["ctrl", "s"]}}]
        self.assertTrue(validate_steps("DESKTOP", {"task": task, "params": {}}, ctrl_s, task).approved)


class ScreenQuestions(unittest.TestCase):
    def test_detects_questions_about_the_screen(self):
        from core.screen_question import is_screen_question
        for text in ("você está vendo o YouTube?", "tá vendo esse botão?", "o que tem na tela?", "consegue ver o vídeo?",
                     "o que você está vendo agora", "olha a tela"):
            self.assertTrue(is_screen_question(text), text)
        for text in ("abre o YouTube", "pesquisa Osasco", "olha a tela e clica em enviar", "salvar o arquivo", "Osasco"):
            self.assertFalse(is_screen_question(text), text)

    def test_resolver_routes_to_look_without_the_model(self):
        from core.followup import resolve
        from core.session import Session
        llm = Mock(side_effect=AssertionError("nao deve chamar o modelo"))
        r = resolve("você está vendo o YouTube?", Session(), llm=llm)
        self.assertEqual(r["kind"], "look")

    def test_vision_only_answers_and_hedges_when_unsure(self):
        from core.screen_question import answer
        vision = Mock()
        vision.read_local.return_value = None      # sem leitura local: vai para a imagem
        vision.look.return_value = {"answer": "O YouTube está aberto na busca por skate.", "seen": "Chrome", "confidence": 0.9}
        out = answer("você está vendo o YouTube?", vision)
        self.assertTrue(out["ok"])
        self.assertIn("YouTube", out["answer"])
        vision.look.assert_called_once()
        self.assertEqual([c[0] for c in vision.method_calls if c[0] not in ("look", "read_local", "restore_browser")], [])
        vision.look.return_value = {"answer": "Há um vídeo pausado.", "confidence": 0.4}
        self.assertTrue(answer("tá vendo o vídeo?", vision)["answer"].startswith("Não tenho certeza"))
        vision.look.return_value = {"error": True}
        self.assertFalse(answer("tá vendo?", vision)["ok"])

    def test_voice_delegates_screen_questions_instead_of_answering_blind(self):
        from core.voice.understand import understand
        llm = Mock(side_effect=AssertionError("a voz nao responde sobre a tela de cabeca"))
        u = understand("você está vendo o YouTube?", 0.95, "", [], llm=llm)
        self.assertEqual(u["kind"], "command")
        self.assertEqual(u["via"], "tela")

    def test_controller_answers_look_without_executing_anything(self):
        from desktop.controller import Controller
        from core.session import Session
        c = Controller.__new__(Controller)
        c.state, c._lock, c._run_id, c._tls = {"running": True}, threading.Lock(), 1, threading.local()
        c._cancel_event, c._plan_gate = threading.Event(), threading.Event()
        c._plan_ok, c._plan_token, c._voice_hints = False, "", {}
        c._ai_client, c._config = Mock(metrics={}), Mock(get=lambda key, default=None: default)
        c._brain = Mock(last_skills={})
        c.session = Session()
        c.session.save = lambda *a, **k: None
        c.engine = Mock(vision=Mock(look=Mock(return_value={"answer": "Sim, o YouTube está aberto.", "confidence": 0.95})))
        c.maestro = Mock()
        events = []
        c._emit = lambda name, payload=None: events.append((name, payload or {}))
        c._after_turn, c._metrics_delta, c._emit_usage = Mock(), (lambda b, a: {}), (lambda: None)
        from core.task_ledger import TaskLedger
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch("core.task_ledger.get_ledger", return_value=TaskLedger(Path(tmp.name))), \
                patch("desktop.controller.history_store.append"):
            c._run("você está vendo o YouTube?", False, False, 1)
        c.maestro.analyze.assert_not_called()
        c.engine.execute.assert_not_called()
        observed = next(payload for name, payload in events if name == "answer")
        self.assertEqual(observed["msg"], "Sim, o YouTube está aberto.")
        self.assertTrue(observed["observation"]["ok"])
        self.assertEqual(observed["observation"]["confidence"], 0.95)


if __name__ == "__main__":
    unittest.main()


class LocalFirstLook(unittest.TestCase):
    """Perguntas que o titulo, a URL e os textos da janela respondem nao gastam modelo."""

    YT = {"title": "skate - YouTube - Google Chrome", "url": "https://www.youtube.com/results?search_query=skate",
          "text": "Inscrever-se\nskate park tour", "box": (0, 0, 1920, 1032)}

    def test_presence_target(self):
        from core.screen_question import presence_target
        self.assertEqual(presence_target("você está vendo o YouTube?"), "youtube")
        self.assertEqual(presence_target("tá vendo a planilha de vendas agora?"), "planilha de vendas")
        self.assertEqual(presence_target("o que você está vendo agora"), "")
        self.assertEqual(presence_target("o que tem na tela?"), "")

    def test_answers_from_title_and_url_without_the_model(self):
        from core.screen_question import answer
        vision = Mock()
        vision.read_local.return_value = self.YT
        vision.look.side_effect = AssertionError("nao deve chamar o modelo")
        out = answer("você está vendo o YouTube?", vision)
        self.assertTrue(out["ok"])
        self.assertEqual(out["via"], "local")
        self.assertTrue(out["answer"].startswith("Sim"))
        out = answer("qual site está aberto?", vision)
        self.assertIn("youtube.com", out["answer"])
        out = answer("tá vendo o Gmail?", vision)
        self.assertTrue(out["answer"].startswith("Não estou vendo"))
        vision.restore_browser.assert_called()

    def test_text_of_the_window_counts(self):
        from core.screen_question import local_answer
        out = local_answer("consegue ver o skate park?", self.YT)
        self.assertTrue(out["answer"].startswith("Sim"))

    def test_visual_questions_go_to_the_assistant_model_with_context(self):
        from core.screen_question import answer
        vision = Mock()
        vision.read_local.return_value = self.YT
        vision.look.return_value = {"answer": "O vídeo está pausado.", "confidence": 0.9, "model": "claude-haiku-5-5"}
        out = answer("o vídeo está tocando? você está vendo o vídeo?", vision)
        self.assertEqual(out["via"], "claude-haiku-5-5")
        vision.look.assert_called_once_with("o vídeo está tocando? você está vendo o vídeo?", context=self.YT)
        vision.look.reset_mock()
        answer("o que tem na tela?", vision)
        vision.look.assert_called_once()

    def test_look_escalates_only_when_the_assistant_is_unsure(self):
        from core.vision import VisionEngine
        v = VisionEngine.__new__(VisionEngine)
        v.model, v.effort, v.assist_model, v.assist_effort = "claude-sonnet-5", "low", "claude-haiku-5-5", "low"
        v._hidden_windows, v.screen_w, v.screen_h = [], 1920, 1080
        v._capture = Mock(return_value=("b64", None, 1.0))
        calls = []
        def call(prompt, b64, model=None, effort=None, max_tokens=4000):
            calls.append(model or v.model)
            return {"answer": "x", "confidence": 0.9 if model is None else 0.3}
        v._call = call
        with patch.object(VisionEngine, "_hide_own", lambda self: None):
            out = v.look("o que tem na tela?", context={"title": "Bloco de Notas", "box": (0, 0, 800, 600)})
        self.assertEqual(calls, ["claude-haiku-5-5", "claude-sonnet-5"])
        self.assertEqual(out["model"], "claude-sonnet-5")
        calls.clear()
        v._call = lambda prompt, b64, model=None, effort=None, max_tokens=4000: (calls.append(model), {"answer": "ok", "confidence": 0.8})[1]
        with patch.object(VisionEngine, "_hide_own", lambda self: None):
            self.assertEqual(v.look("o que tem na tela?")["model"], "claude-haiku-5-5")
        self.assertEqual(calls, ["claude-haiku-5-5"])
        self.assertEqual(v._capture.call_args_list[-1].kwargs.get("max_side"), 1024)

    def test_find_element_crops_the_front_window_and_returns_screen_coordinates(self):
        from core.vision import VisionEngine
        v = VisionEngine.__new__(VisionEngine)
        v.model, v.effort, v._hidden_windows, v.screen_w, v.screen_h = "m", None, [], 1920, 1080
        v._extract_ocr_target = lambda d: None
        v.foreground_box = lambda: (100, 50, 800, 600)
        v._capture = Mock(return_value=("b64", Mock(width=800, height=600), 1.0))
        v._call = lambda prompt, b64, **kw: {"found": True, "x": 10, "y": 20, "confidence": 0.9}
        with patch.object(VisionEngine, "_hide_own", lambda self: None):
            res = v.find_element('botão "Enviar"')
        self.assertEqual((res["x"], res["y"]), (110, 70))
        self.assertEqual(v._capture.call_args_list[0].args[0], (100, 50, 800, 600))
