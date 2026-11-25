"""Navegador próprio do app (Playwright) e as ações web_* do AutomationEngine (separados de core/automation.py).

É o caminho legado: o piloto do navegador do usuário (core/browser_pilot.py) cuida da navegação nova. As ações
web_* continuam passando pela porta de política e de efeitos do execute() em core/automation.py.
"""

import os
import time
from datetime import datetime


class BrowserController:
    def __init__(self):
        self.pw=None; self.browser=None; self.page=None; self._started=False

    def start(self):
        if self._started: return True
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=False, args=["--start-maximized"])
            self.page = self.browser.new_context(no_viewport=True).new_page()
            self._started = True; return True
        except Exception as e: print(f"  ⚠️ Playwright: {e}"); return False

    def ensure(self):
        if not self._started: self.start()
        return bool(self.page)

    def goto(self, url):
        if not self.ensure(): return "⚠️ Browser indisponível"
        if not url.startswith("http"): url = "https://"+url
        self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1); return f"🌐 {self.page.title()}"

    def click_el(self, text):
        if not self.ensure(): return "⚠️"
        for fn in [lambda:self.page.get_by_text(text,exact=False).first, lambda:self.page.get_by_role("link",name=text).first, lambda:self.page.get_by_role("button",name=text).first]:
            try:
                loc=fn()
                if loc.is_visible(timeout=2000): loc.click(); return f"🌐 Clicou: '{text[:30]}'"
            except: pass
        try: self.page.click(text, timeout=3000); return f"🌐 Clicou"
        except: return f"❌ '{text[:30]}'"

    def type_in(self, field, text):
        if not self.ensure(): return "⚠️"
        # Tenta múltiplos seletores (field pode ter alternativas separadas por vírgula)
        selectors = [s.strip() for s in field.split(",")]
        for sel in selectors:
            for fn in [
                lambda: self.page.locator(sel).first,
                lambda: self.page.get_by_placeholder(sel).first,
                lambda: self.page.get_by_role("searchbox").first,
                lambda: self.page.get_by_role("textbox").first,
            ]:
                try:
                    loc = fn()
                    if loc.is_visible(timeout=2000):
                        loc.click(); time.sleep(0.3)
                        loc.fill(text)
                        return f"🌐 Digitou: '{text[:30]}'"
                except: pass
        # Fallback: tenta clicar na área de busca e digitar via teclado
        try:
            self.page.keyboard.press("Tab")
            time.sleep(0.2)
            self.page.keyboard.type(text, delay=50)
            return f"🌐 Digitou (keyboard): '{text[:30]}'"
        except: pass
        return f"❌ '{field[:20]}'"

    def press(self, key):
        if not self.ensure(): return "⚠️"
        self.page.keyboard.press(key); return f"🌐 {key}"

    def shot(self, path):
        if not self.ensure(): return None
        self.page.screenshot(path=path, full_page=False); return path

    def text(self): return self.page.inner_text("body")[:2000] if self.ensure() else ""
    def title(self): return self.page.title() if self.ensure() else ""

    def new_tab(self, url="about:blank"):
        if not self.ensure(): return "⚠️"
        self.page = self.browser.contexts[0].new_page()
        if url != "about:blank": self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return f"🌐 Nova aba"


class WebActions:
    """Ações web_* sobre o BrowserController do engine (self.browser)."""

    def _web_goto(self, p): return self.browser.goto(p.get("url",""))

    def _web_click(self, p): return self.browser.click_el(p.get("target","") or p.get("description",""))

    def _web_type(self, p): return self.browser.type_in(p.get("field","") or p.get("description",""), p.get("text",""))

    def _web_key(self, p): return self.browser.press(p.get("key","Enter"))

    def _web_screenshot(self, p):
        fp = os.path.join("captures",f"web_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        return f"📸 {fp}" if self.browser.shot(fp) else "❌"

    def _web_read(self, p): return f"🌐 {self.browser.title()}\n{self.browser.text()[:500]}"

    def _web_new_tab(self, p): return self.browser.new_tab(p.get("url","about:blank"))
