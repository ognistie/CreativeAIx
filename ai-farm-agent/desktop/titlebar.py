"""Barra de titulo nativa na cor do app (Windows 11).

Fica nativa de proposito: arrastar, encaixar (Win+setas, layouts) e redimensionar continuam
iguais ao resto do Windows. So a cor muda: o fundo da barra, o texto e a borda acompanham a
paleta escolhida no Harness, sem a faixa branca separando a barra do conteudo.
Em Windows sem suporte (10) a chamada falha em silencio e a barra fica padrao.
"""

from __future__ import annotations

import ctypes
import sys

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def _colorref(hex_color: str, fallback: int) -> int:
    h = (hex_color or "").strip().lstrip("#")
    if len(h) == 8:                      # #AARRGGBB do Qt: ignora o alfa
        h = h[2:]
    if len(h) != 6:
        return fallback
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return fallback
    return (b << 16) | (g << 8) | r      # COLORREF e BGR


def is_dark(hex_color: str) -> bool:
    """Luminancia relativa abaixo de 0.4: barra escura, texto claro e controles em modo escuro."""
    h = (hex_color or "").strip().lstrip("#")
    if len(h) == 8:
        h = h[2:]
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return False
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2] < 0.4


def style_title_bar(window, caption: str = "#FBF7F4", text: str = "") -> bool:
    if sys.platform != "win32" or window is None:
        return False
    dark = is_dark(caption)
    text = text or ("#F4F4F7" if dark else "#1D1D1F")
    try:
        handle = ctypes.c_void_p(int(window.winId()))
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        set_attribute.restype = ctypes.c_long

        def apply(attribute: int, value: int) -> None:
            data = ctypes.c_uint(value)
            set_attribute(handle, attribute, ctypes.byref(data), ctypes.sizeof(data))

        bar = _colorref(caption, 0x00F4F7FB)
        apply(DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
        apply(DWMWA_CAPTION_COLOR, bar)
        apply(DWMWA_BORDER_COLOR, bar)               # sem linha cinza em volta
        apply(DWMWA_TEXT_COLOR, _colorref(text, 0x001F1D1D))
        return True
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        print(f"[desktop] barra de titulo nativa sem personalizacao: {exc}")
        return False
