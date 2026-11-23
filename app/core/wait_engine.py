"""
Wait Engine v2 — Esperas condicionais com busca flexivel de janela.
Busca por titulo parcial usando pygetwindow (mais confiavel que pywinauto para detecao).
"""

import re
import time

MAX_WAIT_S = 30.0     # o timeout vem do plano (escrito pelo modelo): nunca mais que isso


def _cap(timeout, default):
    try:
        value = float(timeout)
    except (TypeError, ValueError):
        value = float(default)
    return max(0.5, min(value, MAX_WAIT_S))


def _stopped(should_stop) -> bool:
    try:
        return bool(should_stop and should_stop())
    except Exception:
        return False


def wait_for_window(title, timeout=15, should_stop=None):
    """Espera ate que uma janela com o titulo apareca. Busca parcial. Para no Parar e em MAX_WAIT_S."""
    timeout = _cap(timeout, 15)
    title = str(title or "")
    start = time.time()
    search = title.lower()
    while time.time() - start < timeout:
        try:
            import pygetwindow as gw
            for w in gw.getAllWindows():
                if w.visible and w.title and search in w.title.lower():
                    return {"success": True, "window_title": w.title, "elapsed": round(time.time() - start, 1)}
        except Exception:
            pass
        if _stopped(should_stop):
            return {"success": False, "error": "Cancelado durante a espera."}
        time.sleep(0.5)

    # Fallback: tenta pywinauto (titulo escapado: vem do plano, nao e expressao regular)
    try:
        from pywinauto import Application
        app = Application(backend="uia").connect(title_re=".*" + re.escape(title) + ".*", timeout=3)
        return {"success": True, "elapsed": round(time.time() - start, 1)}
    except:
        pass

    return {"success": False, "error": "Timeout: '" + title + "' nao apareceu em " + str(timeout) + "s"}


def wait_for_element(app_name, element_title, timeout=10, should_stop=None):
    """Espera ate que um elemento apareca numa janela. Para no Parar e em MAX_WAIT_S."""
    timeout = _cap(timeout, 10)
    start = time.time()
    while time.time() - start < timeout:
        try:
            from pywinauto import Application
            app = Application(backend="uia").connect(title_re=".*" + re.escape(str(app_name or "")) + ".*", timeout=1)
            window = app.top_window()
            el = window.child_window(title_re=".*" + re.escape(str(element_title or "")) + ".*", found_index=0)
            if el.exists():
                return {"success": True, "elapsed": round(time.time() - start, 1)}
        except Exception:
            pass
        if _stopped(should_stop):
            return {"success": False, "error": "Cancelado durante a espera."}
        time.sleep(0.5)
    return {"success": False, "error": "Timeout: '" + element_title + "' nao encontrado em " + str(timeout) + "s"}


def wait_for_condition(condition, target, timeout=10):
    if condition == "window_exists":
        return wait_for_window(target, timeout)
    elif condition == "element_visible":
        parts = target.split("::") if "::" in target else ["", target]
        return wait_for_element(parts[0], parts[-1], timeout)
    else:
        time.sleep(min(_cap(timeout, 3), 3))
        return {"success": True, "method": "fixed_wait"}