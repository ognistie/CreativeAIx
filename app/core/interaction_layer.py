"""
Interaction Layer — Camada de abstracao de interacao.
Tenta a estrategia mais confiavel primeiro, faz fallback automatico.
Nivel 1: API/Codigo → Nivel 2: UIA → Nivel 3: Vision
"""

from core.uia_driver import UIADriver
import logging

logger = logging.getLogger("interaction_layer")


class InteractionLayer:
    def __init__(self, vision_engine=None):
        self.uia = UIADriver()
        self.vision = vision_engine

    def click_element(self, app_name, element_desc, *, authorize=None):
        """Resolve e clica via UIA. O executor controla o fallback por visão."""
        if authorize is None:
            return {"success": False, "blocked": True, "error": "Porta de efeitos indisponível."}
        return self.uia.try_click(app_name, element_desc, authorize=authorize)

    def type_in_field(self, app_name, field_desc, text, *, stopped=lambda: False):
        """Resolve a edição via UIA. Visão, quando disponível, passa pelo executor."""
        return self.uia.try_type(app_name, field_desc, text, stopped=stopped)

    def get_app_state(self, app_name):
        """Identifica o estado atual de um app."""
        # UIA
        state = self.uia.read_app_state(app_name)
        if state.get("identified"):
            return state

        # Fallback: OCR local
        try:
            from core.ocr_local import read_screen_text
            texts = read_screen_text()
            return {"identified": bool(texts), "method": "OCR", "visible_texts": [t["text"] for t in texts]}
        except:
            return {"identified": False}
