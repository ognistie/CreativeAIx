"""
Creative AIx Desktop: a interface React (ui/) dentro de janelas Qt (QtWebEngine).

    QWebEngineView (app://ui/index.html)  ─┐
    QWebEngineView (app://ui/mini.html)   ─┼─ ws://127.0.0.1 (token) ─> WebBridge (Bridge + servidor local)
                                           │                              └─> Controller / core / agentes
    WindowMode, atalhos globais, voz ──────┘

Por que assim: roda dentro do python.exe e do QtWebEngineProcess.exe, ambos assinados, entao o
Controle Inteligente de Aplicativos do Windows nao bloqueia (um executavel nosso, sem assinatura, seria
bloqueado).

Seguranca:
- A pagina so carrega do esquema app:// servido daqui (ui/dist). Navegacao para fora e bloqueada;
  links https vao para o navegador padrao.
- Porta e token do servidor local entram na pagina por script injetado (nunca na URL).
- Papel de parede: app://wallpaper/<id> resolve o id pelo core/wallpapers.py; a pagina nunca recebe
  caminho de disco nem acesso a arquivo.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineUrlRequestJob,
                                     QWebEngineUrlScheme, QWebEngineUrlSchemeHandler)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog

from desktop.bridge import Bridge
from desktop.server import HOST_METHODS, RPC_METHODS, Dispatcher, EventServer

APP_DIR = Path(__file__).resolve().parents[1]
UI_DIST = APP_DIR.parent / "ui" / "dist"
SCHEME = b"app"
UI_ORIGIN = "app://ui"
MINI_SIZE = (380, 520)
FONT_TYPES = {".woff2": "font/woff2", ".woff": "font/woff"}     # fonte da interface (Inter), empacotada em ui/dist
BASE_BG = "#08090a"          # base da paleta padrao (app/design/theme.json): sem flash branco ao abrir


def register_scheme() -> None:
    """Antes de criar a QApplication."""
    scheme = QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.CorsEnabled
                    | QWebEngineUrlScheme.Flag.ContentSecurityPolicyIgnored)
    QWebEngineUrlScheme.registerScheme(scheme)


def resolve_ui_file(dist: Path, rel: str) -> Optional[Path]:
    """Arquivo da interface dentro de ui/dist, ou None (fora da pasta, inexistente)."""
    root = dist.resolve()
    candidate = (root / (rel or "index.html")).resolve()
    return candidate if candidate.is_file() and root in candidate.parents else None


class SchemeHandler(QWebEngineUrlSchemeHandler):
    """app://ui/<arquivo> (ui/dist) e app://wallpaper/<id> (core/wallpapers.py)."""

    def __init__(self, dist: Path, wallpaper: Callable[[str], Optional[Path]], parent=None) -> None:
        super().__init__(parent)
        self.dist = dist.resolve()
        self.wallpaper = wallpaper

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802 (Qt)
        url = job.requestUrl()
        host, rel = url.host(), url.path().lstrip("/")
        path: Optional[Path] = None
        if host == "ui":
            path = resolve_ui_file(self.dist, rel)
        elif host == "wallpaper":
            path = self.wallpaper(rel)
        if path is None or not path.is_file():
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        mime = FONT_TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            mime = "text/javascript"
        buf = QBuffer(parent=job)
        buf.setData(QByteArray(path.read_bytes()))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(mime.encode(), buf)


class Page(QWebEnginePage):
    """So o app:// navega dentro da janela; https vai para o navegador; o resto e bloqueado."""

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:  # noqa: N802 (Qt)
        if url.scheme() == SCHEME.decode():
            return True
        if url.scheme() == "https":
            QDesktopServices.openUrl(url)
        return False

    def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802 (Qt)
        """Avisos e erros da interface vao para o log do app (logs/app.log quando sem console)."""
        if level != QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel:
            print(f"[ui] {source.rsplit('/', 1)[-1]}:{line} {message}")

    def createWindow(self, _type):  # noqa: N802 (Qt): target=_blank abre no navegador padrao
        page = Page(self.profile(), self)
        page.urlChanged.connect(lambda u: (u.scheme() == "https" and QDesktopServices.openUrl(u), page.deleteLater()))
        return page


