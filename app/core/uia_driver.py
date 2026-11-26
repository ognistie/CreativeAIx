"""
UIA Driver — Acessa a arvore de acessibilidade do Windows via pywinauto.
Permite interagir com apps por nome/tipo de controle, nao por pixel.
"""

import logging
import re
import time

logger = logging.getLogger("uia_driver")


def paste_edit(hwnd, wrapper, text: str, stopped) -> dict:
    """Foca um campo Edit identificado e cola texto literal, sem gerar teclas do conteúdo."""
    from core.automation import _is_front, _shell_surface
    from core.browser_uia import element_state, focused_state
    from core.clipboard import paste_text
    state = element_state(wrapper.element_info.element)
    if state is None or state[2] != 50004 or not _is_front(hwnd) or _shell_surface(hwnd) or stopped():
        return {"success": False, "error": "O alvo não é um campo de edição confirmado."}
    wrapper.set_focus()
    focused = focused_state()
    if not focused or focused[0] != state[0] or not _is_front(hwnd) or stopped():
        return {"success": False, "error": "O foco mudou antes da digitação."}
    try:
        paste_text(text)
    except Exception:
        return {"success": False, "effect_started": True, "error": "Resultado da colagem incerto."}
    return {"success": True, "method": "UIA"}

# Mapa de controles conhecidos por app
CONTROL_MAPS = {
    "teams": {
        "chat": {"title": "Chat", "control_type": "TreeItem", "alt_titles": ["Chat", "Bate-papo"]},
        "activity": {"title": "Activity", "control_type": "TreeItem", "alt_titles": ["Atividade"]},
        "search": {"title": "Search", "control_type": "Edit", "alt_titles": ["Pesquisar"]},
        "message_box": {"title": "Type a new message", "control_type": "Edit", "alt_titles": ["Digite uma nova mensagem", "Digite uma mensagem"]},
        "send": {"title": "Send", "control_type": "Button", "alt_titles": ["Enviar"]},
    },
    "excel": {
        "name_box": {"title": "Name Box", "control_type": "Edit"},
        "formula_bar": {"title": "Formula Bar", "control_type": "Edit"},
    },
    "vscode": {
        "command_palette": {"hotkey": ["ctrl", "shift", "p"]},
        "terminal": {"hotkey": ["ctrl", "`"]},
        "explorer": {"hotkey": ["ctrl", "shift", "e"]},
        "new_file": {"hotkey": ["ctrl", "n"]},
    },
    "notepad": {
        "text_area": {"title": "", "control_type": "Edit"},
    },
    "word": {
        "blank_doc": {"title": "Blank document", "control_type": "Button", "alt_titles": ["Documento em branco"]},
    },
}


