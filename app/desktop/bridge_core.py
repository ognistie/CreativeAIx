"""
BridgeCore — a logica da interface, sem Qt.

Tudo o que a tela pede ao nucleo passa por aqui: execucao, conversas, voz, Segundo Cerebro, Diario,
Harness, Lab, modo Desenvolvedor. Duas cascas usam a mesma classe:

    desktop/bridge.py   Bridge(QObject, BridgeCore)  -> QML (Signals e @Slots)
    desktop/server.py   HeadlessBridge(BridgeCore)   -> WebSocket JSON-RPC (interface Tauri)

O estado vive na propria instancia (self._controller, self._voice, ...), entao a casca Qt continua
podendo ser montada com `Bridge.__new__` nos scripts de teste. Cada evento sai por `self._emit(nome,
payload)`: `nome` e o nome do Signal do Bridge (ex.: "planReady") e `payload` e a string JSON que o
Signal carrega, `True/False` em "runningChanged" ou None em "quickEntry". A casca decide como entregar.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from desktop.event_bus import bus
from desktop.controller import Controller
from desktop import history_store


def _to_json(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return "{}"


def _local_path(url: str) -> str:
    """file:///C:/a%20b.png -> C:\a b.png. Caminho comum passa como veio."""
    if not url.startswith("file:"):
        return url
    from urllib.parse import unquote, urlparse
    from urllib.request import url2pathname
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.lower() != "localhost":
        return "\\\\" + parsed.netloc + url2pathname(unquote(parsed.path))
    return url2pathname(unquote(parsed.path))