class WidgetWindow(QObject):
    """O pedaco da API de QWindow que o WindowMode usa, sobre um QWidget (a janela da interface).
    E um QObject filho do widget: o WindowMode o usa como pai dos timers."""

    def __init__(self, widget) -> None:
        super().__init__(widget)
        self.w = widget

    def visibility(self):
        return self.w.windowHandle().visibility()

    def showMaximized(self): self.w.showMaximized()          # noqa: E704,N802
    def showNormal(self): self.w.showNormal()                # noqa: E704,N802
    def showMinimized(self): self.w.showMinimized()          # noqa: E704,N802
    def show(self): self.w.show()                            # noqa: E704
    def hide(self): self.w.hide()                            # noqa: E704
    def raise_(self): self.w.raise_()                        # noqa: E704
    def requestActivate(self): self.w.activateWindow()       # noqa: E704,N802
    def isVisible(self): return self.w.isVisible()           # noqa: E704,N802
    def winId(self): return self.w.winId()                   # noqa: E704,N802
    def width(self): return self.w.width()                   # noqa: E704
    def height(self): return self.w.height()                 # noqa: E704
    def screen(self): return self.w.screen()                 # noqa: E704
    def setPosition(self, x, y): self.w.move(x, y)           # noqa: E704,N802

    def setProperty(self, name, value):  # noqa: N802
        if name == "_q_showWithoutActivating":
            self.w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, bool(value))
            return True
        return self.w.setProperty(name, value)


class WebBridge(Bridge):
    """O Bridge (Signals Qt + BridgeCore), com cada evento indo para a interface pelo servidor local.

    Os metodos chegam pelo servidor numa thread de trabalho: o que mexe em janela e marshalado para a
    thread da interface (Qt so aceita janela na thread principal).
    """

    _gui_call = Signal(object)

    def __init__(self, server: EventServer) -> None:
        self._server = server
        self._mini_view = None
        self._main_view = None
        Bridge.__init__(self)
        self._gui_call.connect(self._run_gui_call, Qt.ConnectionType.QueuedConnection)

    def _emit(self, name: str, payload: Any = None) -> None:
        Bridge._emit(self, name, payload)
        self._server.publish(name, payload)
        if name == "runningChanged" and self._mini_view is not None:
            self._on_gui(lambda: self._set_mini_passive(bool(payload)))

    # ── Thread da interface ──────────────────────────────────────────
    @Slot(object)
    def _run_gui_call(self, fn) -> None:
        fn()

    def _on_gui(self, fn: Callable[[], Any], wait: bool = False, timeout: float = 600.0) -> Any:
        if threading.current_thread() is threading.main_thread():
            return fn()
        if not wait:
            self._gui_call.emit(fn)
            return None
        done, box = threading.Event(), {}

        def run():
            try:
                box["v"] = fn()
            finally:
                done.set()
        self._gui_call.emit(run)
        done.wait(timeout)
        return box.get("v")

    def attach_mini(self, view) -> None:
        self._mini_view = view

    def _set_mini_passive(self, passive: bool) -> None:
        """Durante a tarefa o mini chat nao recebe clique nem foco (o agente esta usando outro app)."""
        handle = self._mini_view.windowHandle() if self._mini_view else None
        if handle is None:
            return
        handle.setFlag(Qt.WindowType.WindowTransparentForInput, passive)
        handle.setFlag(Qt.WindowType.WindowDoesNotAcceptFocus, passive)

    # ── Metodos de janela (chamados pela interface) ──────────────────
    def restoreMain(self) -> None:  # noqa: N802
        self._on_gui(lambda: Bridge.restoreMain(self))

    def closeMini(self) -> None:  # noqa: N802
        self._on_gui(lambda: Bridge.closeMini(self))

    def mainActivated(self) -> None:  # noqa: N802
        self._on_gui(lambda: Bridge.mainActivated(self))

    def setTitleBarColor(self, color: str) -> None:  # noqa: N802
        self._on_gui(lambda: Bridge.setTitleBarColor(self, color))

    # ── So no host Qt ────────────────────────────────────────────────
    def pickFiles(self) -> str:  # noqa: N802
        """Dialogo de arquivos do Windows; devolve os caminhos escolhidos (JSON)."""
        def ask():
            paths, _ = QFileDialog.getOpenFileNames(None, "Anexar arquivos")
            return paths
        return json.dumps(self._on_gui(ask, wait=True) or [], ensure_ascii=False)

    def pickFolder(self) -> str:  # noqa: N802
        """Dialogo de pasta do Windows (pasta do projeto do Claude Code / Codex); "" se cancelar."""
        def ask():
            return QFileDialog.getExistingDirectory(None, "Pasta do projeto") or ""
        return json.dumps(self._on_gui(ask, wait=True) or "", ensure_ascii=False)

    # ── Janela principal sem moldura: a barra de titulo da interface comanda ─────
    _EDGES = {"left": Qt.Edge.LeftEdge, "right": Qt.Edge.RightEdge, "top": Qt.Edge.TopEdge, "bottom": Qt.Edge.BottomEdge}

    def _main_window(self):
        return self._main_view.windowHandle() if self._main_view is not None else None

    def attach_main(self, view) -> None:
        self._main_view = view

    def _maximized(self) -> bool:
        return bool(self._main_view is not None and self._main_view.isMaximized())

    def windowMinimize(self) -> None:  # noqa: N802
        self._on_gui(lambda: self._main_view is not None and self._main_view.showMinimized())

    def windowToggleMaximize(self) -> str:  # noqa: N802
        def toggle():
            v = self._main_view
            if v is not None:
                v.showNormal() if v.isMaximized() else v.showMaximized()
            return json.dumps({"maximized": self._maximized()})
        return self._on_gui(toggle, wait=True, timeout=5) or json.dumps({"maximized": False})

    def windowClose(self) -> None:  # noqa: N802
        self._on_gui(lambda: self._main_view is not None and self._main_view.close())

    def windowStartMove(self) -> None:  # noqa: N802
        """Arrastar pela barra de titulo (o Windows cuida do encaixe nas bordas)."""
        def move():
            handle = self._main_window()
            if handle is not None:
                handle.startSystemMove()
        self._on_gui(move)

    def windowStartResize(self, edge: str) -> None:  # noqa: N802
        """edge: left | right | top | bottom ou combinacao com hifen (top-left...)."""
        flags = Qt.Edge(0)
        for part in (edge or "").split("-"):
            if part in self._EDGES:
                flags |= self._EDGES[part]
        if not flags:
            return

        def resize():
            handle = self._main_window()
            if handle is not None and not self._maximized():
                handle.startSystemResize(flags)
        self._on_gui(resize)

    def windowState(self) -> str:  # noqa: N802
        return self._on_gui(lambda: json.dumps({"maximized": self._maximized()}), wait=True, timeout=5) \
            or json.dumps({"maximized": False})

    def openExternal(self, url: str) -> bool:  # noqa: N802
        """So https, no navegador padrao."""
        if not url.startswith("https://"):
            return False
        self._on_gui(lambda: QDesktopServices.openUrl(QUrl(url)))
        return True


