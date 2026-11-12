"""QML load/render check with a fixture bridge. No mic, hotkeys, API or user history.

Runs inside desktop/qml_sandbox.py: the same script checks QML proposed by Developer mode, which has not been
reviewed yet. Bridge slots outside the read list are denied, data is synthetic (temporary brain, history and
settings), the QML engine has no network, Qt.openUrlExternally is intercepted and file writes are off.
Any denied write, network request or external open during load fails the smoke.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import PySide6
DLL_DIRECTORY = os.add_dll_directory(str(Path(PySide6.__file__).parent)) if os.name == 'nt' else None
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QObject, QUrl, QEventLoop, QTimer
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from desktop.bridge import Bridge


def main():
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication([])
    from desktop.main import _setup_fonts
    from PySide6.QtGui import QFontDatabase
    # Offscreen Windows lacks the native font discovery path. Load the installed OS font,
    # using the same family as the real entry point; no font is redistributed.
    for name in ('segoeui.ttf', 'SegoeIcons.ttf', 'segmdl2.ttf'):
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    _setup_fonts(app)
    from desktop import qml_sandbox
    engine, attempts, records, _tmp = qml_sandbox.sandbox(QQmlApplicationEngine, Bridge)
    bridge = Bridge.__new__(Bridge)
    QObject.__init__(bridge)
    bridge._controller = SimpleNamespace(state={'running': False}, list_conversations=lambda: [],
                                         session=SimpleNamespace(id='qa-fixture'))
    bridge._running = False
    bridge._voice = bridge._window_mode = bridge._stop_hotkey = None
    loop = QEventLoop()
    errors = []
    engine.warnings.connect(lambda items: errors.extend(e.toString() for e in items))
    engine.objectCreated.connect(lambda *args: loop.quit())
    engine.rootContext().setContextProperty('Bridge', bridge)
    engine.addImportPath(str(ROOT / 'desktop' / 'qml'))
    engine.load(QUrl.fromLocalFile(str(ROOT / 'desktop' / 'qml' / 'Main.qml')))
    if not engine.rootObjects():
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
    if not engine.rootObjects():
        print('\n'.join(errors))
        return 1
    root = engine.rootObjects()[0]
    root.setProperty('splashActive', False)
    root.show()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()
    image = root.grabWindow()
    screenshot = ROOT / 'memory' / 'ui-release.png'
    if image.isNull() or not image.save(str(screenshot)):
        print('QML loaded but rendering failed.')
        return 1
    if bridge.metaObject().indexOfMethod('approvePlan(bool,QString)') < 0:
        return 1
    print('QML loaded and rendered:', image.width(), image.height())
    # QML que tenta gravar, usar a rede ou abrir algo fora ao carregar reprova (caixa de areia)
    if attempts:
        errors.append('sandbox: escrita negada na Bridge: ' + ', '.join(sorted(set(attempts))))
    if records['network']:
        errors.append('sandbox: rede bloqueada: ' + ', '.join(records['network'][:3]))
    if records['opened']:
        errors.append('sandbox: abertura externa bloqueada: ' + ', '.join(records['opened'][:3]))
    if errors:
        print('\n'.join(errors))
    # Destroy windows while the context bridge is still alive, avoiding shutdown-only warnings.
    for window in app.topLevelWindows(): window.close()
    engine.deleteLater(); app.processEvents()
    return 0 if not errors else 1


if __name__ == '__main__': raise SystemExit(main())
