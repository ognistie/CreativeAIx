"""Contrato da interface: o Bridge (QML) e o servidor da interface Tauri expõem a mesma coisa.

- As assinaturas Qt do Bridge ficam congeladas em fixtures/bridge_contract.txt.
- Os metodos do servidor (desktop/server.py: RPC_METHODS) sao os @Slots publicos do Bridge.
- Todo evento que o BridgeCore emite existe como Signal (ou e um evento so da casca Tauri).
- O BridgeCore e o servidor carregam sem Qt.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))


def _qt_signatures(cls) -> set:
    from PySide6.QtCore import QMetaMethod
    kinds = {QMetaMethod.MethodType.Slot: "slot", QMetaMethod.MethodType.Signal: "signal"}
    mo, out = cls.staticMetaObject, set()
    for i in range(mo.methodOffset(), mo.methodCount()):
        m = mo.method(i)
        if m.methodType() in kinds:
            t = m.typeName()
            t = t if isinstance(t, str) else bytes(t).decode()
            out.add(f"{kinds[m.methodType()]} {bytes(m.methodSignature()).decode()} -> {t}")
    return out


def _names(signatures: set, kind: str) -> set:
    return {s.split(" ", 1)[1].split("(", 1)[0] for s in signatures if s.startswith(kind + " ")}


class BridgeContract(unittest.TestCase):
    def test_qt_signatures_are_unchanged(self):
        from desktop.bridge import Bridge
        text = (APP / "tests" / "fixtures" / "bridge_contract.txt").read_text(encoding="utf-8")
        frozen = {l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")}
        now = _qt_signatures(Bridge)
        self.assertEqual(sorted(frozen - now), [], "Signals/Slots sumiram do Bridge")
        self.assertEqual(sorted(now - frozen), [], "Signals/Slots novos: atualize fixtures/bridge_contract.txt")

    def test_server_methods_are_the_public_slots(self):
        from desktop.bridge import Bridge
        from desktop.server import QT_WINDOW_ONLY, RPC_METHODS
        public = {s for s in _names(_qt_signatures(Bridge), "slot") if not s.startswith("_")}
        self.assertEqual(sorted(RPC_METHODS ^ (public - QT_WINDOW_ONLY)), [])

    def test_every_core_event_is_a_signal(self):
        from desktop.bridge import Bridge
        source = (APP / "desktop" / "bridge_core.py").read_text(encoding="utf-8")
        emitted = set(re.findall(r'self\._emit\("(\w+)"', source))
        signals = _names(_qt_signatures(Bridge), "signal")
        self.assertEqual(sorted(emitted - signals - Bridge._QT_ONLY_EVENTS), [])
        self.assertIn("planReady", emitted)

    def test_core_and_server_load_without_qt(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import desktop.bridge_core, desktop.server; "
                "bad = sorted(m for m in sys.modules if m.startswith('PySide6')); print(bad); sys.exit(1 if bad else 0)")
        out = subprocess.run([sys.executable, "-c", code, str(APP)], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr[-1500:])

    def test_events_reach_qt_signals(self):
        from PySide6.QtCore import QObject
        from desktop.bridge import Bridge
        b = Bridge.__new__(Bridge)
        QObject.__init__(b)
        got = []
        b.planReady.connect(got.append)
        b.runningChanged.connect(got.append)
        b._emit("planReady", '{"n": 1}')
        b._emit("runningChanged", True)
        b._emit("windowRequest", '{"action": "restore_main"}')     # so da casca Tauri: ignorado no Qt
        self.assertEqual(got, ['{"n": 1}', True])


if __name__ == "__main__":
    unittest.main()
