"""
Caixa de areia para carregar QML que ainda nao foi aprovado (gate do modo Desenvolvedor: smoke na worktree).

QML proposto roda o que quiser ao carregar (Component.onCompleted). Sem isolamento, ele podia chamar metodos
de escrita da Bridge, ler notas pessoais e manda-las pela rede, abrir programas ou gravar no disco.
Aqui, por padrao, nada sai:

1. Bridge somente leitura: so os slots de LEITURA listados abaixo funcionam; qualquer outro (inclusive os
   que ainda nao existem) devolve "somente leitura" e fica registrado em `attempts`.
2. Dados sinteticos: o Segundo Cerebro (notas, Diario, Harness) e o historico apontam para uma pasta
   temporaria com uma nota ficticia. Nenhum dado pessoal e lido.
3. Sem rede: toda requisicao do motor QML (XMLHttpRequest, Image remota, import remoto) que nao seja
   arquivo local e trocada por uma URL invalida e falha.
4. Sem abrir nada fora: Qt.openUrlExternally para os esquemas comuns cai num receptor que so registra.
5. Sem gravar arquivos: XMLHttpRequest para file:// desligado e o LocalStorage vai para a pasta temporaria.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

# Slots que so LEEM (o resto e negado). Abrir a janela principal precisa deles.
READ_SLOTS = frozenset({
    "activitySummary", "agentProfile", "appearance", "brainGraph", "brainOverview", "brainRead", "brainSearch",
    "cursorPos", "devList", "getSettings", "harnessGet", "introSeen", "journalGet", "journalList",
    "librarySearch", "loadConversations", "loadHistory", "suggestionsList", "uiSettings", "wallpaperInfo",
    "wallpapersList", "youProfile",
    "providerStatus", "journalDates", "journalFolders", "journalListIn",                            # so verdadeiro/falso por provedor, nunca a chave
    "labRuns", "labRunDetail", "labSkills",     # labObserve fica fora: le o registro real de tarefas
})
# Ajustes da propria janela que a tela principal pede ao abrir: negados tambem, mas sem reprovar o teste
QUIET_SLOTS = frozenset({"mainActivated", "setTitleBarColor"})
DENIED_JSON = '{"ok": false, "error": "Somente leitura: proposta em teste não grava nem executa nada."}'
_SCHEMES = ("http", "https", "file", "mailto", "ftp", "ms-settings", "shell", "tel", "callto", "steam",
            "vscode", "ms-word", "ms-excel", "search-ms", "microsoft-edge")


def lock_bridge(bridge_cls) -> list:
    """Troca, NA CLASSE, todo slot fora de READ_SLOTS por um que nega e registra. -> lista de tentativas."""
    from PySide6.QtCore import QMetaMethod
    attempts: list = []
    mo = bridge_cls.staticMetaObject
    for i in range(mo.methodOffset(), mo.methodCount()):
        m = mo.method(i)
        if m.methodType() != QMetaMethod.MethodType.Slot:
            continue
        name = bytes(m.name()).decode()
        if name in READ_SLOTS or name.startswith("_"):
            continue
        ret = m.typeName()
        ret = ret if isinstance(ret, str) else bytes(ret).decode()

        def denied(self, *args, _name=name, _ret=ret):
            if _name not in QUIET_SLOTS:
                attempts.append(_name)
            if _ret == "QString":
                return DENIED_JSON
            if _ret == "bool":
                return False
            if _ret in ("QVariantList", "QStringList"):
                return []
            return None
        setattr(bridge_cls, name, denied)
    return attempts


def isolate_data(tmp: Path) -> Path:
    """Cerebro e historico apontam para `tmp` com uma nota ficticia (nada da pasta pessoal real)."""
    from core import brain as brain_mod
    personal = Path(tmp) / "pessoal"
    (personal / "Notas").mkdir(parents=True, exist_ok=True)
    (personal / "Notas" / "Nota de teste.md").write_text("# Nota de teste\nConteúdo fictício do teste.\n",
                                                          encoding="utf-8")
    brain_mod._instance = brain_mod.Brain(personal_path=str(personal))
    from desktop import history_store
    history_store.HISTORY_FILE = Path(tmp) / "history.jsonl"
    history_store.HISTORY_FILE.write_text("", encoding="utf-8")
    # Preferencias (podem ter instrucoes escritas pela pessoa): le um arquivo vazio na pasta temporaria
    import functools
    from core import user_settings
    if not getattr(user_settings.load, "_sandboxed", False):
        sandboxed = functools.partial(user_settings.load, Path(tmp) / "settings.json")
        sandboxed._sandboxed = True
        user_settings.load = sandboxed
    return personal


class _NoNetwork(QNetworkAccessManager):
    """Arquivo local (o proprio QML, imagens do app) passa; o resto vira uma URL invalida e falha."""
    blocked: list = []

    def createRequest(self, op, request, data=None):
        url = request.url()
        if not url.isLocalFile() and url.scheme() not in ("qrc", ""):
            _NoNetwork.blocked.append(url.toString()[:200])
            request = QNetworkRequest(QUrl("invalid-scheme://blocked"))
        return super().createRequest(op, request, data)


def _factory():
    from PySide6.QtQml import QQmlNetworkAccessManagerFactory

    class Factory(QQmlNetworkAccessManagerFactory):
        def create(self, parent):
            return _NoNetwork(parent)
    return Factory()


class _UrlSink(QObject):
    opened: list = []

    @Slot(QUrl)
    def open(self, url):
        _UrlSink.opened.append(url.toString()[:200])


def prepare_env() -> None:
    """Antes de criar o motor QML: XMLHttpRequest nao le nem grava arquivo local."""
    os.environ["QML_XHR_ALLOW_FILE_WRITE"] = "0"
    os.environ["QML_XHR_ALLOW_FILE_READ"] = "0"


def harden_engine(engine, tmp: Path) -> dict:
    """Rede bloqueada, LocalStorage na pasta temporaria e abertura externa interceptada. -> registros."""
    from PySide6.QtGui import QDesktopServices
    factory = _factory()
    engine.setNetworkAccessManagerFactory(factory)
    engine.setOfflineStoragePath(str(Path(tmp) / "offline"))
    sink = _UrlSink()
    for scheme in _SCHEMES:
        QDesktopServices.setUrlHandler(scheme, sink, "open")
    # o motor precisa manter as referencias vivas
    engine._sandbox_keep = (factory, sink)
    return {"network": _NoNetwork.blocked, "opened": _UrlSink.opened}


def sandbox(engine_factory, bridge_cls):
    """Prepara tudo e devolve (engine, attempts, records, tmp). Use ANTES de carregar o QML."""
    prepare_env()
    tmp = Path(tempfile.mkdtemp(prefix="qml-sandbox-"))
    attempts = lock_bridge(bridge_cls)
    isolate_data(tmp)
    engine = engine_factory()
    records = harden_engine(engine, tmp)
    return engine, attempts, records, tmp
