"""
BridgeCore — a logica da interface, sem Qt.

Tudo o que a tela pede ao nucleo passa por aqui: execucao, conversas, voz, Segundo Cerebro, Diario,
Harness, Lab, modo Desenvolvedor. Duas cascas usam a mesma classe:

    desktop/bridge.py   Bridge(QObject, BridgeCore)  -> Signals Qt e metodos de janela
    desktop/server.py   Dispatcher                   -> WebSocket JSON-RPC (interface React)

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

    # ── Janela: sem Qt (testes) nao ha janela; o Bridge Qt sobrescreve com as janelas de verdade ─────────
    def restoreMain(self) -> None:
        """Sem Qt nao ha janela principal para trazer de volta."""

    def closeMini(self) -> None:
        """Sem Qt nao ha mini chat."""

    def mainActivated(self) -> None:
        """Sem Qt nao ha mini chat para fechar."""

    def setTitleBarColor(self, color: str) -> None:
        """Sem Qt nao ha barra de titulo nativa."""

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
        # So leitura: a tela mostra se efeitos sensiveis pedem aprovacao (config.yaml > execution.authorization)
        from core.action_risk import mode as authorization_mode
        data["authorization"] = authorization_mode()
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

    def harnessPatch(self, payload: str, label: str) -> str:
        return self._brain_call(lambda: {"harness": self._brain().harness.patch(json.loads(payload), label)})

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
        ], **self._model_catalog()})

    # ── Modelos e provedores (Configuracoes > Modelos) ─────────────────
    @staticmethod
    def _model_catalog() -> dict:
        """Provedores que o app sabe chamar, se estao prontos (nunca a chave) e o modelo de cada nivel."""
        from core import provider_registry as R, secret_store
        from core.config import get_config
        from core.user_settings import MODEL_TIERS, load
        chosen = load().get("models", {})
        catalog = []
        for p in R.providers().values():
            try:
                stored = secret_store.has(p.name)
            except secret_store.SecretStoreError:
                stored = False
            catalog.append({"name": p.name, "label": p.label, "local": p.local, "needs_key": p.needs_key,
                            "configured": R.configured(p), "stored": stored, "signup": p.signup,
                            "example": (f"{p.name}:{p.example}" if p.name != "anthropic" else p.example)
                            if p.example else "",
                            "key_env": p.key_env, "env_detected": bool(p.key_env and os.getenv(p.key_env, "").strip()),
                            "custom": p.name not in R.PRESETS, "base_url": p.base_url if p.name not in R.PRESETS else "",
                            "images": p.capabilities.images, "tools": p.capabilities.tools,
                            "web_search": p.capabilities.server_tools})
        models = {tier: {"chosen": chosen.get(tier, ""), "default": str(get_config().get(f"models.{tier}", ""))}
                  for tier in MODEL_TIERS}
        return {"catalog": catalog, "models": models, "can_store": secret_store.available()}

    def providerKeySave(self, name: str, key: str) -> str:
        """Guarda a chave do provedor protegida pelo Windows (DPAPI). A resposta nunca repete a chave."""
        from core import provider_registry as R, secret_store
        provider = R.providers().get(name or "")
        if provider is None or (not provider.needs_key and provider.kind != "anthropic"):
            return _to_json({"ok": False, "error": "Esse provedor não usa chave."})
        try:
            secret_store.save(provider.name, key)
        except secret_store.SecretStoreError as e:
            return _to_json({"ok": False, "error": str(e)})
        return _to_json({"ok": True, **self._model_catalog()})

    def providerCustomSave(self, payload: str) -> str:
        """Cria/atualiza um provedor compatível com OpenAI pela tela; a chave (opcional) vai para o DPAPI."""
        from core import secret_store
        from core.user_settings import save
        try:
            d = json.loads(payload or "{}")
            name = str(d.get("name") or "").strip().lower()
            row = {"label": d.get("label") or name, "base_url": d.get("base_url"), "images": d.get("images") is True,
                   "structured": d.get("structured") is True, "tools": d.get("tools", True) is not False,
                   "example": d.get("example") or ""}
            save({"custom_providers": {name: row}})
            key = str(d.get("key") or "").strip()
            if key:
                secret_store.save(name, key)
        except (ValueError, secret_store.SecretStoreError) as e:
            return _to_json({"ok": False, "error": str(e)[:1].upper() + str(e)[1:]})
        return _to_json({"ok": True, **self._model_catalog()})

    def providerCustomRemove(self, name: str) -> str:
        from core import provider_registry as R, secret_store
        from core.user_settings import save
        if (name or "") in R.PRESETS:
            return _to_json({"ok": False, "error": "Provedores prontos não podem ser removidos."})
        try:
            save({"custom_providers": {name: None}})
            secret_store.delete(name)
        except (ValueError, secret_store.SecretStoreError) as e:
            return _to_json({"ok": False, "error": str(e)})
        return _to_json({"ok": True, **self._model_catalog()})

    def providerKeyRemove(self, name: str) -> str:
        from core import provider_registry as R, secret_store
        if (name or "") not in R.providers():
            return _to_json({"ok": False, "error": "Provedor desconhecido."})
        try:
            secret_store.delete(name)
        except secret_store.SecretStoreError as e:
            return _to_json({"ok": False, "error": str(e)})
        return _to_json({"ok": True, **self._model_catalog()})

    def providerModels(self, name: str) -> str:
        """Testa a conexão (GET /models, sem gerar texto) e lista os modelos para escolher."""
        from core import provider_registry as R
        from core.egress import EgressDenied, require_online
        from core.model_provider import OpenAICompatProvider, ProviderError
        provider = R.providers().get(name or "")
        if provider is None:
            return _to_json({"ok": False, "error": "Provedor desconhecido."})
        if provider.kind == "anthropic":
            return _to_json({"ok": R.configured(provider), "models": [], "error": "" if R.configured(provider)
                             else "Falta a chave da Anthropic.", "hint": "Use nomes como claude-sonnet-5."})
        try:
            if not provider.local:
                require_online(provider.label)
            key = R.api_key(provider)
            if provider.needs_key and not key:
                return _to_json({"ok": False, "error": f"Adicione a chave de {provider.label} primeiro."})
            base = provider.base_url + ("/v1" if provider.kind == "ollama" else "")
            models = OpenAICompatProvider().list_models(base_url=base, api_key=key, timeout=10)
        except (ProviderError, EgressDenied) as e:
            return _to_json({"ok": False, "error": str(e)})
        return _to_json({"ok": True, "models": [f"{provider.name}:{m}" for m in models]})

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
    LAB_BUDGET_MAX = 5.0          # maior limite de custo estimado que a pessoa pode indicar
    _lab_jobs_lock = threading.Lock()

    def _lab(self):
        from core.lab import get_lab
        return get_lab(self._brain().store.personal)

    def labVersions(self, agent: str) -> str:
        from core.lab import effective_config, v_safe_id
        def run():
            lab = self._lab()
            rows = lab.versions(agent, self._brain().harness)
            active = next(row for row in rows if row["published"])
            rollback = bool(lab._read(f"promotions/{v_safe_id(active['id'])}.json", None))
            tested = {version for entry in lab.runs() for version, stats in (entry.get("summary") or {}).items()
                      if stats.get("success_rate") is not None}
            return {"versions": [{**row, "tested": row["id"] in tested} for row in rows], "rollback_available": rollback,
                    "effective": {v["id"]: effective_config(agent, v) for v in rows}}
        return self._brain_call(run)

    def labArchive(self, version_id: str, archived: bool) -> str:
        return self._brain_call(lambda: {"version": self._lab().archive(version_id, archived, self._brain().harness)})

    def labCreateVariant(self, payload: str) -> str:
        def run():
            d = json.loads(payload or "{}")
            return {"version": self._lab().create_variant(str(d.get("agent", "")), str(d.get("base", "")),
                                                          str(d.get("instructions", "")), d.get("params") or {},
                                                          str(d.get("note", "")))}
        return self._brain_call(run)

    def labDiff(self, a: str, b: str) -> str:
        return self._brain_call(lambda: {"lines": self._lab().diff(a, b)})

    def labDraftRoute(self, payload: str) -> str:
        from core.lab_drafts import draft_route
        return self._brain_call(lambda: draft_route(self._brain().store, json.loads(payload)))

    def labPublish(self, version_id: str) -> str:
        return self.labPromote(version_id)

    def labEvalSets(self) -> str:
        def run():
            from core.lab import _fingerprint
            lab = self._lab()
            return {"sets": [{**row, "hash": _fingerprint(row)} for row in lab.eval_sets()]}
        return self._brain_call(run)

    def labDataset(self, payload: str) -> str:
        def run():
            from core.lab import _fingerprint
            data = json.loads(payload)
            lab = self._lab()
            name = data["name"]
            if data.get("action") == "validate":
                from core.lab_cases import validate_cases
                validate_cases(data["cases"], data["agent"])
                return {}
            if data.get("action") == "save":
                row = lab.save_eval_set(name, data["cases"], data["agent"], data.get("title", ""), data.get("expected", ""))
            elif data.get("action") == "read":
                row = lab.eval_set(name, data.get("revision", ""))
            else:
                raise ValueError("operação de conjunto inválida")
            return {"set": {**row, "hash": _fingerprint(row)}, "revisions": lab.dataset_revisions(name)}
        return self._brain_call(run)

    def labReport(self, run_id: str, format: str, hypothesis: str) -> str:
        from core.lab_report import report
        return self._brain_call(lambda: {"content": report(self._lab().run_detail(run_id), format, hypothesis)})

    def labRollback(self, agent: str, active: str, confirmed: bool) -> str:
        if not confirmed:
            return _to_json({"ok": False, "error": "Confirme a restauração da versão anterior."})
        return self._brain_call(lambda: {"version": self._lab().rollback(agent, self._brain().harness, active)})

    def labRuns(self) -> str:
        return self._brain_call(lambda: {"runs": self._lab().runs(), "busy": bool(getattr(self, "_lab_busy", False))})

    def labRunDetail(self, run_id: str) -> str:
        def run():
            from core.task_ledger import TaskLedger
            lab = self._lab()
            detail = lab.run_detail(run_id)
            task_id = detail.get("task_id")
            events = TaskLedger(lab.folder / "events").events(task_id) if task_id == f"lab-{run_id}" else []
            return {"run": {**detail, "events": events}}
        return self._brain_call(run)

    def labSkills(self, agent: str) -> str:
        from core.lab import skills_and_tools
        return self._brain_call(lambda: skills_and_tools(agent, self._brain()))

    def labToolTest(self, name: str, args_json: str) -> str:
        from core.lab import test_mcp_tool
        return self._brain_call(lambda: test_mcp_tool(name, json.loads(args_json or "{}")))

    def labObserve(self, agent: str, state: str) -> str:
        from core.lab import observe
        return self._brain_call(lambda: {"tasks": observe(agent, state)})

    def _start_lab_job(self, name, job) -> str:
        with self._lab_jobs_lock:
            if getattr(self, "_lab_busy", False):
                return _to_json({"ok": False, "error": "Já há um experimento rodando."})
            cancel = threading.Event()
            self._lab_cancel = cancel
            self._lab_busy = True

            def work():
                try:
                    reply = {"ok": True, **job(cancel)}
                except Exception as e:
                    reply = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
                with self._lab_jobs_lock:
                    self._lab_busy = False
                    self._emit("labFinished", _to_json(reply))

            try:
                threading.Thread(target=work, daemon=True, name=name).start()
            except RuntimeError:
                self._lab_busy = False
                return _to_json({"ok": False, "error": "Não foi possível iniciar o experimento."})
        return _to_json({"ok": True, "started": True})

    def labRun(self, payload: str) -> str:
        """{"set", "versions": [ids], "mode": "simulado"|"real", "confirmed": bool, "budget": US$}.
        Real usa o provedor (custa): so com confirmacao explicita e orcamento ate LAB_BUDGET_MAX."""
        from core.lab import fixture_planner, real_planner, replay_planner
        from core.lab_budget import Budget, budget_scope
        try:
            d = json.loads(payload or "{}")
            mode = d.get("mode")
            if mode not in ("simulado", "real", "fixture"):
                raise ValueError("modo de avaliação inválido")
            versions = d.get("versions", [])
            if not isinstance(versions, list) or not 1 <= len(versions) <= 2 or any(not isinstance(v, str) for v in versions):
                raise ValueError("escolha até duas versões")
            strategies = d.get("runtime_strategies", {})
            if not isinstance(strategies, dict) or strategies.keys() - set(versions) or any(
                    strategy not in ("fixed", "adaptive") for strategy in strategies.values()):
                raise ValueError("estratégias de runtime inválidas")
            budget = self._lab_paid_budget(d) if mode == "real" else None
            seconds, calls, tokens = d.get("timeout", 180), d.get("calls", 40), d.get("tokens", 160000)
            for value, low, high in ((seconds, 15, 600), (calls, 1, 200), (tokens, 512, 1000000)):
                if type(value) is not int or not low <= value <= high:
                    raise ValueError("limites de tempo, chamadas ou tokens inválidos")
            lab = self._lab()
            dataset = lab.eval_set(str(d.get("set", "")), str(d.get("revision", "")))
            revision = lab._archive_dataset(dataset)
        except (ValueError, TypeError, AttributeError, FileNotFoundError) as exc:
            return _to_json({"ok": False, "error": str(exc)})

        protocol = {"objective": str(d.get("objective") or "")[:400], "hypothesis": str(d.get("hypothesis") or "")[:400],
                    "limits": {"usd": budget, "seconds": seconds, "calls": calls, "tokens": tokens},
                    "decision": "comparar pares válidos e sinalizar toda regressão de estado final"}

        def run(cancel):
            planner = real_planner if mode == "real" else fixture_planner if mode == "fixture" else replay_planner(lab, d.get("context", "fixture"))
            limits = Budget(budget, seconds, calls, tokens, cancel) if budget is not None else None
            with budget_scope(limits):
                result = lab.run(dataset["name"], versions, planner, origin=mode, cancel=cancel, revision=revision,
                                 split=d.get("split", "all"), repeats=d.get("repeats", 1), context_mode=d.get("context", "fixture"),
                                 protocol=protocol, on_event=lambda e: self._emit("labProgress", _to_json(e)), budget_usd=budget,
                                 runtime_strategies=strategies)
            return {"run": result}

        return self._start_lab_job("lab-run", run)

    def _lab_paid_budget(self, payload) -> float:
        budget = float(payload.get("budget") or 0)
        if payload.get("confirmed") is not True:
            raise ValueError("a chamada ao provedor precisa da sua confirmação")
        if not 0.01 <= budget <= self.LAB_BUDGET_MAX:
            raise ValueError(f"orçamento deve ficar entre US$ 0,01 e US$ {self.LAB_BUDGET_MAX:.2f}")
        return budget

    def labFeedback(self, payload: str) -> str:
        def run():
            d = json.loads(payload or "{}")
            return {"result": self._lab().add_feedback(str(d.get("run", "")), str(d.get("version", "")),
                                                       str(d.get("case", "")), str(d.get("note", "")), int(d.get("trial", 1)))}
        return self._brain_call(run)

    def labPromotionCheck(self, version_id: str) -> str:
        return self._brain_call(lambda: self._lab().promotion_check(version_id))

    def labPromote(self, version_id: str) -> str:
        return self._brain_call(lambda: {"version": self._lab().promote(version_id, self._brain().harness)})

    def labTraining(self) -> str:
        from core.lab import training_status
        return _to_json({"ok": True, **training_status()})

    def rsiHistory(self, agent: str) -> str:
        from core.rsi import ScientificMemory
        return self._brain_call(lambda: {"entries": ScientificMemory(self._lab()).search(agent=agent, limit=50)})

    def harnessPanorama(self) -> str:
        """Dados da cena 3D do harness (roteamento, planos aprendidos, hipoteses do Lab). So leitura."""
        from core.panorama import build
        from core.learned_plans import get_learned

        def run():
            warnings = []
            try:
                from core.rsi import ScientificMemory
                science = ScientificMemory(self._lab()).search(limit=40)
            except Exception:
                science = []
                warnings.append("Memória científica indisponível; a camada de evolução pode estar incompleta.")
            return {**build(history_store.list_all(limit=200), get_learned().entries(), science), "warnings": warnings}
        return self._brain_call(run)

    def rsiDecide(self, candidate: str, decision: str, confirmed: bool) -> str:
        from core.rsi import decide
        if confirmed is not True:
            return _to_json({"ok": False, "error": "Confirme a decisão desta candidata."})
        return self._brain_call(lambda: {"decision": decide(
            self._lab(), self._brain().harness, candidate, decision, "operador local")})

    def labResearch(self, payload: str) -> str:
        """Propõe uma hipótese isolada; a comparação é uma segunda ação do usuário."""
        from core.lab import research_proposal
        from core.lab_budget import Budget, budget_scope
        try:
            data = json.loads(payload)
            objective = str(data.get("objective") or "").strip()[:400]
            agent = str(data.get("agent") or "FILE").upper()
            lab = self._lab()
            dataset = lab.eval_set(data.get("set", ""), data.get("revision", ""))
            if not objective or dataset["agent"] != agent:
                raise ValueError("informe um objetivo e um conjunto do agente")
            paid = data.get("mode") == "real"
            budget = self._lab_paid_budget(data) if paid else None
            versions = lab.versions(agent, self._brain().harness)
            active = next(v for v in versions if v["published"])
        except (ValueError, TypeError, AttributeError, FileNotFoundError) as exc:
            return _to_json({"ok": False, "error": str(exc)})

        def run(cancel):
            limits = Budget(budget, 60, 1, 12000, cancel) if paid else None
            with budget_scope(limits):
                value = research_proposal(lab, active, dataset, objective, paid)
            return {"proposal": value}

        return self._start_lab_job("lab-research", run)

    def labCancel(self) -> None:
        ev = getattr(self, "_lab_cancel", None)
        if ev is not None:
            ev.set()

    # ── Biblioteca (core/library.py): conteudo estatico, sem rede ──
    def librarySearch(self, query: str, level: str, kind: str) -> str:
        from core import library
        return _to_json({"ok": True, "items": library.search(query, level, kind), "verified_on": library.VERIFIED_ON})

    def libraryCatalog(self, query: str, level: str, kind: str) -> str:
        """Grade da Biblioteca: fichas sem o corpo do artigo (o texto vem em libraryTopic)."""
        from core import library
        return _to_json({"ok": True, "items": library.catalog(query, level, kind), "verified_on": library.VERIFIED_ON})

    def libraryTopic(self, topic_id: str) -> str:
        from core import library
        t = library.topic(topic_id)
        if not t:
            return _to_json({"ok": False, "error": "Tema não encontrado."})
        return _to_json({"ok": True, "topic": t, "verified_on": library.VERIFIED_ON})

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
            from core.atomic_io import replace_file
            tmp = f.with_name(f"{f.name}.tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            replace_file(tmp, f)                     # nunca deixa o arquivo pela metade
        except Exception as exc:
            print(f"  [ui] introducao nao gravada: {type(exc).__name__}: {exc}")

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

    # ── Estudio de agentes (AI Research Lab, core/agent_studio.py) ──
    def studioAgent(self, agent: str) -> str:
        """Especificacao + memoria (nota do agente, notas ligadas, contexto extra) de um agente."""
        from core import agent_studio
        return self._brain_call(lambda: {"spec": agent_studio.spec(agent, self._brain()),
                                         "memory": agent_studio.memory(agent, self._brain())})

    def studioSource(self, agent: str, path: str) -> str:
        """Codigo de um arquivo do agente, so leitura (lista fechada em agent_studio.AGENT_FILES)."""
        from core import agent_studio
        return self._brain_call(lambda: {"file": agent_studio.source(agent, path)})

    def studioSave(self, agent: str, payload: str) -> str:
        """Grava memoria/contexto do agente na camada pessoal do Cerebro. Nunca muda ferramenta ou politica."""
        from core import agent_studio
        return self._brain_call(lambda: {"memory": agent_studio.save(agent, json.loads(payload or "{}"), self._brain())})

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
            "cognitive_activity": lambda p: self._emit("cognitiveActivity", _to_json(p)),
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
            "answer_delta":       lambda p: self._emit("answerDelta", _to_json(p)),
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

    def loadConversations(self, include_turns: bool = False) -> str:
        """Conversas salvas (mais recente primeiro) para a barra lateral."""
        session = self._controller.session
        data = {"items": self._controller.list_conversations(), "current": session.id}
        if include_turns:
            data["turns"] = session.to_dict()["turns"]
        return _to_json(data)

    def openConversation(self, sid: str) -> str:
        """Retoma uma conversa: devolve os pedidos/respostas para a tela."""
        data = self._controller.open_conversation(sid)
        return _to_json(data or {})

    def loadHistory(self) -> str:
        """Retorna JSON com lista de execucoes + stats agregados."""
        items = history_store.list_all(limit=None)          # uma leitura so do arquivo para lista e totais
        return _to_json({
            "items": items[:200],
            "stats": history_store.stats(items),
        })
