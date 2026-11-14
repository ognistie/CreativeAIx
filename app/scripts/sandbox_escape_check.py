"""Carrega um QML hostil dentro de desktop/qml_sandbox.py e imprime, em JSON, o que ele conseguiu fazer.

Uso (os testes chamam em subprocesso, um app Qt por processo):
    python scripts/sandbox_escape_check.py <arquivo.qml> <arquivo-alvo-fora-do-workspace>
"""
import json
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import PySide6
DLL_DIRECTORY = os.add_dll_directory(str(Path(PySide6.__file__).parent)) if os.name == 'nt' else None
from types import SimpleNamespace
from PySide6.QtCore import QObject, QUrl, QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent


def main(qml_path: str, escape_target: str) -> int:
    from desktop import qml_sandbox
    app = QGuiApplication([])
    from desktop.bridge import Bridge
    engine, attempts, records, tmp = qml_sandbox.sandbox(QQmlApplicationEngine, Bridge)
    bridge = Bridge.__new__(Bridge)
    QObject.__init__(bridge)
    bridge._controller = SimpleNamespace(state={'running': False}, list_conversations=lambda: [],
                                         session=SimpleNamespace(id='qa-sandbox'))
    bridge._running = False
    bridge._voice = bridge._window_mode = bridge._stop_hotkey = None
    engine.rootContext().setContextProperty('Bridge', bridge)
    personal = tmp / "pessoal"
    before = sorted(str(p.relative_to(personal)) for p in personal.rglob("*"))
    src = Path(qml_path).read_text(encoding="utf-8").replace("ESCAPE_URL", QUrl.fromLocalFile(escape_target).toString())
    comp = QQmlComponent(engine)
    comp.setData(src.encode("utf-8"), QUrl.fromLocalFile(str(tmp / "proposta.qml")))
    obj = comp.create()
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()
    results = obj.property("results") if obj is not None else None
    results = results.toVariant() if hasattr(results, "toVariant") else (results or {})
    after = sorted(str(p.relative_to(personal)) for p in personal.rglob("*"))
    offline = Path(tmp) / "offline"
    print(json.dumps({
        "loaded": obj is not None, "errors": comp.errorString() if obj is None else "",
        "denied": sorted(set(attempts)), "network": records["network"], "opened": records["opened"],
        "escaped_file": Path(escape_target).exists(), "personal_changed": before != after,
        "read": results.get("read", ""), "results": {k: str(v)[:160] for k, v in results.items()},
        "storage_in_sandbox": offline.exists(),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
