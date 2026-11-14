"""Abre o app de verdade (desktop/web_host.py) sem janela na tela, captura as telas e sai.

Valida o caminho completo do app oficial: Qt + QtWebEngine + interface React + servidor local + nucleo.
Para cada tela pedida, navega pela barra lateral (clique simulado no DOM), espera e salva um PNG.
Imprime um JSON com o resultado, os erros de console da interface e onde ficaram as imagens.

Uso: python app/scripts/snapshot_web_ui.py [pasta_saida] [--screens task,history,...]
Nao chama o modelo: usa uma chave falsa se nao houver ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.chdir(APP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging --log-level=3")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-snapshot-not-a-real-key")

LABELS = {"task": "Nova conversa", "history": "Histórico", "activity": "Atividade", "brain": "Cérebro", "you": "Você",
          "journal": "Diário", "library": "Biblioteca", "lab": "AI Research Lab", "harness": "Harness",
          "settings": "Configurações", "about": "Sobre"}


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else Path(tempfile.mkdtemp(prefix="caix-ui-"))
    screens = list(LABELS)
    if "--screens" in sys.argv:
        screens = sys.argv[sys.argv.index("--screens") + 1].split(",")
    out.mkdir(parents=True, exist_ok=True)

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from desktop import web_host

    console: list[str] = []
    original_console = web_host.Page.javaScriptConsoleMessage

    def capture_console(self, level, message, line, source):
        console.append(f"{source.rsplit('/', 1)[-1]}:{line} {message}")
        original_console(self, level, message, line, source)
    web_host.Page.javaScriptConsoleMessage = capture_console

    report = {"ok": False, "out": str(out), "shots": [], "console": console}
    original_exec = QApplication.exec

    def exec_with_probe(app):
        views = [w for w in app.topLevelWidgets() if w.__class__.__name__ == "QWebEngineView"]
        main_view = next((v for v in views if v.windowTitle() == "Creative AIx"), None)
        mini_view = next((v for v in views if v is not main_view), None)
        queue = list(screens)

        def shoot(name, view):
            path = out / f"{name}.png"
            view.grab().save(str(path))
            report["shots"].append(str(path))

        def next_screen():
            if not queue:
                if mini_view is not None:
                    mini_view.resize(380, 520)
                    mini_view.show()
                    QTimer.singleShot(1500, lambda: (shoot("mini", mini_view), finish()))
                else:
                    finish()
                return
            name = queue.pop(0)
            label = LABELS[name]
            js = ("(() => { const b = [...document.querySelectorAll('nav button')].find(x => x.textContent.trim().startsWith(%s));"
                  " if (b) b.click(); return !!b; })()") % json.dumps(label)
            main_view.page().runJavaScript(js, 0, lambda found: QTimer.singleShot(1800, lambda: (shoot(name, main_view), next_screen())))

        def check_connected():
            main_view.page().runJavaScript(
                "document.body.innerText.includes('Conectando ao núcleo') ? 'connecting' : 'open'", 0,
                lambda state: (report.__setitem__("core", state), next_screen()))

        def finish():
            report["ok"] = bool(report["shots"]) and report.get("core") == "open"
            print(json.dumps(report, ensure_ascii=False, indent=2))
            app.quit()

        main_view.resize(1440, 900)
        QTimer.singleShot(6000, check_connected)
        QTimer.singleShot(120000, lambda: (print(json.dumps({**report, "error": "timeout"})), app.quit()))
        return original_exec()

    QApplication.exec = exec_with_probe
    code = web_host.run()
    sys.stdout.flush()
    os._exit(0 if report["ok"] else (code or 1))


if __name__ == "__main__":
    main()
