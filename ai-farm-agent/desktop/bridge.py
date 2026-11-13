"""
Bridge — QObject expondo o Controller para o QML.

QML nao consegue chamar diretamente um EventBus Python. A `Bridge` traduz:

    EventBus.emit(name, payload)        →  Bridge.<signal>(payload_json_str)
    QML.executeTask(text, dry, report)  →  Controller.execute_task(...)

Cada signal e emitido com payload JSON string (mais simples de consumir
em QML que QVariantMap, e funciona com PySide6 sem ginastica de tipos).

A logica fica em desktop/bridge_core.py (sem Qt), compartilhada com a interface Tauri
(desktop/server.py). Aqui ficam so os Signals, os @Slots que o QML chama (cada um repassa
para o BridgeCore) e o que depende de janela Qt: mini chat, barra de titulo e cursor.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from desktop.bridge_core import BridgeCore, _to_json  # noqa: F401  (_to_json: compatibilidade)

class Bridge(QObject, BridgeCore):
    """Objeto exposto ao QML como `Bridge` via context property."""

    # ── sinais 1-pra-1 com os eventos do EventBus ────────────────────
    phaseChanged       = Signal(str)
    planReady          = Signal(str)
    stepStart          = Signal(str)
    stepDone           = Signal(str)
    apiUsage           = Signal(str)
    contextExtracted   = Signal(str)
    taskDone           = Signal(str)
    executionFinished  = Signal(str)
    reportReady        = Signal(str)
    cancelled          = Signal(str)
    errorRaised        = Signal(str)
    logEntry           = Signal(str)
    historyChanged     = Signal(str)
    # Conversa: como a fala foi entendida, resposta sem acao, nova conversa
    resolved           = Signal(str)
    answerReady        = Signal(str)
    sessionReset       = Signal(str)
    # Modo voz
    voiceState         = Signal(str)
    voiceLevel         = Signal(str)
    voiceHeard         = Signal(str)
    voiceCommand       = Signal(str)
    voiceReply         = Signal(str)
    voiceChat          = Signal(str)
    # Plano esperando aprovacao (Configuracoes > revisar plano) e acesso rapido (Alt+Espaco)
    planReview         = Signal(str)
    quickEntry         = Signal()
    _quickEntryHotkey  = Signal()     # thread do atalho -> thread da interface
    # Conversa: resposta do assistente ao fim de cada pedido; lista de conversas mudou
    assistantMessage   = Signal(str)
    conversationsChanged = Signal(str)
    # Criador (Harness por linguagem natural): proposta pronta para revisar
    creatorReady       = Signal(str)
    devChanged         = Signal(str)
    codingStatus       = Signal(str)   # Configuracoes > Agentes de codigo: CLIs, sessao e MCP
    labProgress        = Signal(str)   # AI Research Lab: um caso terminou ({version, case, status, spent})
    journalSummary     = Signal(str)   # Diario: resumo por IA pronto ({ok, entry} ou {ok: false, error})
    labFinished        = Signal(str)   # AI Research Lab: experimento terminou ({ok, run} ou {ok: false, error})
    # Estado de running (UI bloqueia botao executar)
    runningChanged     = Signal(bool)

    # Nome usado pelo BridgeCore._emit -> Signal Qt (todos iguais, exceto os tratados em _emit)
    _QT_ONLY_EVENTS = frozenset({"windowRequest"})

    def __init__(self) -> None:
        QObject.__init__(self)
        self._window_mode = None
        self.runningChanged.connect(self._on_running_changed)
        self._quickEntryHotkey.connect(self._on_quick_entry)
        self._setup_core()

    def _emit(self, name: str, payload: Any = None) -> None:
        """BridgeCore -> Signal. Pode vir de qualquer thread: o Qt entrega na thread da interface."""
        if name == "quickEntry":
            self._quickEntryHotkey.emit()      # thread do atalho -> thread da interface
            return
        if name in self._QT_ONLY_EVENTS:
            return
        signal = getattr(self, name, None)
        if signal is None:
            return
        signal.emit(payload)

    # ── Interface: abertura, mini chat e atalho de parar ─────────────

    @Slot()
    def _on_quick_entry(self) -> None:
        if self._window_mode:
            self._window_mode.quick_entry()
        self.quickEntry.emit()

    def attach_windows(self, main_window, mini_window) -> None:
        """Chamado pelo main.py depois de carregar o QML."""
        from desktop.window_mode import WindowMode
        cfg = self._ui_cfg()
        self._window_mode = WindowMode(
            main_window, mini_window,
            enabled=cfg.get("mini_chat", True) is not False,
            hide_from_capture=bool(cfg.get("mini_hide_from_capture", False)))

    @Slot(bool)
    def _on_running_changed(self, running: bool) -> None:
        if self._window_mode:
            self._window_mode.set_running(running)

    @Slot()
    def restoreMain(self) -> None:
        if self._window_mode:
            self._window_mode.restore()

    @Slot()
    def closeMini(self) -> None:
        if self._window_mode:
            self._window_mode.close_mini()

    @Slot()
    def mainActivated(self) -> None:
        if self._window_mode:
            self._window_mode.main_activated()

    @Slot(result="QVariantList")
    def cursorPos(self) -> list:
        """Posicao global do cursor (orbe do mini chat: abrir o trajeto com o cursor em cima sem a janela
        receber eventos de mouse durante a tarefa)."""
        from PySide6.QtGui import QCursor
        p = QCursor.pos()
        return [p.x(), p.y()]

    def set_title_window(self, window) -> None:
        self._title_window = window
        self._apply_title()

    @Slot(str)
    def setTitleBarColor(self, color: str) -> None:
        self._title_color = color
        self._apply_title()

    def _apply_title(self) -> None:
        window = getattr(self, "_title_window", None)
        if window is not None:
            from desktop.titlebar import style_title_bar
            style_title_bar(window, getattr(self, "_title_color", "") or "#FBF7F4")

    @Slot(str, result=str)
    def wallpaperImport(self, url: str) -> str:
        from PySide6.QtCore import QUrl
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        return BridgeCore.wallpaperImport(self, path)

    # ── Slots chamados pelo QML: cada um repassa para o BridgeCore ───

    @Slot(result=str)
    def getSettings(self) -> str:
        return BridgeCore.getSettings(self)

    @Slot(str, result=str)
    def saveSettings(self, payload: str) -> str:
        return BridgeCore.saveSettings(self, payload)

    @Slot(str, str, result=bool)
    def renameConversation(self, sid: str, title: str) -> bool:
        return BridgeCore.renameConversation(self, sid, title)

    @Slot(str, result=bool)
    def deleteConversation(self, sid: str) -> bool:
        return BridgeCore.deleteConversation(self, sid)

    @Slot(str, result=str)
    def attachFiles(self, payload: str) -> str:
        return BridgeCore.attachFiles(self, payload)

    @Slot(bool, str)
    def approvePlan(self, ok: bool, token: str) -> None:
        BridgeCore.approvePlan(self, ok, token)

    @Slot(str, str)
    def approvePlanSteps(self, token: str, skipped_json: str) -> None:
        BridgeCore.approvePlanSteps(self, token, skipped_json)

    @Slot(result=str)
    def uiSettings(self) -> str:
        return BridgeCore.uiSettings(self)

    @Slot(result=str)
    def brainOverview(self) -> str:
        return BridgeCore.brainOverview(self)

    @Slot(str, result=str)
    def brainRead(self, rel: str) -> str:
        return BridgeCore.brainRead(self, rel)

    @Slot(str, str, result=str)
    def brainSave(self, rel: str, text: str) -> str:
        return BridgeCore.brainSave(self, rel, text)

    @Slot(str, str, result=str)
    def brainCreate(self, rel: str, text: str) -> str:
        return BridgeCore.brainCreate(self, rel, text)

    @Slot(str, result=str)
    def brainCreateFolder(self, rel: str) -> str:
        return BridgeCore.brainCreateFolder(self, rel)

    @Slot(str, str, result=str)
    def brainRename(self, old: str, new: str) -> str:
        return BridgeCore.brainRename(self, old, new)

    @Slot(str, result=str)
    def brainDelete(self, rel: str) -> str:
        return BridgeCore.brainDelete(self, rel)

    @Slot(str, result=str)
    def brainRestore(self, rel: str) -> str:
        return BridgeCore.brainRestore(self, rel)

    @Slot(str, result=str)
    def brainSearch(self, query: str) -> str:
        return BridgeCore.brainSearch(self, query)

    @Slot(result=str)
    def brainGraph(self) -> str:
        return BridgeCore.brainGraph(self)

    @Slot(result=str)
    def youProfile(self) -> str:
        return BridgeCore.youProfile(self)

    @Slot(str, str, result=str)
    def youSave(self, section: str, text: str) -> str:
        return BridgeCore.youSave(self, section, text)

    @Slot(result=str)
    def harnessGet(self) -> str:
        return BridgeCore.harnessGet(self)

    @Slot(str, str, result=str)
    def harnessSave(self, payload: str, label: str) -> str:
        return BridgeCore.harnessSave(self, payload, label)

    @Slot(str, result=str)
    def harnessRestore(self, version_id: str) -> str:
        return BridgeCore.harnessRestore(self, version_id)

    @Slot(result=str)
    def activitySummary(self) -> str:
        return BridgeCore.activitySummary(self)

    @Slot()
    def codingAgentsCheck(self) -> None:
        BridgeCore.codingAgentsCheck(self)

    @Slot(result=str)
    def wallpapersList(self) -> str:
        return BridgeCore.wallpapersList(self)

    @Slot(str, result=str)
    def wallpaperInfo(self, wallpaper: str) -> str:
        return BridgeCore.wallpaperInfo(self, wallpaper)

    @Slot(str, result=str)
    def wallpaperRemove(self, wallpaper: str) -> str:
        return BridgeCore.wallpaperRemove(self, wallpaper)

    @Slot(str, str, str, result=str)
    def journalList(self, query: str, tag: str, day: str) -> str:
        return BridgeCore.journalList(self, query, tag, day)

    @Slot(result=str)
    def journalFolders(self) -> str:
        return BridgeCore.journalFolders(self)

    @Slot(str, str, str, str, result=str)
    def journalListIn(self, folder: str, query: str, tag: str, day: str) -> str:
        return BridgeCore.journalListIn(self, folder, query, tag, day)

    @Slot(str, result=str)
    def journalGet(self, entry_id: str) -> str:
        return BridgeCore.journalGet(self, entry_id)

    @Slot(str, result=str)
    def journalSave(self, payload: str) -> str:
        return BridgeCore.journalSave(self, payload)

    @Slot(str, bool, result=str)
    def journalSetPrivate(self, entry_id: str, private: bool) -> str:
        return BridgeCore.journalSetPrivate(self, entry_id, private)

    @Slot(str, result=str)
    def journalDelete(self, entry_id: str) -> str:
        return BridgeCore.journalDelete(self, entry_id)

    @Slot(result=str)
    def journalDates(self) -> str:
        return BridgeCore.journalDates(self)

    @Slot(str)
    def journalSummarize(self, entry_id: str) -> None:
        BridgeCore.journalSummarize(self, entry_id)

    @Slot(bool, result=str)
    def journalUseInBrain(self, on: bool) -> str:
        return BridgeCore.journalUseInBrain(self, on)

    @Slot(result=str)
    def providerStatus(self) -> str:
        return BridgeCore.providerStatus(self)

    @Slot(str, result=str)
    def historyDetail(self, task_id: str) -> str:
        return BridgeCore.historyDetail(self, task_id)

    @Slot(str, result=str)
    def labVersions(self, agent: str) -> str:
        return BridgeCore.labVersions(self, agent)

    @Slot(str, result=str)
    def labCreateVariant(self, payload: str) -> str:
        return BridgeCore.labCreateVariant(self, payload)

    @Slot(str, str, result=str)
    def labDiff(self, a: str, b: str) -> str:
        return BridgeCore.labDiff(self, a, b)

    @Slot(str, result=str)
    def labPublish(self, version_id: str) -> str:
        return BridgeCore.labPublish(self, version_id)

    @Slot(result=str)
    def labEvalSets(self) -> str:
        return BridgeCore.labEvalSets(self)

    @Slot(result=str)
    def labRuns(self) -> str:
        return BridgeCore.labRuns(self)

    @Slot(str, result=str)
    def labRunDetail(self, run_id: str) -> str:
        return BridgeCore.labRunDetail(self, run_id)

    @Slot(str, result=str)
    def labSkills(self, agent: str) -> str:
        return BridgeCore.labSkills(self, agent)

    @Slot(str, str, result=str)
    def labToolTest(self, name: str, args_json: str) -> str:
        return BridgeCore.labToolTest(self, name, args_json)

    @Slot(str, str, result=str)
    def labObserve(self, agent: str, state: str) -> str:
        return BridgeCore.labObserve(self, agent, state)

    @Slot(str, result=str)
    def labRun(self, payload: str) -> str:
        return BridgeCore.labRun(self, payload)

    @Slot(str, result=str)
    def labFeedback(self, payload: str) -> str:
        return BridgeCore.labFeedback(self, payload)

    @Slot(str, result=str)
    def labPromotionCheck(self, version_id: str) -> str:
        return BridgeCore.labPromotionCheck(self, version_id)

    @Slot(str, result=str)
    def labPromote(self, version_id: str) -> str:
        return BridgeCore.labPromote(self, version_id)

    @Slot(result=str)
    def labTraining(self) -> str:
        return BridgeCore.labTraining(self)

    @Slot(str, result=str)
    def labResearch(self, payload: str) -> str:
        return BridgeCore.labResearch(self, payload)

    @Slot()
    def labCancel(self) -> None:
        BridgeCore.labCancel(self)

    @Slot(str, str, str, result=str)
    def librarySearch(self, query: str, level: str, kind: str) -> str:
        return BridgeCore.librarySearch(self, query, level, kind)

    @Slot(str, str, result=str)
    def devPropose(self, request: str, tool: str) -> str:
        return BridgeCore.devPropose(self, request, tool)

    @Slot(str, result=str)
    def devCheck(self, pid: str) -> str:
        return BridgeCore.devCheck(self, pid)

    @Slot(result=str)
    def devList(self) -> str:
        return BridgeCore.devList(self)

    @Slot(str, result=str)
    def devDiff(self, pid: str) -> str:
        return BridgeCore.devDiff(self, pid)

    @Slot(str, str, result=str)
    def devAct(self, pid: str, action: str) -> str:
        return BridgeCore.devAct(self, pid, action)

    @Slot(result=str)
    def appearance(self) -> str:
        return BridgeCore.appearance(self)

    @Slot(str)
    def creatorPropose(self, text: str) -> None:
        BridgeCore.creatorPropose(self, text)

    @Slot(str, result=str)
    def creatorApply(self, pid: str) -> str:
        return BridgeCore.creatorApply(self, pid)

    @Slot(str)
    def creatorDiscard(self, pid: str) -> None:
        BridgeCore.creatorDiscard(self, pid)

    @Slot(result=str)
    def suggestionsList(self) -> str:
        return BridgeCore.suggestionsList(self)

    @Slot(str, str, str, result=str)
    def suggestionApprove(self, sid: str, title: str, body: str) -> str:
        return BridgeCore.suggestionApprove(self, sid, title, body)

    @Slot(str, result=str)
    def suggestionDismiss(self, sid: str) -> str:
        return BridgeCore.suggestionDismiss(self, sid)

    @Slot(result=str)
    def introSeen(self) -> str:
        return BridgeCore.introSeen(self)

    @Slot(str, bool)
    def setIntroSeen(self, key: str, seen: bool) -> None:
        BridgeCore.setIntroSeen(self, key, seen)

    @Slot(str, result=str)
    def agentProfile(self, agent: str) -> str:
        return BridgeCore.agentProfile(self, agent)

    @Slot()
    def openBrainFolder(self) -> None:
        BridgeCore.openBrainFolder(self)

    @Slot(str, bool, bool)
    def executeTask(self, task: str, dry_run: bool, generate_report: bool) -> None:
        BridgeCore.executeTask(self, task, dry_run, generate_report)

    @Slot()
    def voiceRecordToggle(self) -> None:
        BridgeCore.voiceRecordToggle(self)

    @Slot()
    def voiceRecordCancel(self) -> None:
        BridgeCore.voiceRecordCancel(self)

    @Slot(bool)
    def setLiveConversation(self, on: bool) -> None:
        BridgeCore.setLiveConversation(self, on)

    @Slot()
    def newSession(self) -> None:
        BridgeCore.newSession(self)

    @Slot()
    def forceStop(self) -> None:
        BridgeCore.forceStop(self)

    @Slot(result=str)
    def loadConversations(self) -> str:
        return BridgeCore.loadConversations(self)

    @Slot(str, result=str)
    def openConversation(self, sid: str) -> str:
        return BridgeCore.openConversation(self, sid)

    @Slot(result=str)
    def loadHistory(self) -> str:
        return BridgeCore.loadHistory(self)
