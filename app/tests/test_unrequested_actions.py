"""Auditoria de 23/11/2026: achados C1-C4 (acao sem pedido). Sem rede, sem modelo real, sem tela.

C1  comentario ("legal, ficou bom") virava tarefa: o resolvedor nao tinha o tipo "conversa".
C2  a pergunta pendente capturava qualquer fala por 3 minutos (TV, comentario, pergunta de andamento).
C3  Enter num app com campo sem nome e Delete/Shift+Delete passavam sem confirmacao.
C4  ligar, sair da conta, bloquear, seguir/curtir e girias de envio nao eram reconhecidos como efeito.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import action_risk as R
from core.followup import resolve
from core.session import Session
from core.voice.understand import understand


def no_llm(system, user):
    raise AssertionError("o modelo nao deveria ser chamado")


def fixed_llm(payload: dict):
    return lambda system, user: json.dumps(payload)


def code_session() -> Session:
    folder = tempfile.mkdtemp()
    Path(folder, "index.html").write_text("<html></html>", encoding="utf-8")
    s = Session()
    s.remember_code(folder, ["index.html"])
    s.add_turn("cria um site de receitas", "cria um site de receitas", "new", ["CODE"], True, "Site criado")
    return s


def pending_session() -> Session:
    s = Session()
    s.add_turn("cria um site de receitas", "cria um site de receitas", "new", ["CODE"], True, "Site criado")
    s.set_pending("Qual cor você quer nos botões?", "mudar a cor dos botões do site", None)
    return s


class C1_CommentNeverActs(unittest.TestCase):
    COMMENTS = ("legal, ficou bom", "show de bola, gostei do azul", "nossa que lindo", "ficou ótimo", "adorei")

    def test_model_question_without_question_mark_is_a_chat(self):
        llm = fixed_llm({"kind": "question", "task": "revisar o site e ajustar o layout",
                         "answer": "Que bom que gostou!", "target": "code"})
        for said in self.COMMENTS:
            res = resolve(said, code_session(), llm=llm)
            self.assertEqual(res["kind"], "question", said)
            self.assertNotIn("ajustar o layout", res["task"], said)
            self.assertTrue(res["answer"], said)

    def test_explicit_chat_kind_never_acts(self):
        llm = fixed_llm({"kind": "chat", "task": "trocar a cor para azul", "answer": "Também gosto!", "target": "code"})
        res = resolve("gostei do azul", code_session(), llm=llm)
        self.assertEqual((res["kind"], res["answer"]), ("question", "Também gosto!"))

    def test_common_praise_is_answered_without_the_model(self):
        for said in ("legal, ficou bom", "que legal", "ficou lindo demais", "muito bom, valeu"):
            res = resolve(said, code_session(), llm=no_llm)
            self.assertEqual((res["kind"], res["via"]), ("question", "papo"), said)

    def test_a_command_mislabeled_as_question_still_acts(self):
        llm = fixed_llm({"kind": "question", "task": "trocar a cor dos botões para azul",
                         "answer": "Já está azul.", "target": "code"})
        res = resolve("troca a cor dos botões pra azul", code_session(), llm=llm)
        self.assertEqual(res["kind"], "continue")
        self.assertEqual(res["target"], "code")

    def test_a_real_question_is_still_answered(self):
        llm = fixed_llm({"kind": "question", "task": "", "answer": "Ficou em C:/site.", "target": "none"})
        res = resolve("onde ficou o site?", code_session(), llm=llm)
        self.assertEqual((res["kind"], res["answer"]), ("question", "Ficou em C:/site."))


class C2_PendingQuestionDoesNotCaptureEverything(unittest.TestCase):
    def test_status_question_is_answered_and_the_question_waits(self):
        s = pending_session()
        res = resolve("como está o site?", s, llm=no_llm)
        self.assertEqual(res["via"], "status")
        self.assertNotIn("resposta à pergunta", res["task"])
        self.assertIsNotNone(s.pending)

    def test_another_question_is_not_an_answer(self):
        s = pending_session()
        res = resolve("qual a previsão do tempo amanhã", s, llm=fixed_llm({"kind": "new", "task": "ver previsão"}))
        self.assertNotEqual(res["via"], "pending")
        self.assertNotIn("resposta à pergunta", res["task"])

    def test_self_contained_request_drops_the_question(self):
        for said in ("pesquisa receita de bolo", "pesquisa voo para recife"):
            s = pending_session()
            res = resolve(said, s, llm=fixed_llm({"kind": "new", "task": said}))
            self.assertNotEqual(res["via"], "pending", said)
            self.assertIsNone(s.pending, said)

    def test_real_answers_still_continue_the_request(self):
        for said in ("azul", "azul claro", "faz os botões redondos", "o mesmo tom do logo", "cor #3366ff"):
            res = resolve(said, pending_session(), llm=no_llm)
            self.assertEqual(res["via"], "pending", said)
            self.assertIn("resposta à pergunta", res["task"], said)

    def test_unrelated_comment_goes_to_the_model_and_is_a_chat(self):
        chat = fixed_llm({"kind": "chat", "task": "", "answer": "Puxado, né? Descansa um pouco.", "target": "none"})
        for said in ("tô cansado hoje", "minha mãe ligou agora há pouco", "hoje o trânsito estava horrível"):
            s = pending_session()
            res = resolve(said, s, llm=chat)
            self.assertEqual((res["kind"], res["via"]), ("question", "chat"), said)
            self.assertIsNotNone(s.pending, said)     # a pergunta continua esperando a resposta

    def test_longer_answer_is_joined_by_the_model(self):
        s = pending_session()
        llm = fixed_llm({"kind": "new", "task": "mudar a cor dos botões do site para azul claro com borda arredondada",
                         "target": "none"})
        res = resolve("azul claro com borda arredondada", s, llm=llm)
        self.assertEqual(res["kind"], "new")
        self.assertIn("azul claro", res["task"])
        self.assertIsNone(s.pending)

    def test_without_the_model_a_comment_never_becomes_a_task(self):
        def down(system, user):
            raise ConnectionError("sem rede")
        for s in (pending_session(), Session()):
            res = resolve("tô cansado hoje", s, llm=down)
            self.assertEqual(res["kind"], "question")

    def test_voice_record_mode_sends_unrelated_comment_to_the_model(self):
        chat = fixed_llm({"kind": "chat", "command": "", "reply": "Descansa!", "confidence": 0.9})
        s = pending_session()
        u = understand("tô cansado hoje", 1.0, s.context_block(), [], llm=chat, session=s, mode="record")
        self.assertEqual(u["kind"], "chat")

    def test_live_voice_sends_long_unrelated_speech_to_the_model(self):
        noise = fixed_llm({"kind": "noise", "command": "", "reply": "", "confidence": 0.9})
        for said in ("hoje tá calor né", "a novela começou agora", "liga a tv ai"):
            s = pending_session()
            u = understand(said, 1.0, s.context_block(), [], llm=noise, session=s, mode="live")
            self.assertEqual(u["kind"], "noise", said)

    def test_live_voice_short_answer_still_skips_the_model(self):
        s = pending_session()
        u = understand("azul", 1.0, s.context_block(), [], llm=no_llm, session=s, mode="live")
        self.assertEqual((u["kind"], u["via"], u["command"]), ("command", "pendente", "azul"))

    def test_voice_question_or_chat_is_never_the_answer(self):
        chat = fixed_llm({"kind": "chat", "command": "", "reply": "Imagina!", "confidence": 0.9})
        for mode in ("record", "live"):
            for said in ("obrigado", "como está o site?", "qual a previsão do tempo amanhã?"):
                s = pending_session()
                u = understand(said, 1.0, s.context_block(), [], llm=chat, session=s, mode=mode)
                self.assertNotEqual(u["via"], "pendente", (mode, said))

    def test_prompt_tells_the_model_unrelated_speech_is_not_an_answer(self):
        from core.voice.understand import SYSTEM
        self.assertIn("Fala sem relação com a pergunta", SYSTEM)


class C3_KeyboardEffects(unittest.TestCase):
    def test_enter_in_unnamed_app_field_sends(self):
        self.assertEqual(R.ui_risk("press", "", key="enter", app=True), "enviar")
        self.assertEqual(R.ui_risk("type", "", submit=True, app=True), "enviar")

    def test_enter_in_messaging_window_sends_whatever_the_field_name(self):
        self.assertEqual(R.ui_risk("press", "Caixa de texto", key="enter", window="geral | Slack", app=True), "enviar")
        self.assertEqual(R.ui_risk("press", "Editor", key="ctrl+enter", window="Microsoft Teams", app=True), "enviar")

    def test_enter_in_a_named_editor_field_is_not_a_send(self):
        self.assertIsNone(R.ui_risk("press", "Editor de texto", key="enter", window="nota.txt - Bloco de Notas",
                                    app=True))
        self.assertIsNone(R.ui_risk("press", "pesquisar", key="enter", web=True))

    def test_delete_keys_are_excluir_everywhere(self):
        for keys in (["delete"], ["shift", "delete"], "shift+del"):
            self.assertEqual(R.hotkey_risk(keys, "Downloads"), "excluir", keys)
            self.assertEqual(R.step_risk("hotkey", {"keys": keys}, "Downloads"), "excluir", keys)
        self.assertEqual(R.ui_risk("press", "", key="shift+delete", app=True), "excluir")

    def test_app_pilot_asks_before_enter_in_slack(self):
        from core.app_pilot import AppPilot
        pilot = AppPilot(llm=Mock(), authorize_ui=lambda kind, act, label: f"confirmar {kind}")
        pilot._window = "geral | Slack"
        with self.assertRaises(R.NeedsConfirmation):
            pilot._check("press", "Caixa de texto", key="enter")
        pilot._window = "Downloads"
        with self.assertRaises(R.NeedsConfirmation):
            pilot._check("press", "", key="delete")

    def test_executor_stops_before_shift_delete(self):
        from core.automation import AutomationEngine
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.dry_run, engine.current_agent, engine.authorized_task = False, "DESKTOP", "limpa a pasta Downloads"
        engine.executed_steps, engine.workspace, engine._fg_before, engine._expect = [], {}, None, None
        engine.should_stop = None
        handler = Mock(return_value="⌨️ shift+delete")
        with patch("core.action_policy.authorize", return_value=""), patch.object(R, "mode", return_value="enforce"), \
                patch.object(R, "_record"), patch("core.automation._fg_state", return_value=(1, "Downloads")), \
                patch.object(type(engine), "_hotkey", handler):
            result = engine.execute("hotkey", {"keys": ["shift", "delete"]})
        self.assertEqual(result["status"], "needs_confirmation")
        handler.assert_not_called()


class C4_MoreEffectKinds(unittest.TestCase):
    def test_new_button_labels_need_confirmation(self):
        cases = {"Chamada de áudio": "ligar", "Iniciar chamada de vídeo": "ligar", "Ligar": "ligar",
                 "Videochamada": "ligar", "Sair da conta": "conta", "Sign out": "conta", "Bloquear contato": "bloquear",
                 "Denunciar": "bloquear", "Seguir": "publicar", "Curtir": "publicar", "Compartilhar": "publicar"}
        for label, kind in cases.items():
            self.assertEqual(R.label_risk(label), kind, label)

    def test_harmless_labels_stay_unclassified(self):
        for label in ("Ligar Bluetooth", "Seguir em frente com a instalação", "Abrir", "Próximo", "Salvar"):
            self.assertNotIn(R.label_risk(label), ("ligar", "publicar"), label)

    def test_slang_counts_as_asking_to_send(self):
        for said in ("dispara a mensagem pro grupo", "joga no grupo esse texto", "manda bala"):
            self.assertTrue(R.requested("enviar", said), said)

    def test_turning_something_on_is_not_a_call(self):
        self.assertFalse(R.requested("ligar", "liga o bluetooth"))
        self.assertTrue(R.requested("ligar", "liga pro Luiz no Teams"))

    def test_plan_cannot_add_a_call_nobody_asked_for(self):
        from core.plan_validator import validate_plan
        plan = {"subtasks": [{"agent": "DESKTOP", "task": "abrir o Teams e ligar para o Luiz",
                              "params": {"app": "teams"}}]}
        self.assertFalse(validate_plan("abre o Teams", plan).approved)
        self.assertTrue(validate_plan("liga pro Luiz no Teams", plan).approved)

    def test_teams_call_routine_hits_the_effect_gate(self):
        from agents.desktop_agent import _build_steps
        for kind in ("call", "video_call"):
            steps = _build_steps("teams", {"person": "Luiz", "action_type": kind})
            risks = [R.step_risk(s["action"], s["params"]) for s in steps]
            self.assertIn("ligar", risks, kind)

    def test_writing_in_a_chat_never_presses_enter(self):
        # Medido com o Maestro real: "escreve 'oi' na conversa" era planejado com envio e reprovado pela POL-009
        from agents.desktop_agent import _build_steps
        for app in ("whatsapp", "teams"):
            typed = _build_steps(app, {"person": "Ana", "message": "oi", "action_type": "write_text"})
            self.assertNotIn("hotkey", [s["action"] for s in typed if s["params"].get("keys") == ["enter"]], app)
            sent = _build_steps(app, {"person": "Ana", "message": "oi", "action_type": "send_message"})
            self.assertEqual(R.step_risk(sent[-1 if app == "whatsapp" else -2]["action"],
                                         sent[-1 if app == "whatsapp" else -2]["params"]), "enviar", app)

    def test_maestro_prompt_says_writing_is_not_sending(self):
        from agents.maestro import PROMPT
        self.assertIn("ESCREVER numa conversa ou campo NAO e ENVIAR", PROMPT)

    def test_spoken_confirmation_names_the_call(self):
        self.assertTrue(R.confirmed("sim, pode ligar", "ligar"))
        self.assertIn("chamada", R._ask("ligar", "Chamada de áudio"))


if __name__ == "__main__":
    unittest.main()
