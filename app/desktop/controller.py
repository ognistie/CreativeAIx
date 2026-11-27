"""
Controller — orquestra agentes e emite eventos para o EventBus.

E o equivalente desktop do antigo `ui/server.py:_run()`. Mesma logica de
execucao, mesmos contratos, MESMOS modulos do core/agents (zero
modificacao). A unica diferenca: em vez de `socketio.emit('phase', ...)`,
chamamos `bus.emit('phase', ...)`.

Mantem 1-pra-1 os eventos esperados pelo antigo frontend, mais 2 novos:
    log              — feed estruturado (level/agent/msg/ts)
    history_changed  — uma execucao foi gravada no historico
"""

from __future__ import annotations

import os
import secrets
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from desktop.event_bus import bus
from desktop import history_store
from desktop.controller_gates import GateMixin
from desktop.controller_reply import ReplyMixin
from desktop.controller_telemetry import TelemetryMixin


# Imports dos agentes/core acontecem dentro do __init__ para evitar
# carregar dependencias pesadas (anthropic, playwright) ao importar este
# modulo em testes.

NO_SCREENSHOT = {
    "wait", "hotkey", "type_text", "app_type", "app_search", "focus_window",
    "vision_click", "vision_type", "uia_click", "uia_type", "run_python",
    "run_command", "write_file", "create_folder", "read_file", "list_files",
    "move_file", "copy_file", "delete_file", "find_files", "pip_install",
    "excel_write", "wait_for_window", "wait_for_element", "browser_read", "open_path", "browser_task", "app_task", "edit_project",
    "revert_project", "blank_document",
}
# So cliques repetem sozinhos. Digitar de novo depois de uma falha que ja digitou parte do texto duplicaria o
# texto (a conferencia pode falhar com o texto ja no campo); vision_type ja tenta achar o campo duas vezes.
RETRY_ACTIONS = {"vision_click", "uia_click", "browser_click"}


def should_retry(action: str, result: dict, dry_run: bool = False) -> bool:
    """Repete um clique uma vez so quando o alvo nem foi achado ("❌"). Um clique que aconteceu e so nao mudou a
    pagina ("⚠️ ... sem efeito") nao repete: Curtir/Seguir alternariam duas vezes."""
    return (not result.get("success", True) and action in RETRY_ACTIONS and not dry_run
            and str(result.get("result", "")).lstrip().startswith("❌"))


MAX_TASK_LENGTH = 2000


# Parametros do plano que carregam CONTEUDO do usuario (o que "a mesma mensagem" retoma)
_CONTENT_KEYS = ("message", "text", "query", "content", "subject", "person", "to", "url", "filename", "name")


def turn_content(subtasks: list, request: str = "") -> str:
    """Conteudo literal de um pedido, a partir do plano: o que cada agente recebeu para fazer
    + os campos de conteudo (mensagem, texto, busca, destinatario...). So entra o que NAO esta
    no pedido entendido (o contexto ja mostra o pedido; repetir so gasta tokens)."""
    seen = (request or "").lower()
    parts = []
    for s in subtasks or []:
        task = str(s.get("task") or "").strip()
        if task and task.lower() not in seen:
            parts.append(f"{(s.get('agent') or '').upper()}: {task}")
            seen += " " + task.lower()
        params = s.get("params") or {}
        for k in _CONTENT_KEYS:
            v = params.get(k)
            if isinstance(v, str) and v.strip() and v.strip().lower() not in seen:
                parts.append(f'{k}="{v.strip()}"')
                seen += " " + v.strip().lower()
    return " | ".join(parts)