class BridgeCore:
    """Logica de Bridge sem Qt. Subclasses implementam `_emit` e chamam `_setup_core()`.

    Sem `__init__` de proposito: no Bridge (QObject, BridgeCore) o `QObject.__init__` e cooperativo e
    chamaria o init daqui; os testes que montam o Bridge com `__new__` + `QObject.__init__` nao podem
    criar Controller, voz nem atalhos.
    """

    def _setup_core(self) -> None:
        self._controller = Controller()
        self._running = False
        self._voice = None
        self._stop_hotkey = None
        self._wire_bus()
        # Voz pronta desde o inicio: atalho global ativo e voz aquecida em segundo
        # plano. O reconhecimento carrega alguns segundos depois de abrir (sem
        # disputar com a abertura), para a primeira fala nao esperar o modelo.
        try:
            from core.config import get_config
            vcfg = get_config().get("voice", {}) or {}
            if vcfg.get("start_on_launch", True):
                self._voice_ctl().start_hotkey()
                if vcfg.get("preload_on_launch", True):
                    timer = threading.Timer(4.0, lambda: self._voice_ctl().stt.preload_async())
                    timer.daemon = True
                    timer.start()
        except Exception as e:
            print(f"  [voz] indisponivel: {e}")
        self._start_stop_hotkey()
        self._start_quick_hotkey()

    def _emit(self, name: str, payload: Any = None) -> None:
        """Entrega um evento para a tela. A casca (Qt ou servidor) implementa."""
        raise NotImplementedError

    # ── Janela: sem Qt, a casca Tauri e quem move as janelas ─────────
    def restoreMain(self) -> None:
        self._emit("windowRequest", _to_json({"action": "restore_main"}))

    def closeMini(self) -> None:
        self._emit("windowRequest", _to_json({"action": "close_mini"}))

    def mainActivated(self) -> None:
        self._emit("windowRequest", _to_json({"action": "main_activated"}))

    def setTitleBarColor(self, color: str) -> None:
        """Na casca Tauri a barra de titulo e desenhada pela propria tela."""

    @staticmethod
    def _ui_cfg() -> Dict[str, Any]:
        """config.yaml > ui, com as escolhas da tela Configuracoes por cima."""
        try:
            from core.config import get_config
            cfg = dict(get_config().get("ui", {}) or {})
        except Exception:
            cfg = {}
        try:
            from core.user_settings import load
            mine = load()
            cfg["splash"], cfg["mini_chat"] = mine["splash"], mine["mini_chat"]
        except Exception:
            pass
        return cfg

    def _start_stop_hotkey(self) -> None:
        """Atalho global para parar: o mini chat nao recebe cliques enquanto
        o agente trabalha, entao parar precisa funcionar de qualquer janela."""
        combo = self._ui_cfg().get("stop_hotkey", "ctrl+alt+x")
        if not combo:
            return
        try:
            from core.voice.hotkey import GlobalHotkey
            hk = GlobalHotkey(combo, self._stop_from_hotkey)
            if hk.start_and_wait():
                self._stop_hotkey = hk
            else:
                print(f"  [ui] atalho de parar {combo} indisponivel (em uso por outro programa)")
        except Exception as e:
            print(f"  [ui] atalho de parar indisponivel: {e}")

    def _stop_from_hotkey(self) -> None:
        if self._running:
            self._controller.force_stop()

    # ── Configuracoes, conversas, anexos, plano ─────────────────────
    def getSettings(self) -> str:
        from core.user_settings import load
        data = load()
        data["hotkeys"] = {"voice": getattr(self._voice, "combo", "") if self._voice else "",
                           "stop": self._stop_hotkey.combo if self._stop_hotkey else "",
                           "quick": self._quick_hotkey.combo if getattr(self, "_quick_hotkey", None) else ""}
        return _to_json(data)

    def saveSettings(self, payload: str) -> str:
        """Grava e aplica o que da para aplicar na hora (voz); abertura e mini chat no proximo inicio."""
        from core.user_settings import save
        try:
            data = save(json.loads(payload or "{}"))
        except ValueError:
            return _to_json({"ok": False})
        if self._voice is not None:
            self._voice.barge_in, self._voice.earcon = data["barge_in"], data["earcon"]
            self._voice.live_conversation = data["live_conversation"]
        return _to_json({"ok": True, **data})

    def shutdown(self) -> None:
        """App fechando: nada de voz, atalho ou tarefa pode continuar depois daqui."""
        for hotkey in (self._stop_hotkey, getattr(self, "_quick_hotkey", None)):
            if hotkey is not None:
                hotkey.stop()
        if self._controller.state.get("running"):
            self._controller.force_stop()
        if self._voice is not None:
            self._voice.shutdown()

    def renameConversation(self, sid: str, title: str) -> bool:
        from core.session import Session
        ok = Session.rename_saved(sid, title)
        if ok and sid == self._controller.session.id:
            self._controller.session.custom_title = " ".join(title.split())[:80]
        if ok:
            self._emit("conversationsChanged", _to_json({"id": sid}))
        return ok

    def deleteConversation(self, sid: str) -> bool:
        from core.session import Session
        if self._running and sid == self._controller.session.id:
            return False                 # nao some com a conversa em execucao
        ok = Session.delete_saved(sid)
        if ok:
            if sid == self._controller.session.id:
                self._controller.new_session()
            self._emit("conversationsChanged", _to_json({"id": sid}))
        return ok

    def attachFiles(self, payload: str) -> str:
        """Lista de caminhos (JSON) -> os que existem; ficam na conversa como arquivos legiveis."""
        try:
            paths = [str(p) for p in json.loads(payload or "[]")]
        except ValueError:
            paths = []
        return _to_json(self._controller.attach_files(paths))

    def approvePlan(self, ok: bool, token: str) -> None:
        self._controller.approve_plan(ok, token)

    def approvePlanSteps(self, token: str, skipped_json: str) -> None:
        """Aprova o plano pulando os passos escolhidos (lista de numeros 1..n, em JSON)."""
        try:
            skip = [n for n in json.loads(skipped_json or "[]") if isinstance(n, int)]
        except ValueError:
            skip = []
        self._controller.approve_plan(True, token, skip=skip)

    def _start_quick_hotkey(self) -> None:
        """Acesso rapido de qualquer app (como Alt+Espaco no ChatGPT e o atalho do Claude):
        abre a caixa de pedido por cima do que estiver na tela."""
        self._quick_hotkey = None
        combo = self._ui_cfg().get("quick_hotkey", "alt+space")
        if not combo:
            return
        try:
            from core.voice.hotkey import GlobalHotkey
            hk = GlobalHotkey(combo, lambda: self._emit("quickEntry", None))
            if hk.start_and_wait():
                self._quick_hotkey = hk
            else:
                print(f"  [ui] atalho de acesso rapido {combo} indisponivel (em uso)")
        except Exception as e:
            print(f"  [ui] atalho de acesso rapido indisponivel: {e}")

    def splash_enabled(self) -> bool:
        return self._ui_cfg().get("splash", True) is not False

    def uiSettings(self) -> str:
        cfg = self._ui_cfg()
        # So anuncia o atalho de parar se ele foi registrado de fato
        combo = self._stop_hotkey.combo if self._stop_hotkey else ""
        label = "+".join(k.capitalize() for k in combo.split("+")) if combo else ""
        return _to_json({
            "splash": self.splash_enabled(),
            "mini_chat": cfg.get("mini_chat", True) is not False,
            "stop_hotkey_label": label,
        })

    # ── Segundo cerebro, Voce e Harness ─────────────────────────────
    # Leitura e escrita pela camada pessoal (core/brain_store.py): o vault do repositorio
    # nunca e alterado pela interface. Toda resposta e JSON com "ok" e, se falhar, "error".
    @staticmethod
    def _brain():
        from core.brain import get_brain
        return get_brain()

    def _brain_call(self, fn) -> str:
        try:
            out = fn()
            return _to_json({"ok": True, **(out if isinstance(out, dict) else {"data": out})})
        except FileExistsError:
            return _to_json({"ok": False, "error": "Já existe uma nota com esse nome."})
        except FileNotFoundError:
            return _to_json({"ok": False, "error": "Nota não encontrada."})
        except PermissionError:
            return _to_json({"ok": False, "error": "A pasta do seu cérebro não está disponível."})
        except ValueError as e:
            msg = str(e) or "inválido"
            return _to_json({"ok": False, "error": msg[:1].upper() + msg[1:]})
        except Exception as e:     # nunca derruba a interface
            return _to_json({"ok": False, "error": f"Falhou: {type(e).__name__}"})

    def brainOverview(self) -> str:
        def run():
            b = self._brain()
            notes = b.store.notes()
            return {"personal": str(b.store.personal or ""), "writable": b.store.writable,
                    "notes": notes, "folders": b.store.folders(),
                    "removed": sorted(b.store.removed()),
                    "edited": sum(1 for n in notes if n["layer"] != "base")}
        return self._brain_call(run)

    def brainRead(self, rel: str) -> str:
        def run():
            st = self._brain().store
            if not st.resolve(rel):
                raise FileNotFoundError(rel)
            return {"rel": rel, "text": st.read(rel), "layer": st.layer_of(rel),
                    "links": st.links(rel), "backlinks": st.backlinks(rel)}
        return self._brain_call(run)

    def brainSave(self, rel: str, text: str) -> str:
        return self._brain_call(lambda: {"rel": self._brain().store.write(rel, text)})

    def brainCreate(self, rel: str, text: str) -> str:
        return self._brain_call(lambda: {"rel": self._brain().store.create(rel, text)})

    def brainCreateFolder(self, rel: str) -> str:
        return self._brain_call(lambda: {"rel": self._brain().store.create_folder(rel)})

    def brainRename(self, old: str, new: str) -> str:
        return self._brain_call(lambda: self._brain().store.rename(old, new))

    def brainDelete(self, rel: str) -> str:
        return self._brain_call(lambda: self._brain().store.delete(rel))

    def brainRestore(self, rel: str) -> str:
        return self._brain_call(lambda: self._brain().store.restore(rel))

    def brainSearch(self, query: str) -> str:
        return self._brain_call(lambda: {"items": self._brain().store.search(query)})

    def brainGraph(self) -> str:
        return self._brain_call(lambda: self._brain().store.graph())

    def youProfile(self) -> str:
        from core.harness import YOU_SECTIONS, you_content, you_rel
        def run():
            st = self._brain().store
            return {"writable": st.writable, "sections": [
                {"name": n, "hint": h, "rel": you_rel(n), "text": you_content(st.read(you_rel(n)))}
                for n, h in YOU_SECTIONS]}
        return self._brain_call(run)

    def youSave(self, section: str, text: str) -> str:
        from core.harness import YOU_SECTIONS, you_rel, you_template
        hints = dict(YOU_SECTIONS)
        def run():
            if section not in hints:
                raise ValueError("seção desconhecida")
            body = you_template(section, hints[section]) + (text or "").strip() + "\n"
            return {"rel": self._brain().store.write(you_rel(section), body)}
        return self._brain_call(run)

    def harnessGet(self) -> str:
        def run():
            h = self._brain().harness
            return {"harness": h.load(), "versions": h.versions(), "writable": h.folder is not None}
        return self._brain_call(run)

    def harnessSave(self, payload: str, label: str) -> str:
        return self._brain_call(lambda: {"harness": self._brain().harness.save(json.loads(payload or "{}"), label)})

    def harnessRestore(self, version_id: str) -> str:
        return self._brain_call(lambda: {"harness": self._brain().harness.restore(version_id)})

    # ── Atividade (core/activity.py): so leitura do historico e da pergunta pendente ──
    def activitySummary(self) -> str:
        from core.activity import summarize
        def run():
            ctl = self._controller
            session = getattr(ctl, "session", None)
            pending = getattr(session, "pending", None) if session is not None else None
            running = ""
            state = getattr(ctl, "state", {}) or {}
            if state.get("running"):
                running = str(state.get("task") or "Tarefa em andamento")
            return summarize(history_store.list_all(limit=500), pending=pending, running=running)
        return self._brain_call(run)

    # ── Configuracoes > Agentes de codigo ──
    def codingAgentsCheck(self) -> None:
        """Confere as CLIs e o MCP numa thread (cada CLI leva ~1 s) e responde por codingStatus."""
        def run():
            try:
                from core.coding_agents import status
                data = {"ok": True, **status()}
            except Exception as exc:
                data = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self._emit("codingStatus", _to_json(data))
        threading.Thread(target=run, daemon=True, name="coding-status").start()

    # ── Papeis de parede (core/wallpapers.py): catalogo com credito + importados na camada pessoal ──
    def wallpapersList(self) -> str:
        from core import wallpapers
        return self._brain_call(lambda: {"items": wallpapers.catalog() + wallpapers.personal(self._brain().store.personal)})

    def wallpaperInfo(self, wallpaper: str) -> str:
        """Caminho e paleta extraida (base, luzes, destaque, texto, reforco do vidro) de um papel escolhido."""
        from core import wallpapers
        def run():
            item = wallpapers.resolve(wallpaper, self._brain().store.personal)
            if item is None:
                raise ValueError("papel de parede desconhecido")
            return {"item": item}
        return self._brain_call(run)

    def wallpaperImport(self, url: str) -> str:
        from core import wallpapers
        path = _local_path(url)
        return self._brain_call(lambda: {"item": wallpapers.import_image(Path(path), self._brain().store.personal)})

    def wallpaperRemove(self, wallpaper: str) -> str:
        from core import wallpapers
        wid = wallpaper.split(":", 1)[1] if wallpaper.startswith("personal:") else ""
        return self._brain_call(lambda: {"removed": wallpapers.remove_personal(wid, self._brain().store.personal)})

    # ── Diario (core/journal.py): caderno pessoal na camada pessoal do Cerebro ──
    def _journal(self):
        return self._brain().journal

    def journalList(self, query: str, tag: str, day: str) -> str:
        j = self._journal()
        return self._brain_call(lambda: {"available": j.available, "items": j.list(query, tag, day),
                                         "tags": j.tags(), **j.config()})

    def journalFolders(self) -> str:
        j = self._journal()
        return self._brain_call(lambda: {"available": j.available, "folders": j.folders(), **j.config()})

    def journalListIn(self, folder: str, query: str, tag: str, day: str) -> str:
        j = self._journal()
        return self._brain_call(lambda: {"available": j.available, "items": j.list(query, tag, day, folder),
                                         "tags": j.tags(), **j.config()})

    def journalGet(self, entry_id: str) -> str:
        e = self._journal().get(entry_id)
        return _to_json({"ok": True, "entry": e} if e else {"ok": False, "error": "Entrada não encontrada."})

    def journalSave(self, payload: str) -> str:
        """{"id"?, "title", "body", "tags", "private"?, "date"?} -> entrada salva (versao nova)."""
        def run():
            d = json.loads(payload or "{}")
            if not isinstance(d, dict):
                raise ValueError("pedido inválido")
            e = self._journal().save(d.get("id") or None, title=str(d.get("title") or ""), body=str(d.get("body") or ""),
                                     tags=d.get("tags") if isinstance(d.get("tags"), list) else [],
                                     private=d.get("private") if isinstance(d.get("private"), bool) else None,
                                     day=str(d.get("date") or ""), folder=str(d.get("folder") or ""))
            return {"entry": e}
        return self._brain_call(run)

    def journalSetPrivate(self, entry_id: str, private: bool) -> str:
        return self._brain_call(lambda: {"entry": self._journal().set_private(entry_id, private)})

    def journalDelete(self, entry_id: str) -> str:
        return self._brain_call(lambda: {"deleted": self._journal().delete(entry_id)})

    def journalDates(self) -> str:
        return self._brain_call(lambda: {"dates": self._journal().dates()})

    def journalSummarize(self, entry_id: str) -> None:
        """Resumo por IA de UMA entrada (a tela ja avisou o que vai para o provedor). Resposta em journalSummary."""
        import threading
        journal = self._journal()

        def ask(system, user):
            from core.ai_client import get_client
            from core.config import get_config
            return get_client().message(model=get_config().get_model("MAESTRO"), system=system, user_content=user,
                                        max_tokens=400, agent="DIARIO")

        def work():
            try:
                out = {"ok": True, "entry": journal.summarize(entry_id, ask)}
            except (ValueError, FileNotFoundError) as e:
                out = {"ok": False, "error": str(e)[:1].upper() + str(e)[1:]}
            except Exception as e:
                out = {"ok": False, "error": f"O resumo não saiu: {type(e).__name__}"}
            self._emit("journalSummary", _to_json(out))
        threading.Thread(target=work, daemon=True, name="journal-summary").start()

    def journalUseInBrain(self, on: bool) -> str:
        return self._brain_call(lambda: self._journal().set_use_in_brain(on))

    def providerStatus(self) -> str:
        """Provedores do proprio app: so se a chave esta configurada (nunca o valor, nem um pedaco dele)."""
        def has(var):
            return bool(os.getenv(var, "").strip())
        return _to_json({"ok": True, "providers": [
            {"name": "Anthropic", "use": "Maestro e agentes (planejar, código, dados, web, arquivos)",
             "configured": has("ANTHROPIC_API_KEY"),
             "next": "Coloque ANTHROPIC_API_KEY no arquivo .env do projeto e reabra o app."},
            {"name": "OpenAI", "use": "Conversa por voz (GPT-Live) e voz falada",
             "configured": has("OPENAI_API_KEY"),
             "next": "Opcional. Para a conversa por voz, coloque OPENAI_API_KEY no .env e reabra o app."},
        ]})

    def historyDetail(self, task_id: str) -> str:
        """Passos e evidencia de uma execucao do Historico (registro de tarefas; segredos mascarados)."""
        import re as _re
        if not _re.fullmatch(r"[\w\-]{6,60}", task_id or ""):
            return _to_json({"ok": False, "error": "Execução inválida."})
        try:
            import mcp_server
            from core.task_ledger import get_ledger, replay
            task = replay(get_ledger().events(task_id))
            clean = lambda v: mcp_server._clean(str(v or ""))[:300]
            steps = sorted([{**s, "ok": True} for s in task["steps_done"]] + [{**s, "ok": False} for s in task["steps_failed"]]
                           + [{**s, "ok": None} for s in task["steps_uncertain"]], key=lambda s: s.get("step") or 0)
            return _to_json({"ok": True, "found": task["events"] > 0, "state": task["state"], "verified": task["verified"],
                             "steps": [{"step": s.get("step"), "action": s.get("action", ""), "description": clean(s.get("description")),
                                        "ok": s["ok"], "verified": bool(s.get("verified"))} for s in steps],
                             "evidence": [{"step": e.get("step"), "result": clean(e.get("result")), "verified": e.get("verified")}
                                          for e in task["evidence"]][:40],
                             "error": clean(task.get("error"))})
        except Exception as e:
            return _to_json({"ok": False, "error": f"Registro indisponível: {type(e).__name__}"})

    # ── AI Research Lab (core/lab.py) ──
    LAB_BUDGET_MAX = 5.0          # teto por experimento real, em US$ (a pessoa escolhe ate aqui)

    def _lab(self):
        from core.lab import get_lab
        return get_lab(self._brain().store.personal)

    def labVersions(self, agent: str) -> str:
        from core.lab import effective_config
        def run():
            rows = self._lab().versions(agent, self._brain().harness)
            return {"versions": rows, "effective": {v["id"]: effective_config(agent, v) for v in rows}}
        return self._brain_call(run)

    def labCreateVariant(self, payload: str) -> str:
        def run():
            d = json.loads(payload or "{}")
            return {"version": self._lab().create_variant(str(d.get("agent", "")), str(d.get("base", "")),
                                                          str(d.get("instructions", "")), d.get("params") or {},
                                                          str(d.get("note", "")))}
        return self._brain_call(run)

    def labDiff(self, a: str, b: str) -> str:
        return self._brain_call(lambda: {"lines": self._lab().diff(a, b)})

    def labPublish(self, version_id: str) -> str:
        return self._brain_call(lambda: {"version": self._lab().publish(version_id, self._brain().harness)})

    def labEvalSets(self) -> str:
        return self._brain_call(lambda: {"sets": self._lab().eval_sets()})

    def labRuns(self) -> str:
        return self._brain_call(lambda: {"runs": self._lab().runs(), "busy": bool(getattr(self, "_lab_busy", False))})

    def labRunDetail(self, run_id: str) -> str:
        return self._brain_call(lambda: {"run": self._lab().run_detail(run_id)})

    def labSkills(self, agent: str) -> str:
        from core.lab import skills_and_tools
        return self._brain_call(lambda: skills_and_tools(agent, self._brain()))

    def labToolTest(self, name: str, args_json: str) -> str:
        from core.lab import test_mcp_tool
        return self._brain_call(lambda: test_mcp_tool(name, json.loads(args_json or "{}")))

    def labObserve(self, agent: str, state: str) -> str:
        from core.lab import observe
        return self._brain_call(lambda: {"tasks": observe(agent, state)})

    def labRun(self, payload: str) -> str:
        """{"set", "versions": [ids], "mode": "simulado"|"real", "confirmed": bool, "budget": US$}.
        Real usa o provedor (custa): so com confirmacao explicita e orcamento ate LAB_BUDGET_MAX."""
        import threading
        from core.lab import real_planner, replay_planner
        try:
            d = json.loads(payload or "{}")
            mode = d.get("mode")
            if mode not in ("simulado", "real"):
                raise ValueError("modo deve ser simulado ou real")
            versions = [str(v) for v in d.get("versions") or []][:2]
            if not versions:
                raise ValueError("escolha ao menos uma versão")
            budget = None
            if mode == "real":
                budget = float(d.get("budget") or 0)
                if d.get("confirmed") is not True:
                    raise ValueError("o modo real precisa da sua confirmação")
                if not 0 < budget <= self.LAB_BUDGET_MAX:
                    raise ValueError(f"orçamento deve ficar entre US$ 0,01 e US$ {self.LAB_BUDGET_MAX:.2f}")
            if getattr(self, "_lab_busy", False):
                raise ValueError("já há um experimento rodando")
        except (ValueError, TypeError) as e:
            return _to_json({"ok": False, "error": str(e)[:1].upper() + str(e)[1:]})
        lab = self._lab()
        planner = real_planner if mode == "real" else replay_planner(lab)
        self._lab_cancel = threading.Event()
        self._lab_busy = True

        def work():
            try:
                run = lab.run(str(d.get("set", "")), versions, planner, origin=mode, cancel=self._lab_cancel,
                              on_event=lambda e: self._emit("labProgress", _to_json(e)), budget_usd=budget)
                self._emit("labFinished", _to_json({"ok": True, "run": run}))
            except Exception as e:
                self._emit("labFinished", _to_json({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}))
            finally:
                self._lab_busy = False
        threading.Thread(target=work, daemon=True, name="lab-run").start()
        return _to_json({"ok": True, "started": True})

    def labFeedback(self, payload: str) -> str:
        def run():
            d = json.loads(payload or "{}")
            return {"result": self._lab().add_feedback(str(d.get("run", "")), str(d.get("version", "")),
                                                       str(d.get("case", "")), str(d.get("note", "")))}
        return self._brain_call(run)

    def labPromotionCheck(self, version_id: str) -> str:
        return self._brain_call(lambda: self._lab().promotion_check(version_id))

    def labPromote(self, version_id: str) -> str:
        return self._brain_call(lambda: {"version": self._lab().promote(version_id, self._brain().harness)})

    def labTraining(self) -> str:
        from core.lab import training_status
        return _to_json({"ok": True, **training_status()})

    def labResearch(self, payload: str) -> str:
        """{"agent", "objective", "confirmed": bool, "budget"}: hipotese pelo modelo + experimento real.
        Usa o provedor (custa): so com confirmacao e orcamento ate LAB_BUDGET_MAX. Nunca publica."""
        import threading
        from core.lab import real_planner, real_proposer
        try:
            d = json.loads(payload or "{}")
            budget = float(d.get("budget") or 0)
            if d.get("confirmed") is not True:
                raise ValueError("a pesquisa usa o modelo e precisa da sua confirmação")
            if not 0 < budget <= self.LAB_BUDGET_MAX:
                raise ValueError(f"orçamento deve ficar entre US$ 0,01 e US$ {self.LAB_BUDGET_MAX:.2f}")
            agent = str(d.get("agent") or "FILE").upper()
            if agent != "FILE":
                raise ValueError("por enquanto a pesquisa roda só com o agente de Arquivos (o único com casos conferíveis)")
            objective = str(d.get("objective") or "").strip()
            if not objective:
                raise ValueError("descreva o objetivo")
            if getattr(self, "_lab_busy", False):
                raise ValueError("já há um experimento rodando")
        except (ValueError, TypeError) as e:
            return _to_json({"ok": False, "error": str(e)[:1].upper() + str(e)[1:]})
        lab = self._lab()
        self._lab_cancel = threading.Event()
        self._lab_busy = True

        def work():
            try:
                out = lab.research(agent, objective, real_proposer(agent), real_planner, origin="real",
                                   budget_usd=budget, cancel=self._lab_cancel,
                                   on_event=lambda e: self._emit("labProgress", _to_json(e)))
                self._emit("labFinished", _to_json({"ok": True, "run": out["run"], "research": {k: v for k, v in out.items() if k != "run"}}))
            except Exception as e:
                self._emit("labFinished", _to_json({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}))
            finally:
                self._lab_busy = False
        threading.Thread(target=work, daemon=True, name="lab-research").start()
        return _to_json({"ok": True, "started": True})

    def labCancel(self) -> None:
        ev = getattr(self, "_lab_cancel", None)
        if ev is not None:
            ev.set()

    # ── Biblioteca (core/library.py): conteudo estatico, sem rede ──
    def librarySearch(self, query: str, level: str, kind: str) -> str:
        from core import library
        return _to_json({"ok": True, "items": library.search(query, level, kind), "verified_on": library.VERIFIED_ON})

    # ── Modo Desenvolvedor, nivel 3 (core/dev_mode.py): Claude Code/Codex numa worktree ──
    def _dev(self):
        if getattr(self, "_dev_obj", None) is None:
            from core.dev_mode import DevMode
            self._dev_obj = DevMode()
        return self._dev_obj

    def _dev_emit(self, pid: str, status: str, message: str = "") -> None:
        self._emit("devChanged", _to_json({"id": pid, "status": status, "message": message}))

    def _dev_background(self, pid_hint: str, work) -> str:
        """Propor e verificar demoram minutos: rodam numa thread e avisam por devChanged."""
        def run():
            try:
                p = work(lambda m: self._dev_emit(pid_hint, "progress", m))
                self._dev_emit(p["id"], p["status"], p.get("summary", ""))
            except Exception as exc:
                self._dev_emit(pid_hint, "error", f"{type(exc).__name__}: {exc}")
        threading.Thread(target=run, daemon=True, name="dev-mode").start()
        return _to_json({"ok": True})

    def devPropose(self, request: str, tool: str) -> str:
        try:
            if not self._brain().harness.load()["dev"].get("code_changes"):
                return _to_json({"ok": False, "error": "Ligue 'Mudancas de codigo' no Harness > Desenvolvedor antes."})
        except Exception as exc:
            return _to_json({"ok": False, "error": str(exc)})
        return self._dev_background("", lambda say: self._dev().propose(request, tool, on_progress=say))

    def devCheck(self, pid: str) -> str:
        return self._dev_background(pid, lambda say: self._dev().check(pid, on_progress=say))

    def devList(self) -> str:
        return self._brain_call(lambda: {"items": self._dev().list()})

    def devDiff(self, pid: str) -> str:
        return self._brain_call(lambda: {"diff": self._dev().get(pid).get("diff", "")})

    def devAct(self, pid: str, action: str) -> str:
        """apply | undo | discard: acoes rapidas, com git local; cada uma so vale no estado certo."""
        actions = {"apply": self._dev().apply, "undo": self._dev().undo, "discard": self._dev().discard}
        if action not in actions:
            return _to_json({"ok": False, "error": "acao desconhecida"})
        out = self._brain_call(lambda: {"proposal": {k: v for k, v in actions[action](pid).items() if k != "diff"}})
        self._dev_emit(pid, "changed")
        return out

    def appearance(self) -> str:
        """Aparencia salva no Harness (cor, ambiente, movimento): lida ao abrir a janela."""
        try:
            return _to_json(self._brain().harness.load()["appearance"])
        except Exception:
            from core.harness import DEFAULT
            return _to_json(DEFAULT["appearance"])

    # ── Criador (etapa 5) e sugestoes (etapa 6): tudo passa pela sua aprovacao ──
    def _creator(self):
        if getattr(self, "_creator_obj", None) is None:
            from core.creator import Creator
            self._creator_obj = Creator(self._brain())
        return self._creator_obj

    def creatorPropose(self, text: str) -> None:
        """Chama o modelo fora da thread da interface; a proposta chega por creatorReady."""
        import threading

        def run():
            self._emit("creatorReady", self._brain_call(lambda: {"proposal": self._creator().propose(text)}))
        threading.Thread(target=run, daemon=True, name="creator").start()

    def creatorApply(self, pid: str) -> str:
        def run():
            try:
                return self._creator().apply(pid)
            except KeyError:
                raise ValueError("a proposta expirou ou já foi aplicada; peça de novo")
        return self._brain_call(run)

    def creatorDiscard(self, pid: str) -> None:
        try:
            self._creator().discard(pid)
        except Exception:
            pass

    def suggestionsList(self) -> str:
        return self._brain_call(lambda: {"items": self._brain().suggestions.pending()})

    def suggestionApprove(self, sid: str, title: str, body: str) -> str:
        def run():
            try:
                return self._brain().suggestions.approve(sid, self._brain().store, title, body)
            except KeyError:
                raise FileNotFoundError(sid)
        return self._brain_call(run)

    def suggestionDismiss(self, sid: str) -> str:
        def run():
            try:
                return self._brain().suggestions.dismiss(sid)
            except KeyError:
                raise FileNotFoundError(sid)
        return self._brain_call(run)

    # ── Introducoes das telas (Cerebro, Voce, Harness): "Entendi" guarda ──
    def _intro_file(self):
        p = self._brain().store.personal
        return p / ".cerebro" / "interface.json" if p else None

    def introSeen(self) -> str:
        try:
            f = self._intro_file()
            return f.read_text(encoding="utf-8") if f and f.is_file() else "{}"
        except Exception:
            return "{}"

    def setIntroSeen(self, key: str, seen: bool) -> None:
        if key not in ("brain", "you", "harness", "diary", "library", "lab"):
            return
        try:
            f = self._intro_file()
            if not f:
                return
            data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
            if not isinstance(data, dict):
                data = {}
            data[key] = bool(seen)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    # ── Perfil de cada agente para o Harness ─────────────────────
    def agentProfile(self, agent: str) -> str:
        """Como o agente esta programado hoje: papel, regras do cerebro e skills."""
        def run():
            from core.brain import AGENT_FOLDERS
            from core.harness import AGENT_INFO
            from core.skills import SkillBook
            a = (agent or "").upper()
            if a not in AGENT_INFO:
                raise ValueError("agente desconhecido")
            b = self._brain()
            folder, name = AGENT_FOLDERS[a]
            rel = f"{folder}/{name}.md"
            skills = [{"name": s.name, "purpose": s.purpose} for s in SkillBook(b).all() if a in s.agents][:8]
            from core.action_policy import TOOLS
            from core import action_risk
            info = dict(AGENT_INFO[a])
            if action_risk.mode() != "enforce":      # sem a trava ligada, a ficha nao promete confirmacao
                info["limits"] = [l for l in info.get("limits", []) if "confirma" not in l.lower()]
            return {**info, "agent": a, "rules": b.agent_notes(a), "tools": sorted(TOOLS.get(a, set())),
                    "note": rel if b.store.resolve(rel) else "", "skills": skills}
        return self._brain_call(run)

    def openBrainFolder(self) -> None:
        """Abre a pasta do cerebro pessoal no Explorer (cria se ainda nao existir)."""
        try:
            import os
            p = self._brain().store.personal
            if p:
                p.mkdir(parents=True, exist_ok=True)
                os.startfile(str(p))
        except Exception:
            pass

    def _wire_bus(self) -> None:
        m = {
            "phase":              self._on_phase,
            "plan_ready":         lambda p: self._emit("planReady", _to_json(p)),
            "step_start":         lambda p: self._emit("stepStart", _to_json(p)),
            "step_done":          lambda p: self._emit("stepDone", _to_json(p)),
            "api_usage":          lambda p: self._emit("apiUsage", _to_json(p)),
            "context_extracted":  lambda p: self._emit("contextExtracted", _to_json(p)),
            "task_done":          self._on_task_done,
            "execution_finished": self._on_execution_finished,
            "report_ready":       lambda p: self._emit("reportReady", _to_json(p)),
            "cancelled":          self._on_cancelled,
            "error":              self._on_error,
            "log":                lambda p: self._emit("logEntry", _to_json(p)),
            "history_changed":    lambda p: self._emit("historyChanged", _to_json(p)),
            "resolved":           lambda p: self._emit("resolved", _to_json(p)),
            "answer":             self._on_answer,
            "session_reset":      lambda p: self._emit("sessionReset", _to_json(p)),
            "voice_state":        lambda p: self._emit("voiceState", _to_json(p)),
            "voice_level":        lambda p: self._emit("voiceLevel", _to_json(p)),
            "voice_heard":        lambda p: self._emit("voiceHeard", _to_json(p)),
            "voice_command":      lambda p: self._emit("voiceCommand", _to_json(p)),
            "voice_reply":        lambda p: self._emit("voiceReply", _to_json(p)),
            "voice_chat":         lambda p: self._emit("voiceChat", _to_json(p)),
            "plan_review":        lambda p: self._emit("planReview", _to_json(p)),
            "assistant_message":  lambda p: self._emit("assistantMessage", _to_json(p)),
            "conversations_changed": lambda p: self._emit("conversationsChanged", _to_json(p)),
        }
        for ev, cb in m.items():
            bus.on(ev, cb)

    def _on_phase(self, payload: dict) -> None:
        self._emit("phaseChanged", _to_json(payload))
        # quando entra em fase "maestro" pela primeira vez, running=True
        if not self._running:
            self._running = True
            self._emit("runningChanged", True)

    def _on_task_done(self, payload: dict) -> None:
        self._emit("taskDone", _to_json(payload))

    def _on_execution_finished(self, payload: dict) -> None:
        self._emit("executionFinished", _to_json(payload))
        if self._running:
            self._running = False
            self._emit("runningChanged", False)

    def _on_answer(self, payload: dict) -> None:
        self._emit("answerReady", _to_json(payload))

    def _on_cancelled(self, payload: dict) -> None:
        self._emit("cancelled", _to_json(payload))

    def _on_error(self, payload: dict) -> None:
        self._emit("errorRaised", _to_json(payload))
        if not self._controller.state.get("running"):
            self._on_execution_finished({"success": False, "status": "rejected"})

    def executeTask(self, task: str, dry_run: bool, generate_report: bool) -> None:
        self._controller.execute_task(task, dry_run=dry_run,
                                      generate_report=generate_report)

    def _voice_ctl(self):
        if self._voice is None:
            from core.config import get_config
            from desktop.voice import VoiceController
            vcfg = dict(get_config().get("voice", {}) or {})
            try:
                from core.user_settings import load
                mine = load()
                vcfg["barge_in"], vcfg["earcon"] = mine["barge_in"], mine["earcon"]
                vcfg["live_conversation"] = mine["live_conversation"]
            except Exception:
                pass
            self._voice = VoiceController(self._controller, vcfg)
        return self._voice

    def voiceRecordToggle(self) -> None:
        """Microfone: 1o clique grava, 2o envia (como mensagem de audio)."""
        self._voice_ctl().record_toggle()

    def voiceRecordCancel(self) -> None:
        self._voice_ctl().record_cancel()

    def setLiveConversation(self, on: bool) -> None:
        """Conversa ao vivo: microfone aberto, cada fala vira pedido e executa em fila."""
        self._voice_ctl().set_live(on)

    def newSession(self) -> None:
        self._controller.new_session()

    def forceStop(self) -> None:
        self._controller.force_stop()

    def loadConversations(self) -> str:
        """Conversas salvas (mais recente primeiro) para a barra lateral."""
        return _to_json({"items": self._controller.list_conversations(),
                         "current": self._controller.session.id})

    def openConversation(self, sid: str) -> str:
        """Retoma uma conversa: devolve os pedidos/respostas para a tela."""
        data = self._controller.open_conversation(sid)
        return _to_json(data or {})

    def loadHistory(self) -> str:
        """Retorna JSON com lista de execucoes + stats agregados."""
        return _to_json({
            "items": history_store.list_all(limit=200),
            "stats": history_store.stats(),
        })
