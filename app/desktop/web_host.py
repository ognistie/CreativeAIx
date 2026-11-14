"""
Creative AIx Desktop: a interface React (ui/) dentro de janelas Qt (QtWebEngine).

    QWebEngineView (app://ui/index.html)  ─┐
    QWebEngineView (app://ui/mini.html)   ─┼─ ws://127.0.0.1 (token) ─> WebBridge (Bridge + servidor local)
                                           │                              └─> Controller / core / agentes
    WindowMode, atalhos globais, voz ──────┘  (os mesmos do app QML)

Por que assim: roda dentro do python.exe e do QtWebEngineProcess.exe, ambos assinados, entao o
Controle Inteligente de Aplicativos do Windows nao bloqueia (um executavel nosso, sem assinatura, seria
bloqueado). O nucleo, os atalhos, a voz e a troca para o mini chat sao os mesmos do app QML.

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
BASE_BG = "#011d1c"          # Theme.qml (abismo escuro): sem flash branco ao abrir


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
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
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
    """O Bridge do app QML, com cada evento tambem indo para a interface web pelo servidor local.

    Os metodos chegam pelo servidor numa thread de trabalho: o que mexe em janela e marshalado para a
    thread da interface (Qt so aceita janela na thread principal).
    """

    _gui_call = Signal(object)

    def __init__(self, server: EventServer) -> None:
        self._server = server
        self._mini_view = None
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

    def openExternal(self, url: str) -> bool:  # noqa: N802
        """So https, no navegador padrao."""
        if not url.startswith("https://"):
            return False
        self._on_gui(lambda: QDesktopServices.openUrl(QUrl(url)))
        return True


def _wallpaper_file(bridge: WebBridge) -> Callable[[str], Optional[Path]]:
    def resolve(wid: str) -> Optional[Path]:
        try:
            from urllib.parse import unquote
            from core import wallpapers
            item = wallpapers.resolve(unquote(wid), bridge._brain().store.personal)
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


def run() -> int:
    from desktop.instance import InstanceServer, notify_running
    from desktop.main import APP_ID, _brand_icon, _quit_on_signals, _setup_fonts, _shutdown

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
    if notify_running():
        return 0
    _setup_fonts(app)

    server = EventServer(extra_origins=(UI_ORIGIN,)).start()
    bridge = WebBridge(server)
    server.attach(Dispatcher(bridge, RPC_METHODS | HOST_METHODS))
    info = {"port": server.port, "token": server.token, "host": "qt"}

    profile = QWebEngineProfile("creative-aix", app)
    profile.setPersistentStoragePath(str(APP_DIR / "desktop" / "data" / "web"))
    handler = SchemeHandler(UI_DIST, _wallpaper_file(bridge), app)
    profile.installUrlSchemeHandler(SCHEME, handler)

    main = _make_view(profile, "index.html", info, QColor(BASE_BG))
    main.setWindowTitle("Creative AIx")
    main.setMinimumSize(900, 600)
    screen = app.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        main.setGeometry(area.x() + 40, area.y() + 40, min(1440, area.width() - 80), min(900, area.height() - 80))
    main.showMaximized()
    bridge.set_title_window(main.windowHandle())

    mini = _make_view(profile, "mini.html", info, QColor(0, 0, 0, 0))
    mini.setWindowTitle("Creative AIx · mini chat")
    mini.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    mini.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    mini.resize(*MINI_SIZE)
    mini.winId()                                   # cria a janela nativa sem mostrar
    bridge.attach_windows(WidgetWindow(main), WidgetWindow(mini))
    bridge.attach_mini(mini)

    def show_existing() -> None:
        if main.isMinimized() or not main.isVisible():
            main.showMaximized()
        main.raise_()
        main.activateWindow()

    instance = InstanceServer(show_existing, parent=app)
    if not instance.listening:
        print("[desktop] sem controle de instancia unica")
    _quit_on_signals(app)
    app.aboutToQuit.connect(lambda: (_shutdown(bridge), server.stop()))
    app._keep = (bridge, server, profile, handler, main, mini, instance)  # type: ignore[attr-defined]
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
