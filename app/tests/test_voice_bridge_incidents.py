"""Replay dos incidentes do modo Conversa (docs/architecture/voice-execution-bridge.md).

Cada caso confere o ESTADO FINAL (quantos envios passaram pela porta, quantas tarefas entraram
na fila, como ficou a pendencia), nao so o texto da resposta. Sem rede, sem modelo, sem tela;
nada e gravado nos registros reais (o log de autorizacao vai para uma pasta temporaria).
"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import core.action_risk as R
from core.followup import resolve
from core.session import Session


class _Log(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "authorization.jsonl"
        real_record = R._record
        self.rec = patch.object(R, "_record", side_effect=lambda row, path=None: real_record(row, self.log))
        self.rec.start()

    def tearDown(self):
        self.rec.stop()
        self.tmp.cleanup()

    def rows(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() else []

    def engine(self, task):
        from core.automation import AutomationEngine
        e = AutomationEngine.__new__(AutomationEngine)
        e.dry_run, e.current_agent, e.authorized_task = False, "WEB", task
        e.effect_scope = "tarefa-1"
        return e

    def pilot(self, engine):
        from core.browser_pilot import BrowserPilot
        return BrowserPilot(llm=lambda s, u: "{}", authorize_ui=engine._authorize_ui)


class I1_MessageSentManyTimes(_Log):
    """"escrever 'Oi' na conversa" virou varias mensagens enviadas a uma pessoa real."""

    def test_enter_in_a_chat_field_with_an_odd_label_is_a_send(self):
        # O campo do chat se chamava "Historico ativado": a regra por rotulo nao via o envio
        self.assertEqual(R.ui_risk("type", "Histórico ativado", submit=True, web=True), "enviar")
        self.assertEqual(R.ui_risk("press", "Histórico ativado", key="Enter", web=True), "enviar")
        self.assertIsNone(R.ui_risk("type", "Pesquisar no Google", submit=True, web=True))
        self.assertIsNone(R.ui_risk("type", "Barra de endereço", submit=True, web=True))
        self.assertIsNone(R.ui_risk("type", "Histórico ativado", submit=False, web=True))   # digitar nao envia

    def test_enforce_stops_before_the_first_send_without_confirmation(self):
        from core.action_risk import NeedsConfirmation
        engine = self.engine("escrever \"Oi\" na conversa no chat")
        pilot = self.pilot(engine)
        with patch.object(R, "mode", return_value="enforce"):
            with self.assertRaises(NeedsConfirmation) as stop:
                pilot._check("type", "Histórico ativado", submit=True)
        self.assertIn(R.CONFIRM_MARK, str(stop.exception))
        self.assertEqual([r["decision"] for r in self.rows()], ["blocked"])

    def test_a_confirmed_send_happens_once_per_task(self):
        from core.action_risk import NeedsConfirmation
        engine = self.engine("escrever \"Oi\" na conversa — confirmo")
        pilot = self.pilot(engine)
        sent = 0
        with patch.object(R, "mode", return_value="enforce"):
            for _ in range(4):           # o piloto via o campo vazio e tentava de novo
                try:
                    pilot._check("type", "Histórico ativado", submit=True)
                    sent += 1
                except NeedsConfirmation as stop:
                    self.assertIn("uma vez nesta tarefa", str(stop))
        self.assertEqual(sent, 1)
        self.assertEqual([r["decision"] for r in self.rows()],
                         ["allowed", "blocked_repeat", "blocked_repeat", "blocked_repeat"])

    def test_repeat_is_blocked_even_in_shadow_mode(self):
        engine = self.engine("escrever oi")
        with patch.object(R, "mode", return_value="shadow"):
            first = engine._authorize_ui("enviar", "type", "Histórico ativado")
            second = engine._authorize_ui("enviar", "click", "Enviar mensagem")
        self.assertEqual(first, "")
        self.assertIn(R.CONFIRM_MARK, second)

    def test_a_new_task_has_its_own_budget(self):
        engine = self.engine("manda oi — confirmo")
        with patch.object(R, "mode", return_value="enforce"):
            self.assertEqual(engine._authorize_ui("enviar", "click", "Enviar"), "")
            engine.effect_scope = "tarefa-2"
            self.assertEqual(engine._authorize_ui("enviar", "click", "Enviar"), "")

    def test_plan_cannot_add_a_send_the_person_did_not_ask_for(self):
        from core.plan_validator import validate_plan
        plan = {"subtasks": [{"agent": "WEB", "task": "escrever 'Oi' na conversa aberta no chat e enviar"}]}
        v = validate_plan("escrever \"Oi\" na conversa no chat", plan)
        self.assertIn("POL-009", [x["policy"] for x in v.violations])
        ok = validate_plan("manda \"Oi\" na conversa no chat", plan)
        self.assertNotIn("POL-009", [x["policy"] for x in ok.violations])
        code = {"subtasks": [{"agent": "CODE", "task": "remover o botao e publicar a versao nova do site"}]}
        self.assertNotIn("POL-009", [x["policy"] for x in validate_plan("tira o botao do site", code).violations])

class I1_SpokenConfirmation(unittest.TestCase):
    def session(self):
        s = Session.__new__(Session)
        Session.__init__(s)
        s.set_pending("Antes de enviar ('Enviar') preciso da sua confirmação. Posso seguir?",
                      "escrever \"Oi\" na conversa no chat", None, kind="confirm")
        return s

    def test_saved_confirmation_cannot_replay_the_old_request(self):
        res = resolve("confirmo", self.session())
        self.assertEqual((res["task"], res["kind"], res["via"]), ("confirmo", "question", "confirm"))
        self.assertFalse(res.get("confirmed"))

    def test_no_ends_without_any_effect(self):
        s = self.session()
        res = resolve("não", s)
        self.assertEqual(res["kind"], "question")
        self.assertIsNone(s.pending)

    def test_another_request_is_not_a_confirmation(self):
        s = self.session()
        res = resolve("abrir a calculadora", s)
        self.assertFalse(res.get("confirmed"))
        self.assertIsNone(s.pending)

    def test_ok_cannot_authorize_an_effect(self):
        self.assertIsNone(R.effect_reply("ok"))
        self.assertEqual(resolve("ok", self.session())["kind"], "question")


class I2_StatusQuestion(unittest.TestCase):
    def test_status_questions_are_recognized_and_commands_are_not(self):
        from core.task_status import is_status_question
        for q in ("verificar o estado do desenvolvimento do site e informar o status", "como está o site?",
                  "já terminou?", "qual é o status", "o que você tá fazendo?"):
            self.assertTrue(is_status_question(q), q)
        for c in ("abrir a página de status do servidor", "criar um site sobre status de pedidos",
                  "abrir o VS Code", "escrever oi"):
            self.assertFalse(is_status_question(c), c)

    def test_the_answer_comes_from_the_ledger(self):
        from core.task_ledger import TaskLedger
        from core.task_status import describe
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp))
            ledger.begin("t1", "criar um site sobre um campeonato")
            ledger.step_started("t1", 1, "CODE", "create_project", {}, "Criar")
            ledger.step_finished("t1", 1, "create_project", {"success": True, "result": "Arquivos criados"})
            ledger.finish("t1", "completed", verified=True)
            self.assertIn("Terminei: criar um site sobre um campeonato", describe(ledger))
            ledger.begin("t2", "abrir o projeto no VS Code")
            self.assertIn("Estou fazendo agora: abrir o projeto no VS Code", describe(ledger))
            self.assertNotIn("VS Code", describe(ledger, exclude="t2"))
            self.assertIn("Na fila: 1", describe(ledger, queued=["abrir o site"]))


class I3_VSCodeProject(unittest.TestCase):
    def test_project_opens_in_the_editor_in_one_step(self):
        from core.existing_targets import existing_plan, existing_steps
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "site_teste"
            proj.mkdir()
            session = Mock(code={"folder": str(proj)})
            plan = existing_plan("abrir o projeto no VS Code", session)
            steps = existing_steps(plan["subtasks"][0]["params"]["existing"])
            self.assertEqual([(s["action"], s["params"]["path"]) for s in steps], [("open_in_editor", str(proj))])
            # caminho citado no pedido vence o projeto da conversa
            other = Path(tmp) / "outro projeto"
            other.mkdir()
            cited = existing_plan(f"no VS Code já aberto, abrir a pasta do projeto em {other}", Mock(code=None))
            self.assertEqual(cited["subtasks"][0]["params"]["existing"]["path"], str(other))


class I4_PendingQuestionCapture(unittest.TestCase):
    def session(self, age=0):
        s = Session.__new__(Session)
        Session.__init__(s)
        s.set_pending("O projeto desta conversa não tem página HTML para abrir no navegador.",
                      "abrir o site do projeto no navegador")
        s.pending["at"] -= age
        return s

    def test_navigation_commands_are_new_requests(self):
        for said in ("Abre o VS", "trazer o VS Code já aberto para frente", "fecha o navegador"):
            s = self.session()
            res = resolve(said, s, llm=lambda a, b: '{"kind": "new"}')
            self.assertNotIn("resposta à pergunta", res["task"], said)
            self.assertIsNone(s.pending, said)

    def test_a_real_answer_still_continues_the_request(self):
        res = resolve("o da pasta trabalhos", self.session())
        self.assertIn("resposta à pergunta", res["task"])

    def test_old_question_expires(self):
        s = self.session(age=600)
        res = resolve("o da pasta trabalhos", s, llm=lambda a, b: '{"kind": "new"}')
        self.assertNotIn("resposta à pergunta", res["task"])


class P0_DuplicateDelegation(unittest.TestCase):
    """A confirmacao falada virou uma SEGUNDA tarefa igual; o modelo de voz tambem re-delega."""

    def voice(self):
        from desktop.voice import VoiceController
        v = VoiceController.__new__(VoiceController)
        v.conv, v.ctrl = None, Mock(state={}, session=Mock(pending=None))
        v._cmd_q, v._inflight, v._recent_done, v._repeat_offer = __import__("collections").deque(), False, [], ""
        v._qlock = __import__("threading").RLock()
        v._dispatch = Mock()
        v._say = Mock()
        return v

    def test_same_request_while_running_is_not_queued(self):
        v = self.voice()
        v._inflight, v._reply_task = True, ("escrever 'Oi' na conversa com a contato no chat", "")
        with patch("desktop.voice.bus"):
            v._enqueue(v._reply_task[0], "isso, pode escrever")
        self.assertEqual(len(v._cmd_q), 0)

    def test_same_request_just_done_asks_before_repeating(self):
        v = self.voice()
        v._recent_done = [("escrever 'Oi' na conversa com a contato no chat", time.monotonic(), True)]
        with patch("desktop.voice.bus"):
            v._enqueue(v._recent_done[0][0], "pode escrever")
        self.assertEqual(len(v._cmd_q), 0)
        self.assertTrue(v._repeat_offer)
        with patch("desktop.voice.bus"):
            v._enqueue(v._repeat_offer, "sim", force=True)
        self.assertEqual(len(v._cmd_q), 1)

    def test_different_or_navigation_requests_still_queue(self):
        v = self.voice()
        v._inflight, v._reply_task = True, ("abrir o Google", "")
        v._recent_done = [("abrir o YouTube", time.monotonic(), True)]
        with patch("desktop.voice.bus"):
            v._enqueue("abrir o Google e pesquisar receitas", "")
            v._enqueue("abrir o YouTube", "")
        self.assertEqual(len(v._cmd_q), 2)

    def test_different_recipient_amount_and_destination_each_queue(self):
        v = self.voice()
        original = "transferir R$ 12 para Ana na conta 7"
        v._inflight, v._reply_task = True, (original, "")
        distinct = [original.replace("Ana", "Bia"), original.replace("12", "15"),
                    original.replace("conta 7", "conta 8")]
        with patch("desktop.voice.bus"):
            v._enqueue(original, original)
            for command in distinct:
                v._enqueue(command, command)
        self.assertEqual([c for c, _, _ in v._cmd_q], distinct)

    def test_status_question_answers_without_queueing(self):
        v = self.voice()
        with patch("desktop.voice.bus"), patch("core.task_status.describe", return_value="Nada rodando."):
            self.assertTrue(v._status_reply("já terminou?"))
        self.assertEqual(len(v._cmd_q), 0)
        v._say.assert_called_once()

    def test_yes_to_a_pending_confirmation_reaches_the_controller(self):
        v = self.voice()
        v.ctrl.reply_to_effect.side_effect = lambda text: R.spoken_effect_code(text) == "1001"
        self.assertTrue(v._confirm_reply("confirmo 1001"))
        self.assertFalse(v._confirm_reply("sim, mas não envie"))
        self.assertEqual(list(v._cmd_q), [])


class ControllerReplay(unittest.TestCase):
    """O _run de verdade do controller, com agentes falsos e o resolvedor de verdade."""

    def setUp(self):
        from core.session import Session
        from core.task_ledger import TaskLedger
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = TaskLedger(Path(self.tmp.name))
        self.session = Session()
        self.session.save = lambda *a, **k: None
        self.events = []

    def run_said(self, said, results):
        import threading
        from desktop.controller import Controller
        c = Controller.__new__(Controller)
        c.state, c._lock, c._run_id, c._tls = {"running": True}, threading.Lock(), 1, threading.local()
        c._cancel_event, c._plan_gate = threading.Event(), threading.Event()
        c._plan_ok, c._plan_token, c._voice_hints = False, "", {}
        c._ai_client, c._config = Mock(metrics={}), Mock(get=lambda key, default=None: default)
        c._brain = Mock(last_skills={}, write_plan=Mock(return_value=None), context_for=Mock(return_value=""))
        c.capture, c.memory, c.narrator = Mock(), Mock(), Mock()
        c.session = self.session
        c._ContextManager = lambda: Mock(prepare_subtask=lambda s, i: s, extract_from_results=Mock(return_value={}),
                                         after_subtask=Mock(), has_folder=False)
        agent = Mock(spec=["plan"])
        agent.plan.return_value = {"steps": [{"action": "wait", "params": {}, "description": "passo"}]}
        c.agents = {"WEB": agent}
        c.maestro = Mock(analyze=Mock(return_value={"analysis": "a", "skills": [], "subtasks": [
            {"agent": "WEB", "task": "escrever no chat", "params": {}, "original_task": said}]}))
        seq = iter(results)
        c.engine = Mock(execute=Mock(side_effect=lambda a, p, dry_run=False: {"action": a, **next(seq)}),
                        workspace={}, last_say="")
        c._after_turn, c._metrics_delta, c._emit_usage = Mock(), (lambda b, a: {}), (lambda: None)
        c._emit = lambda name, payload=None: self.events.append((name, payload or {}))
        with patch("core.task_ledger.get_ledger", return_value=self.ledger), \
                patch("desktop.controller.history_store.append"), \
                patch("core.plan_validator.validate_steps", return_value=Mock(approved=True)), \
                patch("core.followup.from_hint", return_value=None), \
                patch("core.followup._default_llm", return_value='{"kind": "new"}'), \
                patch("agents.maestro.vault_plan", return_value=None), \
                patch("agents.maestro.continue_plan", return_value=None), \
                patch("core.existing_targets.existing_plan", return_value=None), \
                patch("core.user_settings.load", return_value={"plan_review": False}), patch("time.sleep"), \
                patch("core.action_logger.log_action"):
            c._run(said, False, False, 1)
        return c

    def test_status_question_runs_nothing(self):
        c = self.run_said("verificar o estado do desenvolvimento do site e informar o status", [])
        c.maestro.analyze.assert_not_called()
        c.engine.execute.assert_not_called()
        self.assertTrue(any(name == "answer" for name, _ in self.events))

    def test_refused_effect_ends_the_current_run_without_replanning(self):
        blocked = {"success": False, "status": "needs_confirmation", "result": "Ação não autorizada."}
        c = self.run_said("enviar mensagem no chat", [blocked])
        self.assertEqual(c.engine.execute.call_count, 1)
        self.assertIsNone(self.session.pending)
        c = self.run_said("confirmo", [])
        c.engine.execute.assert_not_called()
        c.maestro.analyze.assert_not_called()

    def test_approval_remains_inside_the_same_executor_call(self):
        import threading
        from desktop.controller import Controller
        from core.automation import AutomationEngine
        c = Controller.__new__(Controller)
        c.state, c._lock, c._tls, c._run_id = {"running": True}, threading.Lock(), threading.local(), 1
        c._cancel_event, c._plan_gate = threading.Event(), threading.Event()
        c._plan_token, c._effect_deadline, c._plan_ok = "", 0, False
        c._effect_sequence, c._effect_code = 1000, ""
        engine = AutomationEngine.__new__(AutomationEngine)
        engine.current_agent, engine.authorized_task, engine.effect_scope = "WEB", "enviar dois itens", "qa"
        engine.confirm_effect = lambda question: c._wait_effect(question, False, timeout=0.1)
        tokens, codes, delivered = [], [], []

        def answer(event, payload):
            if not payload.get("effect"):
                return
            token = payload["token"]
            if tokens:
                self.assertFalse(c.approve_plan(True, tokens[-1]))
                self.assertFalse(c.reply_to_effect("confirmo " + codes[-1]))
            tokens.append(token)
            codes.append(payload["spoken_code"])
            self.assertFalse(c.reply_to_effect("confirmo"))
            if len(tokens) == 3:
                self.assertTrue(c.reply_to_effect("não"))
            elif len(tokens) < 3:
                self.assertTrue(c.reply_to_effect("confirmo " + " ".join(codes[-1])))
            if len(tokens) < 4:
                self.assertFalse(c.approve_plan(True, token))

        c._emit = answer
        with patch.object(R, "mode", return_value="enforce"), patch.object(R, "_record"):
            for label in ("item A", "item B", "recusado", "expirado"):
                if not engine._authorize_ui("enviar", "click", label):
                    delivered.append(label)
        self.assertEqual(delivered, ["item A", "item B"])
        self.assertEqual(len(tokens), 4)
        self.assertFalse(c.approve_plan(True, tokens[-1]))
        self.assertFalse(c.reply_to_effect("confirmo"))


if __name__ == "__main__":
    unittest.main()