def _wallpaper_file() -> Callable[[str], Optional[Path]]:
    """Papel de parede pelo id. Nao depende do Bridge: a abertura ja mostra o fundo escolhido enquanto o nucleo
    carrega (a pagina guarda o ultimo id visto)."""
    def resolve(wid: str) -> Optional[Path]:
        try:
            from urllib.parse import unquote
            from core import wallpapers
            from core.brain import get_brain
            item = wallpapers.resolve(unquote(wid), get_brain().store.personal)
            return Path(item["path"]) if item and item.get("path") else None
        except Exception:
            return None
    return resolve


def _make_view(profile: QWebEngineProfile, page_name: str, info: dict, background: QColor) -> QWebEngineView:
    view = QWebEngineView()
    page = Page(profile, view)
    page.setBackgroundColor(background)
    script = QWebEngineScript()
    script.setName("creative-aix-host")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(False)
    script.setSourceCode(f"window.__CREATIVE_AIX__ = {json.dumps({**info, 'window': page_name.split('.')[0]})};")
    page.scripts().insert(script)
    view.setPage(page)
    view.setUrl(QUrl(f"{UI_ORIGIN}/{page_name}"))
    return view


def ui_available() -> bool:
    return (UI_DIST / "index.html").is_file() and (UI_DIST / "mini.html").is_file()


# Modulos pesados do nucleo (SDK do provedor, Maestro, Controller): importados numa thread enquanto a janela ja
# aparece com a abertura. Antes eram importados na thread da interface, antes de qualquer janela: ~6 s em que o
# Windows mostrava "nao respondendo" e um segundo clique abria outro app.
PRELOAD = ("anthropic", "numpy", "pyautogui", "agents.maestro", "desktop.controller", "core.automation",
           "core.voice.stt")