class Controller(ReplyMixin, GateMixin, TelemetryMixin):
    """Coracao do desktop. Executa tarefas em background e publica eventos."""

    # Troca de conversa (nova/abrir) x resposta escrita em segundo plano: a resposta de um pedido so e
    # gravada na conversa dele. Na classe porque os testes montam o Controller com __new__.
    _session_lock = threading.RLock()

    def __init__(self) -> None:
        from agents.maestro import Maestro
        from agents.data_agent import DataAgent
        from agents.web_agent import WebAgent
        from agents.code_agent import CodeAgent
        from agents.desktop_agent import DesktopAgent
        from agents.file_agent import FileAgent
        from core.automation import AutomationEngine
        from core.capture import ScreenCapture
        from core.narrator import ReportNarrator
        from core.context_manager import ContextManager
        from core.ai_client import get_client
        from agents.memory_agent import MemoryAgent

        self._ContextManager = ContextManager
        self._ai_client = get_client()
        from core.config import get_config
        self._config = get_config()
        self._ai_client.on_progress = self._on_llm_progress
        self.memory = MemoryAgent()
        from core.brain import get_brain
        self._brain = get_brain()
        self.maestro = Maestro(memory=self.memory)
        from agents.extcode_agent import ExtCodeAgent
        self.agents = {
            "DATA": DataAgent(),
            "WEB": WebAgent(),
            "CODE": CodeAgent(),
            "DESKTOP": DesktopAgent(),
            "FILE": FileAgent(),
            "EXTCODE": ExtCodeAgent(),
        }
        self.engine = AutomationEngine()
        self.capture = ScreenCapture()
        self.narrator = ReportNarrator()

        # Cleanup automatico de arquivos antigos no startup
        try:
            from scripts.cleanup_old_files import run_cleanup
            stats = run_cleanup(verbose=False)
            if stats["removed"]:
                print(f"  [cleanup] {stats['removed']} arquivos antigos removidos "
                      f"({stats['bytes_freed'] / 1024 / 1024:.1f} MB liberados)")
        except Exception as e:
            print(f"  [cleanup] falhou (nao critico): {e}")

        # Memoria: tira do caminho workflows de formatos antigos (v5-)
        try:
            moved = self.memory.purge_legacy()["moved"]
            if moved:
                print(f"  [memoria] {moved} workflow(s) de formato antigo movidos para .legacy/")
        except Exception as e:
            print(f"  [memoria] limpeza falhou (nao critico): {e}")

        # Conversa: o que foi feito e o que ficou aberto, entre pedidos
        from core.session import Session
        self.session = Session()
        self.session.restore_active()
        # Pedido falado ja entendido COM a conversa (continua em qual alvo?): evita
        # a 2a chamada do resolvedor. Chave = texto do pedido; validado em followup.from_hint.
        self._voice_hints: Dict[str, dict] = {}

        # Tarefa que ficou sem fim na ultima vez (o app caiu ou foi fechado no meio). Nada e repetido.
        try:
            from core.task_ledger import get_ledger
            self.interrupted_tasks = get_ledger().recover()
            for lost in self.interrupted_tasks:
                print(f"  [tarefas] interrompida: {lost['id']} ({len(lost['steps_uncertain'])} passo(s) sem resultado conhecido)")
        except Exception as e:
            self.interrupted_tasks = []
            print(f"  [tarefas] recuperacao falhou (nao critico): {type(e).__name__}")

        self.state = {"running": False}
        self._cancel_event = threading.Event()
        # Revisao do plano (opcao em Configuracoes): o pedido espera o "Executar" do usuario
        self._plan_gate = threading.Event()
        self._plan_ok = False
        self._plan_token = ""
        self._plan_skip: set = set()     # passos (1..n) que a pessoa pulou na revisao do plano
        self._effect_deadline = 0.0
        self._effect_sequence = 1000
        self._effect_code = ""
        self._lock = threading.Lock()
        # Cada execucao recebe um id. Uma thread cancelada que ainda esteja
        # presa (ex.: aguardando a API) nao pode emitir eventos na tela da
        # tarefa seguinte nem desligar o estado "running" dela.
        self._run_id = 0
        self._tls = threading.local()

    # ──────────────────────────────────────────────────────────────────
    #  API publica (consumida pelo Bridge)
    # ──────────────────────────────────────────────────────────────────

    def execute_task(self, task: str, dry_run: bool = False,
                     generate_report: bool = True, *, source: str = "text", heard: str = "",
                     session_id: Optional[str] = None) -> bool:
        """Dispara execucao em thread separada."""
        task = (task or "").strip()
        if not task:
            bus.emit("error", {"msg": "Tarefa vazia."})
            return False
        if len(task) > MAX_TASK_LENGTH:
            bus.emit("error",
                     {"msg": f"Tarefa muito longa (max {MAX_TASK_LENGTH} chars)."})
            return False
        with self._lock:
            if session_id is not None and self.session.id != session_id:
                return False
            if self.state["running"]:
                if source != "voice":
                    stopping = self._cancel_event.is_set()
                    bus.emit("error", {"msg": "Ainda estou parando a tarefa anterior. Tente de novo em alguns segundos."
                                       if stopping else "Ja existe uma execucao em andamento."})
                return False
            self.state["running"] = True
            self.state["task"] = task[:200]          # a tela Atividade mostra o que esta rodando
            self._cancel_event.clear()
            self._run_id += 1
            run_id = self._run_id

        if source == "voice":
            # A interface observa; a execução não depende de uma chamada de volta do React.
            bus.emit("voice_command", {"text": task, "heard": heard, "executing": True,
                                       "run_id": run_id, "session_id": self.session.id})

        def run():
            self._tls.voice = source == "voice"
            self._run(task, dry_run, generate_report, run_id)

        threading.Thread(target=run, daemon=True).start()
        return True

    def voice_hint(self, text: str, hint: dict) -> None:
        """A voz avisa como o pedido foi entendido (kind/target) antes de envia-lo a tela."""
        self._voice_hints = {**dict(list(self._voice_hints.items())[-4:]), (text or "").strip(): hint}

    def new_session(self) -> None:
        """Nova conversa: esquece pedidos anteriores e o que estava aberto."""
        with self._lock:
            if self.state["running"]:
                return
            with self._session_lock:
                self.session.reset()
                self.session.remember_active("")
            bus.emit("session_reset", {"session": self.session.id})

    # ── conversas salvas ─────────────────────────────────────────────
    def list_conversations(self) -> list:
        from core.session import Session
        return Session.list_saved()

    def open_conversation(self, sid: str) -> Optional[dict]:
        """Retoma uma conversa salva: o historico volta para a tela e o contexto
        (pedidos, respostas, o que ainda estiver aberto) volta para o agente."""
        from core.session import Session
        data = Session.read_saved(sid)
        if not data:
            return None
        with self._lock:
            if self.state["running"]:
                return None
            with self._session_lock:
                self.session.load(data)
                self.session.remember_active(sid)
            bus.emit("session_reset", {"session": self.session.id, "loaded": True})
        return data


    def attach_files(self, paths: list) -> list:
        """Anexos do usuario (+ ou arrastar): entram na conversa como arquivos que o assistente
        pode ler ("resume esta planilha") e o pedido cita o caminho para os agentes."""
        ok = [p for p in (paths or []) if isinstance(p, str) and os.path.isfile(p)]
        if ok:
            self.session.remember_files(ok)
        return ok


    def force_stop(self) -> None:
        """Cancela execucao em andamento."""
        with self._lock:
            self._plan_ok = False
            self._plan_token = ""
            self._cancel_event.set()
            self._plan_gate.set()       # um plano esperando aprovacao tambem para
        bus.emit("cancelled", {"msg": "Cancelamento solicitado; aguardando encerramento."})

    # ──────────────────────────────────────────────────────────────────
    #  Loop interno (porta de ui/server.py:_run)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _ledger_call(method, *args, **kwargs) -> None:
        """O registro de tarefas nunca pode derrubar a execucao que ele observa."""
        try:
            method(*args, **kwargs)
        except Exception as error:
            print(f"  [Registro de tarefas] falhou: {type(error).__name__}")

    def _is_current(self) -> bool:
        """True na thread da execucao ativa (ou fora de qualquer execucao)."""
        rid = getattr(self._tls, "run_id", None)
        return rid is None or rid == self._run_id

    def _alive(self) -> bool:
        """A execucao desta thread deve continuar?"""
        cancelled = getattr(self, "_cancel_event", None)
        return self.state["running"] and self._is_current() and not (cancelled and cancelled.is_set())

    def _emit(self, event: str, payload: Any = None) -> None:
        if self._is_current():
            self._touch()                  # qualquer evento da tarefa conta como avanco para o vigia
            bus.emit(event, payload)


    def _run(self, task: str, dry_run: bool, gen_report: bool,
             run_id: int = 0) -> None:
        self._tls.run_id = run_id or self._run_id
        from core.ai_client import bind_cancel
        from core.lab_budget import Budget, budget_scope
        from core.run_context import RunContext
        bind_cancel(lambda: not self._alive())
        self._touch()
        self._start_watchdog(self._tls.run_id)
        try:
            config = getattr(self, "_config", {})
            usd = float(config.get("execution.model_budget_usd", 0))
            timeout = float(config.get("execution.run_limit_s", 0))
            cancelled = lambda: not self._alive()
            budget = Budget(usd, timeout if timeout > 0 else 0,
                            int(config.get("execution.model_call_limit", 30)),
                            int(config.get("execution.model_token_limit", 300000)), cancelled) if usd > 0 else None
            deadline = budget.deadline if budget else time.monotonic() + timeout if timeout > 0 else None
            run = RunContext(task, cancelled, deadline, budget, dry_run=dry_run)
            from core.egress import offline
            if budget is not None and deadline is not None and config.get("execution.model_replan", False) is True and not offline():
                from core.objective_replanner import choose_read_strategy
                run.read_replanner = lambda observation, choices: choose_read_strategy(
                    self._ai_client, config.get_model("maestro"), observation, choices)
            bind_cancel(run.interrupted)
            with budget_scope(run.budget):
                self._run_inner(task, dry_run, gen_report, run_id, run=run)
        except Exception as error:
            # Falha antes do try interno (registro, metricas): a tarefa termina com erro em vez de deixar o app
            # "ocupado" para sempre
            self._emit("error", {"msg": f"Falha ao iniciar a tarefa: {type(error).__name__}: {error}"})
            self._emit("execution_finished", {"success": False, "status": "failed"})
        finally:
            bind_cancel(None)
            # O escopo de arquivos da conversa vale so para este pedido (a thread pode ser reaproveitada)
            from core.file_contracts import CONVERSATION_ROOTS
            CONVERSATION_ROOTS.set(())
            with self._lock:
                if self._is_current():
                    self.state["running"] = False

    # Tarefa sem nenhum avanco (passo, andamento do piloto, texto do modelo) por esse tempo e interrompida.
    # Esperas pela pessoa (revisao do plano, confirmacao de efeito) nao contam.
    IDLE_LIMIT_S = 300

    def _touch(self) -> None:
        self._last_activity = time.monotonic()

    def _start_watchdog(self, run_id: int) -> None:
        limit = float(self._config.get("execution.idle_limit_s", self.IDLE_LIMIT_S) or self.IDLE_LIMIT_S) \
            if getattr(self, "_config", None) else self.IDLE_LIMIT_S

        def watch():
            while True:
                time.sleep(2)
                with self._lock:
                    if not self.state.get("running") or self._run_id != run_id or self._cancel_event.is_set():
                        return
                    waiting_person = bool(getattr(self, "_plan_token", ""))
                if waiting_person:
                    self._touch()
                    continue
                idle = time.monotonic() - getattr(self, "_last_activity", time.monotonic())
                if idle > limit:
                    with self._lock:
                        if self._run_id != run_id or not self.state.get("running"):
                            return
                        self._watchdog_fired = run_id
                        self._cancel_event.set()
                        self._plan_gate.set()
                    bus.emit("cancelled", {"msg": f"Parei: a tarefa ficou {idle:.0f} s sem avançar."})
                    return
        threading.Thread(target=watch, daemon=True, name="task-watchdog").start()

    def _run_inner(self, task: str, dry_run: bool, gen_report: bool,
                   run_id: int = 0, *, run) -> None:
        from core.step_runtime import verified_success
        all_success = True
        task_start = time.time()
        metrics_before = self._ai_client.metrics
        entry = history_store.new_execution(task, dry_run=dry_run)
        # A tela casa eventos atrasados (resposta em segundo plano, historico) pela execucao, nao pelo texto:
        # repetir o mesmo pedido fazia a resposta da execucao anterior cair na nova.
        entry["run_id"] = self._tls.run_id
        # Registro duravel: esta tarefa sobrevive a uma queda do app (core/task_ledger.py).
        # So observa: falhar aqui nao muda o resultado da execucao.
        from core.task_ledger import get_ledger
        run.ledger, run.task_id = get_ledger(), entry["id"]
        ledger, task_id = run.ledger, run.task_id
        voice_source = getattr(self._tls, "voice", False) is True
        self._ledger_call(ledger.begin, task_id, task, source="voz" if voice_source or task.strip() in self._voice_hints else "texto",
                          dry_run=dry_run, session_id=self.session.id)
        brain_plan = None
        all_records = run.evidence
        said = task
        turn = {"kind": "new", "agents": [], "summary": "", "recorded": False, "content": ""}
        turn["voice"] = voice_source
        entry["session_id"] = self.session.id
        # Onde o tempo foi (ms por fase): base para medir latencia (scripts/latency_report.py)
        timing = {"resolve": 0, "maestro": 0, "agent_plan": 0, "steps": 0}
        entry["timing"] = timing
        t_mark = time.time()

        def lap(phase: str) -> None:
            nonlocal t_mark
            now = time.time()
            timing[phase] += int((now - t_mark) * 1000)
            t_mark = now

        try:
            self._emit("phase", {"phase": "maestro", "msg": "Entendendo o pedido...", "run_id": self._tls.run_id})
            self._log("INFO", "MAESTRO", f"Recebida tarefa: {task[:80]}")

            # Conversa: "agora abra esse segundo video" vira um pedido
            # completo, apontando para o que ficou aberto antes.
            from core.followup import from_hint, resolve
            # So a origem real conta: um texto digitado igual a uma dica de voz recente pulava a revisao do plano
            from_voice = voice_source
            res = from_hint(said, self.session, self._voice_hints.pop(said.strip(), None)) \
                or resolve(said, self.session)
            self._emit_usage()
            lap("resolve")
            kind, target = res["kind"], res.get("target")
            turn["kind"] = kind
            if res.get("via") == "pending":
                self.session.clear_pending()
            if res["task"] != said or kind != "new":
                self._emit("resolved", {"said": said, "task": res["task"], "kind": kind,
                                        "target": target or ""})
                self._log("INFO", "MAESTRO", f"Entendido ({kind}): {res['task'][:120]}")
            task = res["task"]
            entry["resolved"] = task
            # Escopo de arquivos da conversa: "abra o relatorio" (sem caminho) pode usar a pasta que a pessoa
            # citou antes ou o arquivo que o app criou nesta conversa. Vale so nesta thread, ate o fim do _run.
            from core.file_contracts import CONVERSATION_ROOTS, conversation_roots
            run.file_roots = tuple(conversation_roots(self.session))
            CONVERSATION_ROOTS.set(run.file_roots)

            # Pergunta que o resolvedor respondeu so com o resumo da conversa: com a conversa ligada, quem
            # responde e ela (historico inteiro + leitura de arquivos). Papo e confirmacao seguem sem modelo.
            chat_on = self._chat_enabled(dry_run, from_voice)
            if self._answer_without_running(res, said, task, target, entry, turn, ledger, task_id, dry_run,
                                            from_voice, chat_on):
                entry.setdefault("route", "resposta")          # panorama do harness (core/panorama.py)
                return

            self._emit("phase", {"phase": "maestro", "msg": "Analisando intencao..."})
            # Memoria: o Maestro consulta rotas parecidas e as usa como
            # referencia no prompt (nunca como atalho).
            conversation = "" if self.session.empty else self.session.context_block()
            # Continuar no que esta aberto ("clica em X", "pausa o video", "volta"): o alvo ja
            # diz qual agente age; vai direto, sem a chamada do Maestro (~2,5 s por pedido)
            from agents.maestro import continue_plan, vault_plan
            from agents.extcode_agent import extcode_plan
            from core.existing_targets import existing_plan
            # Abrir o que ja existe (pasta ou site do projeto, subpasta, janela) nao passa pelo modelo:
            # cair num agente que so cria era o que fazia o agente de codigo criar um projeto novo.
            # "com o Claude" / "pelo Codex": o agente externo, na pasta citada ou no projeto da conversa
            # Acao no computador pedida "com o Claude Code / Codex" (ou pelo seletor do topo): os agentes de
            # codigo trabalham numa pasta de projeto; abrir programa ou site segue pelos agentes do computador
            ext_plan = extcode_plan(task, self.session)
            route_task = task
            if ext_plan and ext_plan.get("reroute"):
                self._log("INFO", "EXTCODE", ext_plan["note"])
                route_task, ext_plan = ext_plan["reroute"], None
                self._emit("resolved", {"said": said, "task": route_task, "kind": kind, "target": target or ""})
            # Planos aprendidos: pedido novo, sem depender da conversa, cujo molde ja deu certo varias vezes com o
            # mesmo plano -> executa o plano sem chamar o Maestro (core/learned_plans.py). Validado como um do modelo.
            from core.learned_plans import get_learned
            learnable = kind == "new" and res.get("via") != "pending" and not dry_run
            plan = vault_plan(route_task) or existing_plan(route_task, self.session) \
                or ext_plan \
                or continue_plan(route_task, kind, target, self.session) \
                or (get_learned().plan_for(route_task) if learnable else None)
            # Sem atalho nem plano aprendido: a conversa responde (pergunta, analise, leitura de pastas) ou devolve
            # um pedido de acao para o Maestro. "continue" age no que esta aberto e segue direto para os agentes.
            if not plan and chat_on and kind in ("new", "question"):
                # "abre o bloco de notas", "abre a pasta X", "pesquisa X no Google": sem modelo nenhum
                from agents.maestro import profile_plan, shortcut_open_plan
                plan = shortcut_open_plan(route_task, target or "")
                # Rota aplicada no Lab: o perfil decide o agente antes da conversa (que reescreveria o pedido)
                if not plan and kind == "new" and not target:
                    plan = profile_plan(route_task)
            handed_by_chat = False
            if not plan and chat_on and kind in ("new", "question"):
                lap("resolve")
                # So pedido novo pode virar acao; pergunta/comentario a conversa apenas responde
                chat = self._run_chat(said, task, entry, spoken=from_voice, allow_actions=kind == "new")
                lap("maestro")
                if chat is not None and chat.kind == "cancelled":
                    self._emit("cancelled", {"msg": "Cancelado."})
                    turn["recorded"] = not chat.text
                    turn["kind"], turn["summary"] = "question", chat.text
                    return
                if chat is not None and chat.kind == "failed":
                    self._emit("error", {"msg": chat.text})
                    entry["error"] = chat.text[:300]
                    turn["kind"] = "question"
                    return
                if chat is None and kind == "question":
                    # Conversa indisponivel numa pergunta/comentario: fica a resposta do resolvedor. Nunca cai no
                    # Maestro, que poderia transformar "legal, ficou bom" em tarefa (regra da main).
                    answer = res.get("answer") or "Não consegui responder agora. Pode tentar de novo?"
                    self._emit("answer", {"msg": answer, "run_id": self._tls.run_id})
                    turn["kind"], turn["summary"] = "question", answer
                    entry["success"] = bool(res.get("answer"))
                    return
                if chat is not None and chat.kind == "answer":
                    entry["route"] = "conversa"
                    self._emit("answer", {"msg": chat.text, "run_id": self._tls.run_id})
                    turn["kind"] = "question"
                    turn["summary"] = chat.text
                    entry["success"] = bool(chat.text)
                    if not chat.text:
                        entry["error"] = "conversa sem resposta"
                    return
                if chat is not None and chat.kind == "act":
                    route_task = chat.task
                    # O molde aprendido e da FALA da pessoa; o pedido reescrito pela conversa nao vira molde
                    learnable = False
                    handed_by_chat = True
                    self._log("INFO", "CHAT", f"Pedido de ação: {route_task[:160]}")
                    self._emit("resolved", {"said": said, "task": route_task, "kind": kind, "target": target or ""})
                    entry["resolved"] = route_task
                    # Abrir arquivo/pasta pelo caminho exato: plano pronto, conferido pelo escopo de leitura
                    plan = chat.plan or vault_plan(route_task) or existing_plan(route_task, self.session)
                    from core.coding_agents import tool_in
                    if not plan and tool_in(said):
                        handed = extcode_plan(route_task, self.session)
                        plan = handed if handed and not handed.get("reroute") else None
            plan = plan or self.maestro.analyze(route_task, conversation=conversation, continue_in=target or "")
            if plan.get("learned_key"):
                self._log("INFO", "MAESTRO", plan.get("analysis", "Plano aprendido"))
            # Por onde o pedido passou: o panorama do harness mostra ao vivo e soma o trafego no historico
            from core.panorama import route_of
            entry["route"] = route_of(plan, handed_by_chat)
            # Copia do plano como saiu do planejador (a execucao acrescenta alvos de continuacao aos params)
            import copy as _copy
            learn_source = _copy.deepcopy(plan) if learnable else None
            self._emit_usage()
            lap("maestro")
            maestro_skills = self._brain.last_skills.pop("MAESTRO", [])
            if maestro_skills:
                self._log("INFO", "MAESTRO", "Skills aplicadas: " + ", ".join(maestro_skills))
                entry.setdefault("agent_skills", {})["MAESTRO"] = maestro_skills

            if plan.get("needs_clarification"):
                question = plan.get("question", "Tarefa ambigua — pode dar mais detalhes?")
                # A resposta do usuario continua ESTE pedido (sem redigitar tudo)
                self.session.set_pending(question, task, target)
                self._emit("error", {"msg": question, "kind": "clarification"})
                entry["error"] = "clarification_required"
                turn["recorded"] = True     # a resposta continua o pedido (pending)
                return

            if plan.get("limitation"):
                # Pedido que o sistema nao cumpre como foi feito (ex.: letra
                # de musica protegida). Aviso honesto em vez de substituto.
                self._emit("error", {"msg": plan.get("message", ""), "kind": "limitation"})
                entry["error"] = "limitation: " + plan.get("message", "")
                return

            if plan.get("error"):
                if plan.get("rejected_plan") and not dry_run:
                    brain_plan = self._brain.write_plan(task, plan["rejected_plan"])
                self._emit("error", {"msg": plan.get("message", "Erro do Maestro.")})
                entry["error"] = plan.get("message", "maestro_error")
                return

            # Revisar o plano antes de agir (Configuracoes): so pedidos digitados — na voz a
            # confirmacao falada ja cumpre esse papel. Atalhos sem IA (abrir app) nao esperam.
            skipped_steps: set = set()
            from core.user_settings import load as _settings
            if (_settings().get("plan_review") and not dry_run and not from_voice
                    and plan.get("fast_path") != "abrir"):
                with self._lock:
                    if self._cancel_event.is_set():
                        return
                    self._plan_gate.clear()
                    self._plan_ok = False
                    self._plan_skip = set()
                    self._plan_token = secrets.token_hex(16)
                self._emit("plan_review", {"token": self._plan_token, "plan": {
                    "summary": plan.get("analysis", ""),
                    "steps": [f"[{s.get('agent', '')}] {s.get('task', '')}" for s in plan.get("subtasks", [])]}})
                self._log("INFO", "MAESTRO", "Aguardando aprovação do plano")
                approved = self._plan_gate.wait(180) and self._plan_ok
                with self._lock:
                    self._plan_token = ""
                    skipped_steps = {n for n in self._plan_skip if n <= len(plan.get("subtasks", []))}
                # Pular todos os passos = nao executar nada
                if approved and skipped_steps and len(skipped_steps) >= len(plan.get("subtasks", [])):
                    approved = False
                if not approved or not self._alive():
                    self._emit("cancelled", {"msg": "Plano não aprovado."})
                    entry["error"] = "plano não aprovado"
                    turn["recorded"] = True
                    return

            # Plano proposto e validado vai para o segundo cerebro antes de
            # executar; cada agente anexa seus passos e a validacao.
            # Simulacao nao deixa rastro no segundo cerebro (o plano simulado viraria referencia)
            brain_plan = None if dry_run else self._brain.write_plan(task, plan)

            subtasks = plan.get("subtasks", [])
            skipped = set(skipped_steps)
            turn["content"] = turn_content(subtasks, task)
            entry["subtasks"] = [
                {"agent": s.get("agent", ""), "task": s.get("task", "")}
                for s in subtasks
            ]
            entry["skills"] = plan.get("skills", [])

            self._emit("plan_ready", {"plan": {
                "task_summary": plan.get("analysis", ""),
                "route": entry.get("route", ""),
                "steps": [
                    {
                        "step": i + 1,
                        "description": f"[{s['agent']}] {s['task']}",
                        "action": s["agent"],
                    }
                    for i, s in enumerate(subtasks)
                ],
                "skills": plan.get("skills", []),
            }})

            self._ledger_call(ledger.plan, task_id, [f"[{s['agent']}] {s['task']}" for s in subtasks])
            self.capture.clear_records()
            step_n = 0
            ctx_mgr = self._ContextManager()
            cont_target = self.session.target(target)
            cont_used = False
            from core.task_schedule import Availability
            schedule = run.make_schedule(subtasks, skipped)
            runtime = run.runtime
            objective_replan = self._config.get("execution.objective_replan", True) is True
            self.engine._target_hwnd = None
            entry["runtime"] = {}

            for node, subtask in zip(schedule.nodes, subtasks):
                si = node.id - 1
                if not self._alive():
                    self._emit("cancelled", {"msg": "Cancelado."})
                    return

                availability = schedule.availability(node)
                dependency = node.dependency
                self._ledger_call(ledger.checkpoint, task_id, node.id, dependency, availability.value)
                # Passo pulado na revisao (ou que depende de um pulado): nao executa e nao conta como falha
                if availability is Availability.SKIPPED:
                    skipped.add(si + 1)
                    self._log("INFO", "MAESTRO", f"Subtarefa {si + 1} pulada por você.")
                    continue
                if availability is Availability.BLOCKED:
                    all_success = False
                    self._log("WARN", "MAESTRO", f"Subtarefa {si + 1} bloqueada: pre-requisito {dependency} falhou.")
                    continue
                subtask = ctx_mgr.prepare_subtask(subtask, si)

                agent_name = subtask.get("agent", "").upper()
                agent = self.agents.get(agent_name)
                if not agent:
                    all_success = False
                    self._log("WARN", "MAESTRO",
                              f"Agente desconhecido: {agent_name}")
                    continue

                subtask_params = dict(subtask.get("params", {}) or {})
                # Continuation capabilities are owned by Session, never supplied by the model.
                subtask_params.pop('continue', None)
                subtask['params'] = subtask_params
                # Continuacao: entrega ao agente o alvo ja aberto (aba, janela, projeto)
                from core.routing import continue_target_for
                tgt, why = continue_target_for(self.session, agent_name, subtask_params, target,
                                               task, cont_used)
                if tgt:
                    subtask_params["continue"] = tgt
                    subtask["params"] = subtask_params
                    cont_used = cont_used or why == "resolver"
                    self._log("INFO", agent_name, f"Continuando em: {tgt.get('key') or tgt['type']} ({why})")
                turn["agents"].append(agent_name)
                agent_task = subtask.get("task", "")
                # Versao original (do usuario) — usada por agentes que precisam
                # do tema puro (CodeAgent: topic + theme leak). O Maestro
                # garante via `setdefault` no analyze(). Fallback para `task`.
                original_task = subtask.get("original_task", agent_task)
                dep = subtask.get("depends_on")

                self._emit("phase", {"phase": "agent", "msg": f"{agent_name} Agent..."})
                self._log("INFO", agent_name, f"Iniciando: {agent_task[:80]}")

                legacy_ctx = None
                if dep is not None:
                    try:
                        extracted = ctx_mgr.get(int(dep))
                        if extracted:
                            legacy_ctx = {
                                "agent": extracted.get("agent"),
                                "results": extracted.get("output", []),
                                "files": extracted.get("files", []),
                                "folder": extracted.get("folder"),
                                "primary_path": extracted.get("primary_path"),
                                "url": extracted.get("url"),
                            }
                    except (ValueError, TypeError):
                        pass

                # Plano do agente
                if agent_name == "DESKTOP" and subtask_params.get("app"):
                    agent_plan = agent.plan(
                        {"task": agent_task, "params": subtask_params,
                         "original_task": original_task},
                        context=subtask_params,
                    )
                else:
                    # Propaga `original_task` no payload do agente. Agentes
                    # que ignoram esse campo continuam funcionando normal
                    # (backward-compat).
                    payload = {"task": agent_task, "original_task": original_task,
                               "params": subtask_params}
                    agent_plan = agent.plan(payload, context=legacy_ctx)
                self._emit_usage()
                lap("agent_plan")

                # Rastro dos 3 subagentes do agente (entender/montar/conferir)
                sub_traces = agent_plan.get("subagents") or []
                if sub_traces:
                    from agents.subagents import summarize
                    self._log("INFO", agent_name, "Subagentes: " + summarize(sub_traces))

                if agent_plan.get("error") or not agent_plan.get("steps"):
                    # Plano vazio/falho = subtask nao executada. Antes isso
                    # nao marcava falha e a tarefa ia para a memoria como
                    # "sucesso".
                    all_success = False
                    why = agent_plan.get('error') or agent_plan.get('reason') or 'sem steps'
                    self._log("ERROR", agent_name, f"Plano falhou: {why}")
                    if not entry.get("error"):
                        entry["error"] = f"O agente {agent_name} não montou o plano: {why}"[:300]
                    continue

                agent_steps = agent_plan.get("steps", [])

                # O agente propoe; o Maestro valida os passos contra as
                # politicas antes de qualquer acao no computador.
                from core.plan_validator import validate_steps
                step_check = validate_steps(agent_name, subtask, agent_steps, task)
                used_skills = self._brain.last_skills.pop(agent_name, [])
                if used_skills:
                    self._log("INFO", agent_name, "Skills aplicadas: " + ", ".join(used_skills))
                    entry.setdefault("agent_skills", {})[agent_name] = used_skills
                self._brain.append_agent_plan(brain_plan, agent_name, subtask,
                                              agent_steps, step_check, sub_traces)
                if not step_check.approved:
                    all_success = False
                    self._log("WARN", "MAESTRO",
                              f"Passos do agente {agent_name} reprovados: {step_check.summary()}")
                    # O motivo real vai para a resposta: antes saia "nao veio detalhe do motivo"
                    if not entry.get("error"):
                        entry["error"] = f"Política recusou os passos ({agent_name}): {step_check.summary()}"[:300]
                    if hasattr(agent, "report_result") and not dry_run:
                        agent.report_result({"task": agent_task}, False)
                    continue

                sub_results = []
                sub_ok = True
                is_desktop = agent_name == "DESKTOP"
                ws_snapshot = dict(self.engine.workspace)
                # Acoes longas (piloto do navegador) param no Esc e narram cada turno
                self.engine.should_stop = run.interrupted
                self.engine.current_agent = agent_name
                self.engine.authorized_task = said
                self.engine.effect_scope = task_id      # cada efeito no maximo uma vez nesta tarefa
                self.engine.effect_session = self.session.id
                self.engine.confirm_effect = lambda question: self._wait_effect(question, from_voice)
                def copy_probe(source, destination):
                    if not dry_run:
                        self._ledger_call(ledger.copy_intent, task_id, step_n, source, destination)
                self.engine.copy_probe = copy_probe
                def on_progress(msg, _a=agent_name):
                    self._log("INFO", _a, msg)
                    # O piloto age por dentro de um passo: e o rastro do que ele ja fez se o app cair
                    self._ledger_call(ledger.progress, task_id, step_n, msg)
                self.engine.on_progress = on_progress

                for j, step in enumerate(agent_steps):
                    if not self._alive():
                        self._emit("cancelled", {"msg": "Cancelado."})
                        return
                    step_n += 1
                    action = step.get("action", "")
                    params = step.get("params", {})
                    desc = step.get("description", "")
                    start_time = time.time()

                    self._emit("step_start", {
                        "step": step_n,
                        "total": step_n + len(agent_steps) - j - 1,
                        "desc": f"[{agent_name}] {desc}",
                        "action": action,
                        "progress": round(si / max(1, len(subtasks)) * 100),
                    })

                    self._ledger_call(ledger.step_started, task_id, step_n, agent_name, action, params, desc)
                    def dispatch(arguments):
                        return self.engine.execute(action, arguments, dry_run=dry_run)

                    from core.action_policy import authorize
                    result = run.execute_step(
                        agent_name, action, params, dispatch, retry=action in RETRY_ACTIONS,
                        adaptive=objective_replan, phase_iv=not objective_replan,
                        authorize_patch=lambda updated: not authorize(agent_name, said, action, updated),
                        allow_directory=lambda path: not authorize("FILE", said, "list_files", {"path": path}),
                        on_patch=lambda patch: self._ledger_call(ledger.note, task_id, "replan", step=step_n,
                                                               strategy=patch.strategy, observation=patch.observation),
                        before_retry=lambda: self._ledger_call(ledger.step_retry, task_id, step_n, action))
                    entry["runtime"].update(actions=runtime.actions, retries=runtime.retries,
                                            recovered=runtime.recovered, replans=runtime.replans)
                    # Segunda conferencia fora do handler (core/verification.py): falso sucesso nao ensina nada
                    from core.verification import apply_independent_check
                    result = apply_independent_check(action, params, result)
                    if result.get("false_success"):
                        entry["runtime"]["false_successes"] = entry["runtime"].get("false_successes", 0) + 1
                        self._log("WARN", agent_name, f"Conferência independente divergiu: {action}")
                    self._ledger_call(ledger.step_finished, task_id, step_n, action, result)

                    if result.get("status") in ("needs_confirmation", "action_limit", "timeout", "cancelled",
                                                "uncertain", "partial", "budget_limit"):
                        entry["error"] = result["result"]
                        self._emit("error", {"msg": entry["error"]})
                        return

                    # frase final do piloto; so vale se ele foi o ULTIMO passo do pedido
                    turn["say"] = getattr(self.engine, "last_say", "") or ""

                    # Subagente de conferencia pos-passo (ex.: ContentGuard do
                    # WebAgent marca prompt injection no conteudo lido).
                    if hasattr(agent, "review_step"):
                        result = agent.review_step(step, result)

                    if not result.get("success", True):
                        all_success = False
                        sub_ok = False
                        self._log("WARN", agent_name,
                                  f"Step falhou: {action}",
                                  {"error": result.get("error", "")})
                    else:
                        self._log("INFO", agent_name, f"OK: {action}")

                    duration = int((time.time() - start_time) * 1000)
                    try:
                        from core.action_logger import log_action
                        log_action(agent_name, action, params, result,
                                   duration_ms=duration)
                    except Exception:
                        pass

                    all_records.append(result)
                    sub_results.append(result.get("result", ""))

                    cap = None
                    if (self._config.get("privacy.capture_enabled", False)
                            and not dry_run and action not in NO_SCREENSHOT
                            and not is_desktop):
                        try:
                            cap = self.capture.capture_step(
                                step_n, desc, action, result.get("result", "")
                            )
                        except Exception:
                            pass

                    self._emit("step_done", {
                        "step": step_n,
                        "total": step_n + len(agent_steps) - j - 1,
                        "ok": result.get("success", False),
                        "result": result.get("result", ""),
                        "desc": f"[{agent_name}] {desc}",
                        "action": action,
                        "screenshot": (cap.get("filename")
                                       if cap and cap.get("filename") else None),
                        "progress": round((si + 1) / max(1, len(subtasks)) * 100),
                    })
                    if not result.get("success", False):
                        break  # subsequent actions may require the failed click/open/type
                    time.sleep(0.05)
                lap("steps")
                schedule.finish(node, sub_ok)
                self._ledger_call(ledger.checkpoint, task_id, node.id, dependency,
                                  "succeeded" if sub_ok else "failed")

                if not dry_run and hasattr(agent, "report_result"):
                    agent.report_result({"task": agent_task}, sub_ok)

                if not dry_run:
                    extracted = ctx_mgr.extract(
                        subtask_index=si,
                        agent_name=agent_name,
                        step_results=sub_results,
                        engine_workspace=self.engine.workspace,
                        workspace_snapshot=ws_snapshot,
                    )
                    if (extracted.get("files") or extracted.get("folder")
                            or extracted.get("url")):
                        self._emit("context_extracted", {
                            "subtask": si + 1,
                            "agent": agent_name,
                            "folder": extracted.get("folder"),
                            "files": extracted.get("files", []),
                            "primary_path": extracted.get("primary_path"),
                            "url": extracted.get("url"),
                        })
                        # Acumula no historico
                        if extracted.get("folder"):
                            entry["artifacts"]["folder"] = extracted.get("folder")
                        if extracted.get("files"):
                            entry["artifacts"]["files"] = extracted.get("files", [])
                        if extracted.get("url"):
                            entry["artifacts"]["url"] = extracted.get("url")
                    # O que ficou aberto vira contexto do proximo pedido
                    from core.observer import observe
                    seen = observe(agent_name, subtask_params, extracted, self.session)
                    if seen:
                        self._log("INFO", agent_name, f"Sessao: {seen}")
                    if extracted.get("summary") or extracted.get("text"):
                        turn["summary"] = extracted.get("summary") or extracted.get("text", "")[:400]

            # Restaura browser SO no final
            if getattr(self.engine, "vision", None):
                try:
                    self.engine.vision.restore_browser()
                except Exception:
                    pass

            if not dry_run and verified_success(all_records):
                # Registra a ROTA (agentes + tipo de acao, sem conteudo) com
                # o resultado. Falhas tambem contam: rota que falha mais do
                # que funciona deixa de ser sugerida ao Maestro.
                try:
                    mem = self.memory.record(task, subtasks, all_success)
                    if mem.get("saved"):
                        self._log("INFO", "MEMORY",
                                  f"Rota registrada ({'sucesso' if all_success else 'falha'})")
                except Exception as mem_err:
                    self._log("WARN", "MEMORY", f"Falha ao registrar rota: {mem_err}")

            # Auto-aperfeicoamento: o resultado ensina (ou desensina) o molde deste tipo de pedido. So planos do Maestro
            # ou ja aprendidos; atalhos sem IA nao precisam. Passo pulado na revisao nao conta como sucesso do plano.
            if learn_source is not None and all_records and not skipped_steps \
                    and (learn_source.get("learned_key") or not learn_source.get("fast_path")):
                try:
                    if self._alive():
                        status = get_learned().observe_execution(
                            task, learn_source, all_success, records=all_records, run_id=task_id)
                    else:
                        status = None
                    entry["learned"] = bool(learn_source.get("learned_key"))
                    if status == "promoted" and not learn_source.get("learned_key"):
                        self._log("INFO", "MEMORY", "Aprendi este tipo de pedido: das próximas vezes, sem chamar a IA")
                    elif status in ("candidate", "blocked") and learn_source.get("learned_key"):
                        self._log("WARN", "MEMORY", "O plano aprendido falhou; volto a planejar com a IA")
                except Exception as learn_err:
                    self._log("WARN", "MEMORY", f"Aprendizado não registrado: {type(learn_err).__name__}")

            # NB: o registro de execucoes vive em desktop/history_store.py
            # (gravado no finally desta funcao). Aprendizado de rotas vive
            # em memory/workflow_store v6.

            self._emit("task_done", {
                "msg": "Execucao concluida." if all_success else "Execucao concluida com falhas.",
                "success": all_success,
                "verified": verified_success(all_records),
                "steps": step_n,
                "dry_run": dry_run,
                "skills": plan.get("skills", []),
                "context_summary": ctx_mgr.summary(),
            })
            self._log("INFO", "SYSTEM",
                      f"Execucao concluida em {step_n} step(s).")

            if gen_report and not dry_run:
                self._emit("phase", {"phase": "reporting",
                                   "msg": "Gerando relatorio..."})
                report = self.narrator.generate_report(
                    task, all_records, self.capture.get_captures_as_base64(3)
                )
                self._emit("report_ready", {"report": report})

            entry["success"] = all_success
            if not all_success:
                # Falhou depois de um efeito ja confirmado (envio, pagamento): a resposta avisa, senao a pessoa
                # repete o pedido e o efeito sai duas vezes
                from core.action_risk import effects_note
                done = getattr(self.engine, "effects_done_in", lambda _s: [])(task_id)
                if isinstance(done, list) and done:
                    entry["effects_done"] = done
                    entry["effects_note"] = effects_note(done)
            if not all_success and not entry.get("error"):
                # O que falhou DE VERDADE (para a tela e para a resposta nao chutar a causa)
                bad = [f"{r.get('action', '')}: {str(r.get('result', ''))[:140]}"
                       for r in all_records if not r.get("success", True)]
                if bad:
                    entry["error"] = "Passo que falhou — " + " | ".join(bad[:2])

        except Exception as e:
            tb = traceback.format_exc()
            self._emit("error", {"msg": str(e), "trace": tb})
            self._log("ERROR", "SYSTEM", f"Excecao: {e}", {"trace": tb})
            entry["error"] = str(e)
        finally:
            try:
                if self._cancel_event.is_set():
                    idle = getattr(self, "_watchdog_fired", None) == self._tls.run_id
                    entry.update(success=False, status="cancelled",
                                 error="parado: a tarefa ficou sem avançar" if idle else "cancelado pelo usuario")
                entry["verified"] = entry.get("success") is True and verified_success(all_records)
                # Conversa: este pedido vira contexto do proximo (mesmo se falhou) e ja fica gravado
                reply_target = (None, None)
                if not turn["recorded"]:
                    try:
                        reply_target = self._record_turn(said, task, turn, entry)
                    except Exception as sess_err:
                        print(f"  [Sessao] Falhou ao registrar: {sess_err}")
                entry["ended_at"] = datetime.now().isoformat(timespec="seconds")
                entry["duration_ms"] = int((time.time() - task_start) * 1000)
                self._ledger_call(ledger.finish, task_id,
                                  "cancelled" if entry.get("status") == "cancelled"
                                  else "completed" if entry.get("success") else "failed",
                                  verified=entry["verified"], error=entry.get("error"))
                # Metricas REAIS desta execucao (delta do AIClient)
                entry["metrics"] = self._metrics_delta(
                    metrics_before, self._ai_client.metrics)
                try:
                    history_store.append(entry)
                    self._emit("history_changed", {"entry": entry})
                except Exception as hist_err:
                    print(f"  [History] Falhou ao gravar: {hist_err}")
                # A resposta ao usuario sai primeiro (em segundo plano); gravar no
                # Obsidian nao atrasa o "Pronto" na tela nem na voz.
                if not turn["recorded"]:
                    self._after_turn(said, task, turn, entry, *reply_target)
                # Segundo cerebro: plano vira "executado"/"falhou" e a execucao
                # entra em 40 Execucoes/Sucesso ou Falhas (consulta futura).
                if not str(entry.get("error") or "").startswith(("clarification", "limitation")):
                    try:
                        self._brain.finish(brain_plan, entry, all_records)
                    except Exception as brain_err:
                        print(f"  [Brain] Falhou ao registrar: {brain_err}")

            finally:
                with self._lock:
                    if self._is_current():
                        self.state["running"] = False
                self._emit("execution_finished", {"success": entry.get("success", False),
                                                  "status": entry.get("status", "finished")})
