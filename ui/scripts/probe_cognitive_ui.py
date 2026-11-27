"""Verificacao visual reproduzivel: Qt fora da tela, perfil descartavel e somente dados demo.

Inicie `npm run dev -- --port 5178`; rode com o Python do projeto.
Nao inicia Controller, voz, ferramentas ou chamadas a modelos.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-logging --log-level=3")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "creativeaix-cognitive")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
    from PySide6.QtCore import QTimer, QUrl
    app = QApplication([])
    errors = []

    class ProbePage(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                errors.append(f"{source.rsplit('/', 1)[-1]}:{line}: {message}")

    profile = QWebEngineProfile()  # sem nome: off-the-record
    view = QWebEngineView()
    page = ProbePage(profile, view)
    view.setPage(page)
    view.resize(1600, 1100)
    view.show()
    result = {"ok": False, "synthetic": True, "checks": {}, "shots": [], "errors": errors}

    def js(code, callback=lambda _: None):
        page.runJavaScript(code, 0, callback)

    def wait_for(expression, then):
        def checked(found):
            if found:
                then()
            else:
                QTimer.singleShot(300, lambda: wait_for(expression, then))
        js(expression, checked)

    def shot(name):
        path = args.out / (name + ".png")
        view.grab().save(str(path))
        result["shots"].append(str(path.resolve()))

    def open_lab():
        js("[...document.querySelectorAll('nav button')].find(b=>b.textContent.includes('AI Research Lab')).click()")
        wait_for("!!document.querySelectorAll('.lab-hub-card')[2]", open_memory)

    def open_memory():
        js("document.querySelectorAll('.lab-hub-card')[2].click()")
        wait_for("!!document.querySelector('.hp-canvas') && document.querySelectorAll('.hp-timeline option').length>1", dark)

    def dark():
        QTimer.singleShot(3500, lambda: (shot("dark"), replay()))

    def replay():
        js("(()=>{const s=document.querySelector('.hp-timeline select');s.value='demo-cognitive';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
        wait_for("!!document.querySelector('.hp-timeline input')", scrub)

    def scrub():
        js("(()=>{const s=document.querySelector('.hp-timeline input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(s,'2100');s.dispatchEvent(new Event('input',{bubbles:true}));return true})()")
        QTimer.singleShot(1800, check_replay)

    def check_replay():
        js("document.querySelector('.hp-live-step')?.textContent.includes('verification') || document.querySelector('.hp-live-step')?.textContent.includes('Verificação')",
           lambda ok: result["checks"].update(replay=bool(ok)))
        shot("replay")
        js("document.documentElement.dataset.motion='off'")
        QTimer.singleShot(1800, stable_start)

    def stable_start():
        js("(()=>{const c=document.querySelector('.hp-canvas');window.__cognitiveFrame=c.toDataURL();window.__draws=0;const ctx=c.getContext('2d'),f=ctx.clearRect;ctx.clearRect=function(...args){window.__draws++;return f.apply(this,args)}})()")
        QTimer.singleShot(600, stable_end)

    def stable_end():
        js("window.__cognitiveFrame===document.querySelector('.hp-canvas').toDataURL()",
           lambda ok: result["checks"].update(reduced_motion=bool(ok)))
        js("window.__draws", lambda n: (result.update(idle_canvas_draws=n), result["checks"].update(idle_rendering=n == 0)))
        js("document.documentElement.dataset.theme='claro';document.querySelector('.lab-knowledge-list li button')?.click()")
        wait_for("!!document.querySelector('.lab-note h3')", light)

    def light():
        result["checks"]["note_navigation"] = True
        QTimer.singleShot(1000, lambda: (shot("light-note"), compact()))

    def compact():
        js("[...document.querySelectorAll('nav button')].find(b=>b.textContent.includes('Nova conversa')).click()")
        wait_for("!!document.querySelector('.task-panorama-toggle')", toggle)

    def toggle():
        js("(()=>{const b=document.querySelector('.task-panorama-toggle');if(b.getAttribute('aria-pressed')!=='true')b.click()})()")
        wait_for("(()=>{const c=document.querySelector('.is-compact .hp-canvas');return !!c && c.width>100 && c.height>100})()", done)

    def done():
        result["checks"]["compact"] = True
        QTimer.singleShot(3500, finish)

    def finish():
        shot("compact")
        result["ok"] = all(result["checks"].values()) and len(result["checks"]) == 5 and not errors
        print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
        app.exit(0 if result["ok"] else 1)

    def timeout():
        result["error"] = "timeout"
        print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
        app.exit(1)

    page.load(QUrl("http://127.0.0.1:5178/?demo&nosplash"))
    wait_for("[...document.querySelectorAll('nav button')].some(b=>b.textContent.includes('AI Research Lab'))", open_lab)
    QTimer.singleShot(90000, timeout)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
