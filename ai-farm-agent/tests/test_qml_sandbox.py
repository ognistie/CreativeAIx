"""Caixa de areia do QML proposto (desktop/qml_sandbox.py): prova de isolamento exigida antes do Lab.

Um QML hostil tenta gravar pela Bridge, executar uma tarefa, ler dados pessoais e manda-los pela rede, gravar
um arquivo fora do workspace, abrir programas e usar armazenamento local. O estado externo tem de ficar intacto.
"""
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))


class HostileProposal(unittest.TestCase):
    def test_hostile_qml_changes_nothing_outside(self):
        target = Path(tempfile.gettempdir()) / f"escape-{uuid.uuid4().hex[:8]}.txt"
        out = subprocess.run([sys.executable, str(APP / "scripts" / "sandbox_escape_check.py"),
                              str(APP / "tests" / "fixtures" / "malicious_proposal.qml"), str(target)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(APP))
        line = next((l for l in out.stdout.splitlines() if l.startswith("{")), "")
        self.assertTrue(line, out.stdout + out.stderr[-1500:])
        r = json.loads(line)
        self.assertTrue(r["loaded"], r["errors"])
        # escrita e execucao pela Bridge: negadas e registradas
        for slot in ("journalSave", "harnessSave", "brainSave", "saveSettings", "executeTask", "setIntroSeen"):
            self.assertIn(slot, r["denied"])
        for key in ("journal", "harness", "brain", "settings"):
            self.assertIn("Somente leitura", r["results"][key])
        # estado externo intacto
        self.assertFalse(r["escaped_file"])
        self.assertFalse(target.exists())
        self.assertFalse(r["personal_changed"])
        # rede e abertura externa bloqueadas (registradas, nunca feitas)
        self.assertTrue(any("example.invalid" in u for u in r["network"]))
        self.assertEqual(len(r["opened"]), 2)
        # armazenamento local so na pasta temporaria
        self.assertTrue(r["storage_in_sandbox"])

    def test_every_write_slot_is_denied_by_default(self):
        """Slot novo na Bridge nasce negado na caixa de areia: so a lista de leitura passa."""
        from PySide6.QtCore import QMetaMethod
        from desktop.bridge import Bridge
        from desktop.qml_sandbox import READ_SLOTS
        mo = Bridge.staticMetaObject
        slots = {bytes(mo.method(i).name()).decode() for i in range(mo.methodOffset(), mo.methodCount())
                 if mo.method(i).methodType() == QMetaMethod.MethodType.Slot}
        self.assertTrue(READ_SLOTS <= slots, READ_SLOTS - slots)
        for name in ("journalSave", "journalDelete", "harnessSave", "brainSave", "brainDelete", "executeTask",
                     "devPropose", "devAct", "saveSettings", "wallpaperImport", "creatorApply", "codingAgentsCheck"):
            self.assertNotIn(name, READ_SLOTS)


class StaticReview(unittest.TestCase):
    def test_risky_qml_additions_are_flagged(self):
        from core.dev_mode import risky_lines
        diff = ("+++ b/ai-farm-agent/desktop/qml/views/X.qml\n"
                "+    Component.onCompleted: { const x = new XMLHttpRequest() }\n"
                "+    onClicked: Qt.openUrlExternally(\"https://exemplo.com\")\n"
                "+    Image { source: \"http://exemplo.com/a.png\" }\n"
                "+    import QtQuick.LocalStorage\n"
                "+    Text { text: \"ok\" }\n"
                "-    const old = new XMLHttpRequest()\n")
        found = risky_lines(diff)
        self.assertEqual(len(found), 4)
        self.assertFalse(any("Text" in f for f in found))


if __name__ == "__main__":
    unittest.main()
