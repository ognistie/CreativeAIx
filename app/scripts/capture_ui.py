"""Capturas fora da tela de todas as telas, nos dois temas (revisao visual da E2/E4).

Mesma montagem do smoke (bridge de fixture, sem microfone, API nem historico real), renderizador
por software. Grava memory/ui-captures/<tema>-<n>-<tela>.png e falha se o QML avisar algo.
UI_WALLPAPER=catalog:<id> acrescenta capturas com o papel de parede aplicado.
UI_PALETTE=<paleta> tira a foto e usa o fundo dessa paleta (com GPU, a malha em shader).
UI_SYNTHETIC=1 usa dados sinteticos (Cerebro, Diario, Lab e historico numa pasta temporaria).
UI_GPU=1 renderiza com a placa de video (malha em shader, vidro desfocado): janela real posicionada fora
da area visivel, sem foco e sem receber entrada (o grab do modo offscreen nao funciona com Direct3D).
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

GPU = os.environ.get('UI_GPU') == '1'
os.environ['QT_QPA_PLATFORM'] = 'windows' if GPU else 'offscreen'
os.environ.setdefault('QT_QUICK_BACKEND', 'rhi' if GPU else 'software')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import PySide6
DLL_DIRECTORY = os.add_dll_directory(str(Path(PySide6.__file__).parent)) if os.name == 'nt' else None
from PySide6.QtGui import QGuiApplication, QFontDatabase
from PySide6.QtCore import QObject, QUrl, QEventLoop, QTimer, QMetaObject, Q_ARG, Qt
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle
from desktop.bridge import Bridge

PAGES = ['conversa', 'historico', 'sobre', 'configuracoes', 'cerebro', 'voce', 'harness', 'atividade', 'diario', 'biblioteca',
         'lab']
SETTER = (b'import QtQuick\nimport "components" as C\n'
          b'QtObject { function mode(m) { C.Theme.mode = m } function paper(w) { C.Theme.applyAppearance({ wallpaper: w }) }'
          b' function look(p) { C.Theme.applyAppearance({ wallpaper: "", palette: p }) } }')


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication([])
    from desktop.main import _setup_fonts
    for name in ('segoeui.ttf', 'bahnschrift.ttf', 'SegoeIcons.ttf', 'segmdl2.ttf'):
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    _setup_fonts(app)
    if os.environ.get('UI_SYNTHETIC') == '1':      # Cerebro, historico e preferencias sinteticos (nada da pasta pessoal)
        import tempfile
        from desktop import qml_sandbox
        qml_sandbox.isolate_data(Path(tempfile.mkdtemp(prefix='ui-capture-')))
    bridge = Bridge.__new__(Bridge)
    QObject.__init__(bridge)
    bridge._controller = SimpleNamespace(state={'running': False}, list_conversations=lambda: [],
                                         session=SimpleNamespace(id='qa-fixture'))
    bridge._running = False
    bridge._voice = bridge._window_mode = bridge._stop_hotkey = None
    from desktop import history_store
    history_store.HISTORY_FILE = ROOT / 'memory' / 'test_tmp' / 'ui-empty-history.jsonl'
    history_store.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history_store.HISTORY_FILE.write_text('', encoding='utf-8')
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda items: errors.extend(e.toString() for e in items))
    engine.rootContext().setContextProperty('Bridge', bridge)
    engine.addImportPath(str(ROOT / 'desktop' / 'qml'))
    engine.load(QUrl.fromLocalFile(str(ROOT / 'desktop' / 'qml' / 'Main.qml')))
    wait(300)
    if not engine.rootObjects():
        print('\n'.join(errors) or 'QML nao carregou')
        return 1
    root = engine.rootObjects()[0]
    root.setProperty('splashActive', False)
    if GPU:
        root.setFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        root.setPosition(-20000, -20000)
    root.show()
    size = os.environ.get('UI_SIZE', '')            # ex.: 1920x1200 para ver na escala real da tela
    if size:
        w, h = (int(v) for v in size.lower().split('x'))
        root.setProperty('width', w)
        root.setProperty('height', h)
    wait(800)
    out = ROOT / 'memory' / 'ui-captures'
    out.mkdir(parents=True, exist_ok=True)
    comp = QQmlComponent(engine)
    comp.setData(SETTER, QUrl.fromLocalFile(str(ROOT / 'desktop' / 'qml' / 'x.qml')))
    setter = comp.create()
    if setter is None:
        print(comp.errorString())
        return 1
    saved = 0
    palette = os.environ.get('UI_PALETTE', '')      # ex.: ameixa -> sem foto, fundo em malha com essa paleta
    for mode in ('escuro', 'claro'):
        QMetaObject.invokeMethod(setter, 'mode', Q_ARG('QVariant', mode))
        wait(200)
        for n, page in enumerate(PAGES):
            root.setProperty('page', n)
            if palette:       # o Harness reaplica a aparencia salva ao abrir: o fundo de teste volta a cada tela
                QMetaObject.invokeMethod(setter, 'look', Q_ARG('QVariant', palette))
            wait(700 if n == 0 else 450)
            image = root.grabWindow()
            path = out / f'{mode}-{n}-{page}.png'
            if image.isNull() or not image.save(str(path)):
                print('falha ao renderizar', path)
                return 1
            saved += 1
        root.setProperty('sidebarCollapsed', True)
        root.setProperty('page', 0)
        wait(500)
        root.grabWindow().save(str(out / f'{mode}-recolhida.png'))
        root.setProperty('sidebarCollapsed', False)
        saved += 1
        wallpaper = os.environ.get('UI_WALLPAPER', '')
        if wallpaper:
            QMetaObject.invokeMethod(setter, 'paper', Q_ARG('QVariant', wallpaper))
            wait(1500)
            root.grabWindow().save(str(out / f'{mode}-papel.png'))
            root.setProperty('page', 6)
            wait(600)
            root.grabWindow().save(str(out / f'{mode}-papel-harness.png'))
            QMetaObject.invokeMethod(setter, 'paper', Q_ARG('QVariant', ''))
            wait(300)
            saved += 2
    print(f'{saved} capturas em {out}')
    if errors:
        print('\n'.join(errors))
    for window in app.topLevelWindows():
        window.close()
    engine.deleteLater()
    app.processEvents()
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