class _CoreLoader(QObject):
    """Importa o nucleo fora da thread da interface e avisa (sinal enfileirado) quando terminar."""

    loaded = Signal()

    def start(self) -> None:
        def work():
            import importlib
            for name in PRELOAD:
                try:
                    importlib.import_module(name)
                except Exception as exc:          # o Bridge vai importar de novo e mostrar o erro real
                    print(f"[desktop] pre-carga de {name} falhou: {type(exc).__name__}: {exc}")
            try:
                # O cliente do provedor carrega os certificados TLS (~0,5 s): criado aqui, o Bridge so o reusa.
                from core.ai_client import get_client
                get_client()
            except Exception:
                pass                              # sem chave: o Bridge mostra o erro como antes
            self.loaded.emit()
        threading.Thread(target=work, daemon=True, name="core-preload").start()


def run() -> int:
    import time
    from desktop.instance import InstanceServer, claim, notify_running, notify_running_wait
    from desktop.shell import APP_ID, _brand_icon, _quit_on_signals, _setup_fonts, _shutdown

    started = time.perf_counter()
    register_scheme()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Creative AIx")
    app.setOrganizationName("ognistie")
    app.setApplicationDisplayName("Creative AIx")
    app.setWindowIcon(_brand_icon())
    first = claim()
    if first is False:
        notify_running_wait()                     # a outra instancia vem para a frente (mesmo se ainda carregando)
        return 0
    if notify_running():
        return 0
    # Instancia unica registrada ja aqui, antes de qualquer coisa demorada: abrir de novo enquanto o app
    # carrega traz esta janela para a frente em vez de abrir uma segunda.
    windows: dict = {}

    def show_existing() -> None:
        main = windows.get("main")
        if main is None:
            return
        if main.isMinimized() or not main.isVisible():
            main.showMaximized()
        main.raise_()
        main.activateWindow()

    instance = InstanceServer(show_existing, parent=app)
    if not instance.listening:
        print("[desktop] sem controle de instancia unica")
    _setup_fonts(app)
    _quit_on_signals(app)

    server = EventServer(extra_origins=(UI_ORIGIN,)).start()
    info = {"port": server.port, "token": server.token, "host": "qt"}
    holder: dict = {}

    profile = QWebEngineProfile("creative-aix", app)
    profile.setPersistentStoragePath(str(APP_DIR / "desktop" / "data" / "web"))
    handler = SchemeHandler(UI_DIST, _wallpaper_file(), app)
    profile.installUrlSchemeHandler(SCHEME, handler)

    main = _make_view(profile, "index.html", info, QColor(BASE_BG))
    main.setWindowTitle("Creative AIx")
    # Sem a moldura do Windows: a barra de titulo e da interface (mesmo material do app, nao uma faixa a parte)
    main.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    # Sem moldura o Qt tira os estilos de minimizar/maximizar: clicar no icone da barra de tarefas nao minimizava e o
    # encaixe nas bordas (Snap) ficava limitado. Os hints devolvem os estilos sem desenhar a moldura.
    main.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
    main.setWindowFlag(Qt.WindowType.WindowSystemMenuHint, True)
    main.setMinimumSize(900, 600)
    screen = app.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        main.setGeometry(area.x() + 40, area.y() + 40, min(1440, area.width() - 80), min(900, area.height() - 80))
    main.showMaximized()
    windows["main"] = main
    print(f"[desktop] janela em {time.perf_counter() - started:.2f} s")

    mini = _make_view(profile, "mini.html", info, QColor(0, 0, 0, 0))
    mini.setWindowTitle("Creative AIx · mini chat")
    mini.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    mini.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    mini.resize(*MINI_SIZE)
    mini.winId()                                   # cria a janela nativa sem mostrar

    def attach_core() -> None:
        """Nucleo importado: o Bridge sobe na thread da interface (QObject) e o servidor passa a responder."""
        bridge = WebBridge(server)
        holder["bridge"] = bridge
        bridge.set_title_window(main.windowHandle())
        bridge.attach_windows(WidgetWindow(main), WidgetWindow(mini))
        bridge.attach_mini(mini)
        bridge.attach_main(main)
        server.attach(Dispatcher(bridge, RPC_METHODS | HOST_METHODS))
        app.aboutToQuit.connect(lambda: _shutdown(bridge))
        print(f"[desktop] nucleo pronto em {time.perf_counter() - started:.2f} s")

    loader = _CoreLoader()
    loader.loaded.connect(attach_core, Qt.ConnectionType.QueuedConnection)
    loader.start()
    app.aboutToQuit.connect(server.stop)
    app._keep = (holder, server, profile, handler, main, mini, instance, loader)  # type: ignore[attr-defined]
    return app.exec()

if __name__ == "__main__":
    sys.exit(run())
