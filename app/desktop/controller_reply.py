"""Conversa e resposta do Controller (separadas de desktop/controller.py).

Gravar o pedido na conversa, escrever a resposta do assistente em segundo plano, a conversa com ferramentas
(ChatAgent) e o desfazer. O Controller herda ReplyMixin; o laço de execução continua em controller.py.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

from desktop.event_bus import bus


class ReplyMixin:
    """Conversa e resposta; usa self.session, self._emit e self._session_lock do Controller."""

    def _record_turn(self, said: str, task: str, turn: dict, entry: dict):
        """O pedido entra na conversa e a conversa e gravada JA, antes da resposta (que leva segundos):
        trocar de conversa nesse meio tempo nao pode apagar o pedido. Devolve (id da conversa, Turn)."""
        with self._session_lock:
            recorded = self.session.add_turn(said, task, turn["kind"], turn["agents"], entry.get("success"),
                                             turn["summary"] or entry.get("error") or "", turn.get("content", ""))
            session_id = self.session.id
            try:
                self.session.save()
                if len(self.session.turns) == 1:
                    self.session.remember_active(session_id)
            except Exception as e:
                print(f"  [Sessao] nao gravou: {type(e).__name__}: {e}")
        return session_id, recorded

    def _store_reply(self, session_id: str, recorded, reply: str) -> None:
        """Grava a resposta no pedido que a originou: na conversa aberta se ainda for a dele, senao direto no
        arquivo da conversa dele. Nunca em outra conversa nem em outro pedido."""
        from core.session import Session
        with self._session_lock:
            if self.session.id == session_id and self.session.set_reply(recorded, reply):
                self.session.save()
                return
        Session.set_saved_reply(session_id, recorded, reply)

    def _after_turn(self, said: str, task: str, turn: dict, entry: dict,
                    session_id: Optional[str] = None, recorded=None) -> None:
        """Depois de cada pedido: a resposta do assistente (natural, como numa conversa). Em segundo plano:
        nao atrasa o proximo pedido. O pedido ja foi gravado (_record_turn); aqui so entra a resposta."""
        err = str(entry.get("error") or "")
        kind = turn.get("kind")
        note = str(entry.get("effects_note") or "")

        def noted(text: str) -> str:
            # Deterministico: o aviso de efeito ja feito nunca depende do modelo que escreve a resposta
            return f"{text} {note}".strip() if note and note not in text else text
        reply_run_id = getattr(getattr(self, '_tls', None), 'run_id', getattr(self, '_run_id', None))
        reply_session_id = session_id or getattr(self.session, 'id', None)

        def work():
            reply, speak = "", False
            try:
                if kind == "question":
                    reply = turn.get("summary", "")
                elif err.startswith("clarification"):
                    with self._session_lock:
                        reply = (self.session.pending or {}).get("question", "") \
                            if self.session.id == reply_session_id else ""
                elif err.startswith("limitation"):
                    reply = err.split(":", 1)[-1].strip()
                elif turn.get("voice") and kind != "cancel":
                    # O GPT-Live já conversa e formula a fala: recebe o resultado diretamente,
                    # sem outra chamada ao modelo apenas para reescrever a mesma informação.
                    reply = noted(str(turn.get("say") or turn.get("summary") or err or "A execução não retornou detalhes."))
                    bus.emit("assistant_message", {"said": said, "text": reply, "speak": True,
                             "success": bool(entry.get("success")), "verified": bool(entry.get("verified")),
                             "run_id": reply_run_id, "session_id": reply_session_id, "source": "executor"})
                elif kind != "cancel" and turn.get("say"):
                    # O piloto ja escreveu a frase para o usuario no ultimo turno: sai na hora,
                    # sem mais uma chamada de IA (~1,5 s antes da resposta falada)
                    from core.reply import informative
                    reply = noted(turn["say"])
                    speak = informative(turn.get("summary", "") or reply, bool(entry.get("success"))) or bool(note)
                    bus.emit("assistant_message", {"said": said, "text": reply, "speak": speak,
                                                   "success": bool(entry.get("success")),
                                                   "run_id": reply_run_id, "session_id": reply_session_id})
                elif kind != "cancel":
                    from core.reply import compose
                    with self._session_lock:
                        recent = [t.reply for t in self.session.turns[-4:] if t.reply]
                    r = compose(said, task, turn.get("summary", ""), bool(entry.get("success")), err, recent)
                    reply, speak = noted(r["text"]), r["speak"] or bool(note)
                    bus.emit("assistant_message", {"said": said, "text": reply, "speak": speak,
                                                   "success": bool(entry.get("success")),
                                                   "run_id": reply_run_id, "session_id": reply_session_id})
                if reply and recorded is not None and reply_session_id:
                    self._store_reply(reply_session_id, recorded, reply)
            except Exception as e:
                print(f"  [Resposta] falhou: {type(e).__name__}: {e}")
            finally:
                bus.emit("conversations_changed", {"id": reply_session_id})
        threading.Thread(target=work, daemon=True, name="assistant-reply").start()

    def _run_undo(self, dry_run: bool, turn: dict) -> bool:
        """"desfaz": volta a versao anterior do projeto de codigo da conversa."""
        code = self.session.code or {}
        folder = code.get("folder", "")
        turn["agents"].append("CODE")
        self._emit("plan_ready", {"plan": {
            "task_summary": "desfazer a ultima alteracao",
            "steps": [{"step": 1, "description": "[CODE] Voltar a versao anterior do projeto",
                       "action": "CODE"}],
            "skills": []}})
        self._emit("step_start", {"step": 1, "total": 1, "action": "revert_project",
                                  "desc": "[CODE] Voltar a versao anterior", "progress": 0})
        open_t = "index.html" if os.path.exists(os.path.join(folder, "index.html")) else ""
        self.engine.current_agent, self.engine.authorized_task = 'CODE', 'desfazer ultima edicao'
        r = self.engine.execute("revert_project", {"folder": folder, "open": open_t}, dry_run=dry_run)
        self._emit("step_done", {"step": 1, "total": 1, "ok": r.get("success", False),
                                 "result": r.get("result", ""), "action": "revert_project",
                                 "desc": "[CODE] Voltar a versao anterior", "progress": 100})
        turn["summary"] = str(r.get("result", ""))[:300]
        self._emit("task_done", {"msg": "Concluido.", "steps": 1, "dry_run": dry_run})
        return bool(r.get("success"))

    def _chat_enabled(self, dry_run: bool, from_voice: bool = False) -> bool:
        """Conversa para pedidos de verdade, digitados ou falados (a fala recebe resposta curta, para ser lida
        em voz alta). Simular nao le nada: nenhum handler roda em simulacao. chat.voice: false devolve a voz ao
        fluxo antigo."""
        if dry_run:
            return False
        config = getattr(self, "_config", None)
        if config is None or not config.get("chat.enabled", True):
            return False
        return bool(config.get("chat.voice", True)) if from_voice else True

    def _run_chat(self, said: str, task: str, entry: dict, spoken: bool = False, allow_actions: bool = True):
        """Uma volta da conversa (agents/chat_agent.py) com texto em streaming e cada leitura como passo na tela.
        Falha do modelo nunca derruba o pedido: devolve None e o pedido segue pelo Maestro."""
        from agents.chat_agent import ChatAgent
        run_id = self._tls.run_id
        self._emit("phase", {"phase": "agent", "msg": "Pensando na resposta...", "run_id": run_id})
        pending: list[str] = []
        sent: list[str] = []
        offset, seq, last = 0, 0, 0.0
        steps = {"n": 0, "open": {}}

        def emit_stream(op: str, text: str) -> None:
            nonlocal seq, last, offset
            self._emit("answer_delta", {"v": 1, "run_id": run_id, "seq": seq, "op": op,
                                        "offset": offset, "text": text})
            seq += 1
            last = time.monotonic()
            length = len(text.encode("utf-16-le", errors="surrogatepass")) // 2
            offset = offset + length if op == "append" else length

        def on_reset(text: str) -> None:
            pending.clear()
            sent[:] = [text]
            emit_stream("replace", text)

        def on_text(piece: str) -> None:
            pending.append(piece)
            now = time.monotonic()
            if now - last >= 0.06:  # ~16 eventos/s, com checkpoints esparsos para reparar lacunas.
                batch = "".join(pending)
                pending.clear()
                sent.append(batch)
                if seq % 32 == 0:
                    emit_stream("replace", "".join(sent))
                else:
                    emit_stream("append", batch)

        def on_tool(name: str, label: str, ok, result: str) -> None:
            if ok is None:
                steps["n"] += 1
                steps["open"][name] = steps["n"]
                self._emit("step_start", {"step": steps["n"], "total": steps["n"], "desc": f"[CHAT] {label}",
                                          "action": name, "progress": 0})
                return
            n = steps["open"].pop(name, steps["n"])
            self._emit("step_done", {"step": n, "total": steps["n"], "ok": bool(ok), "result": result,
                                     "desc": f"[CHAT] {label}", "action": name, "progress": 0})
            self._log("INFO" if ok else "WARN", "CHAT", f"{label}: {'ok' if ok else result}")

        from agents.chat_agent import ChatResult
        from core.ai_client import LLMCancelled
        agent = getattr(self, "chat", None)
        try:
            if agent is None:
                agent = self.chat = ChatAgent(client=self._ai_client, config=self._config)
            result = agent.respond(said, self.session, task=task, on_text=on_text, on_tool=on_tool,
                                   should_stop=lambda: not self._alive(), spoken=spoken,
                                   allow_actions=allow_actions, on_reset=on_reset)
        except LLMCancelled as error:
            if seq:
                on_reset("")
            # Prazo da chamada estourado: parar e avisar. Cair no Maestro seria uma segunda espera longa.
            self._log("WARN", "CHAT", str(error))
            return ChatResult("failed", str(error))
        except Exception as error:
            if seq:
                on_reset("")
            self._log("WARN", "CHAT", f"Conversa indisponível ({type(error).__name__}); seguindo sem ela.")
            return None
        finally:
            self._emit_usage()
        if result.kind == "answer":
            emit_stream("final", result.text)
        elif seq:
            on_reset("")
        used = sorted(set(result.tools_used) - {"executar_no_computador", "abrir_no_computador"})
        entry["subtasks"] = [{"agent": "CHAT", "task": "conversa" + (f" ({', '.join(used)})" if used else "")}]
        return result

    def _answer_without_running(self, res: dict, said: str, task: str, target, entry: dict, turn: dict,
                                ledger, task_id: str, dry_run: bool, from_voice: bool, chat_on: bool) -> bool:
        """Pedidos que se resolvem sem executar nada no computador: olhar a tela, cancelar sem tarefa, pergunta
        respondida pelo resolvedor, esclarecimento, desfazer, status das tarefas e pergunta sobre um arquivo que o
        assistente criou. True = respondido (o _run_inner encerra); False = segue para planejar e executar."""
        kind = res["kind"]
        if kind == "look":
            # Camada de harness: o Vision so olha a tela e responde; nenhuma acao no computador
            self._emit("phase", {"phase": "maestro", "msg": "Olhando a tela..."})
            from core.screen_question import answer as look_answer
            seen = look_answer(said, getattr(self.engine, "vision", None))
            self._emit_usage()
            self._emit("answer", {"msg": seen["answer"], "observation": seen,
                                  "run_id": self._tls.run_id, "session_id": self.session.id})
            entry["subtasks"] = [{"agent": "VISION", "task": "olhar a tela e responder"}]
            turn["kind"] = "question"
            turn["summary"] = seen["answer"]
            entry["success"] = bool(seen["ok"])
            if not seen["ok"]:
                entry["error"] = "leitura da tela sem resposta"
            return True
        if kind == "cancel":
            self._emit("answer", {"msg": "Nada em execução para parar."})
            entry["success"] = True
            turn["recorded"] = True     # nao entra na conversa
            return True
        # Comentario/papo ("legal, ficou bom", "valeu") digitado tambem vai para a conversa: resposta natural,
        # com a conversa inteira, em vez de frase pronta. So responde (sem ferramentas de acao). Na voz, a
        # resposta curta do entendimento fica (latencia).
        chat_reply = chat_on and kind == "question" and (
            res.get("via") == "llm" or (res.get("via") in ("chat", "papo") and not from_voice))
        if kind == "question" and not chat_reply:
            self._emit("answer", {"msg": res["answer"], "run_id": self._tls.run_id})
            turn["summary"] = res["answer"]
            entry["success"] = True
            return True
        if kind == "clarify":
            self.session.set_pending(res["question"], task, target)
            self._emit("error", {"msg": res["question"], "kind": "clarification"})
            entry["error"] = "clarification_required"
            turn["recorded"] = True     # a resposta continua o pedido (pending)
            return True
        if kind == "undo":
            ok = self._run_undo(dry_run, turn)
            entry["success"] = ok
            return True

        # "Como esta o site?" / "verificar o estado e informar o status": responde com o
        # registro de tarefas e nao executa nada (antes criava um projeto novo)
        from core.task_status import describe, is_status_question
        if res.get("via") != "pending" and (is_status_question(said) or is_status_question(task)):
            ans = describe(ledger, exclude=task_id)
            self._emit("answer", {"msg": ans})
            turn["kind"] = "question"
            turn["summary"] = ans
            entry["success"] = True
            return True

        # Pergunta sobre algo que o assistente CRIOU ("resume a planilha que voce gerou"):
        # le o arquivo e responde numa chamada (antes: piloto lendo a tela, 2 min e falha)
        from core import artifact_qa
        last = self.session.turns[-1] if self.session.turns else None
        just_created = bool(last and last.success and set(last.agents) & {"DATA", "CODE"})
        art = artifact_qa.wants_answer(task, getattr(self.session, "files", []), just_created)
        if art and not dry_run:
            self._emit("phase", {"phase": "maestro", "msg": "Lendo o arquivo..."})
            try:
                ans = artifact_qa.answer(task, art)
            except Exception as qa_err:
                ans = ""
                self._log("WARN", "MAESTRO", f"Leitura do arquivo falhou: {qa_err}")
            self._emit_usage()
            entry["subtasks"] = [{"agent": "READER", "task": f"ler {os.path.basename(art)}"}]
            turn["kind"] = "question"
            if ans:
                self._log("INFO", "MAESTRO", f"Respondido lendo {os.path.basename(art)}")
                self._emit("answer", {"msg": ans})
                turn["summary"] = ans
                entry["success"] = True
                return True
            # Ler a TELA nao resolve (a grade do Excel nao expoe os valores): avisa em vez de
            # cair no piloto, que gastava 30 s e falhava do mesmo jeito
            msg = (f"Abri o arquivo {os.path.basename(art)}, mas não consegui montar a resposta agora. "
                   "Quer que eu tente de novo?")
            self._emit("answer", {"msg": msg})
            turn["summary"] = msg
            entry["success"] = False
            entry["error"] = "leitura do arquivo sem resposta"
            return True
        return False