class UIADriver:
    def connect_app(self, app_name):
        """Conecta a um app pelo titulo da janela."""
        try:
            from pywinauto import Application
            app = Application(backend="uia").connect(title_re=f".*{re.escape(app_name)}.*", timeout=5)
            return {"success": True, "app": app}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def try_click(self, app_name, element_desc, *, authorize):
        """Resolve o controle antes de pedir autorização e despacha uma vez."""
        conn = self.connect_app(app_name)
        if not conn["success"]:
            return {**conn, "effect_started": False}

        app = conn["app"]
        dispatched = False
        try:
            window = app.top_window()
            window.set_focus()
            time.sleep(0.3)

            def click(el, method):
                nonlocal dispatched
                from core.browser_uia import element_state
                wrapper = el.wrapper_object()
                def identity():
                    state = element_state(wrapper.element_info.element)
                    return (window.handle, state) if state is not None else None

                reason = authorize(wrapper.window_text(), identity)
                if reason:
                    return {"success": False, "blocked": True, "error": reason}
                from core.automation import _is_front
                if not _is_front(window.handle):
                    return {"success": False, "blocked": True, "error": "Foco da janela não confirmado."}
                dispatched = True
                wrapper.click_input()
                return {"success": True, "method": method}

            app_key = app_name.lower()
            for map_key in CONTROL_MAPS:
                if map_key in app_key or app_key in map_key:
                    controls = CONTROL_MAPS[map_key]
                    for ctrl_name, ctrl_info in controls.items():
                        if element_desc.lower() in ctrl_name or ctrl_name in element_desc.lower():
                            # Hotkey
                            if "hotkey" in ctrl_info:
                                import pyautogui
                                from core.automation import _effect_window, _is_front
                                reason = authorize(ctrl_name, _effect_window)
                                if reason:
                                    return {"success": False, "blocked": True, "error": reason}
                                if not _is_front(window.handle):
                                    return {"success": False, "blocked": True, "error": "Foco da janela não confirmado."}
                                dispatched = True
                                pyautogui.hotkey(*ctrl_info["hotkey"])
                                return {"success": True, "method": "hotkey"}

                            # UIA click com titulos alternativos
                            titles = [ctrl_info["title"]] + ctrl_info.get("alt_titles", [])
                            ctrl_type = ctrl_info.get("control_type", "")
                            for title in titles:
                                criteria = {"control_type": ctrl_type} if ctrl_type else {}
                                el = window.child_window(title_re=f".*{re.escape(title)}.*", found_index=0, **criteria)
                                if el.exists(timeout=2):
                                    return click(el, "control_map")

            el = window.child_window(title_re=f".*{re.escape(element_desc)}.*", found_index=0)
            if el.exists(timeout=3):
                return click(el, "generic_search")
            return {"success": False, "effect_started": False, "hwnd": window.handle,
                    "error": f"Elemento '{element_desc}' nao encontrado via UIA"}

        except Exception as e:
            return {"success": False, "effect_started": dispatched, "error": str(e)}

    def try_type(self, app_name, field_desc, text, *, stopped=lambda: False):
        """Tenta digitar em um campo via UIA."""
        if not all(isinstance(value, str) and value for value in (app_name, field_desc, text)):
            return {"success": False, "error": "Aplicativo, campo ou texto ausente."}
        conn = self.connect_app(app_name)
        if not conn["success"]:
            return conn

        try:
            window = conn["app"].top_window()
            window.set_focus()
            time.sleep(0.3)

            app_key = app_name.lower()
            titles = []
            for map_key in CONTROL_MAPS:
                if map_key in app_key or app_key in map_key:
                    for ctrl_name, ctrl_info in CONTROL_MAPS[map_key].items():
                        if field_desc.lower() in ctrl_name or ctrl_name in field_desc.lower():
                            titles.extend([ctrl_info.get("title", ""), *ctrl_info.get("alt_titles", [])])
            for title in dict.fromkeys([*(title for title in titles if title), field_desc]):
                if stopped():
                    return {"success": False, "error": "Tarefa cancelada."}
                edit = window.child_window(title_re=f".*{re.escape(title)}.*", control_type="Edit")
                if edit.exists(timeout=2):
                    return paste_edit(window.handle, edit.wrapper_object(), text, stopped)
            return {"success": False, "effect_started": False, "hwnd": window.handle,
                    "error": f"Campo '{field_desc}' não encontrado via UIA"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_app_state(self, app_name):
        """Le o estado atual de um app via UIA."""
        conn = self.connect_app(app_name)
        if not conn["success"]:
            return {"identified": False}

        try:
            window = conn["app"].top_window()
            title = window.window_text()
            visible = []
            for ctrl in window.descendants():
                try:
                    t = ctrl.window_text()
                    if t and len(t) < 200:
                        visible.append(t)
                except:
                    pass
            return {"identified": True, "method": "UIA", "window_title": title, "visible_texts": visible[:50]}
        except Exception as e:
            return {"identified": False, "error": str(e)}

    def list_controls(self, app_name):
        """Debug: lista todos os controles de um app."""
        conn = self.connect_app(app_name)
        if not conn["success"]:
            return conn["error"]
        window = conn["app"].top_window()
        window.print_control_identifiers()
        return "Controles impressos no console."
