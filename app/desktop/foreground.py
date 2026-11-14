"""
Quem esta em primeiro plano no Windows, sem Qt.

Usado pelo mini chat nas duas interfaces: `window_mode.py` (Qt, o proprio processo) e o servidor da
interface Tauri (`server.py`), onde as janelas sao de outro processo (a casca) e o PID dela chega por
CREATIVE_AIX_SHELL_PID.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import Iterable, Optional

# Janelas do proprio Windows que nao contam como "o agente foi para outro app"
SHELL_CLASSES = {
    "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
    "Windows.UI.Core.CoreWindow", "ForegroundStaging", "MultitaskingViewFrame",
    "XamlExplorerHostIslandWindow", "TaskSwitcherWnd", "NotifyIconOverflowWindow",
    "TopLevelWindowForOverflowXamlIsland",
}


def foreign_foreground(own_pids: Optional[Iterable[int]] = None) -> bool:
    """True se a janela em primeiro plano e de outro programa (nem nosso, nem do shell)."""
    if sys.platform != "win32":
        return False
    mine = set(own_pids) if own_pids is not None else {os.getpid()}
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    if not h:
        return False
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value in mine:
        return False
    cls = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, cls, 256)
    if cls.value in SHELL_CLASSES:
        return False
    return bool(u.IsWindowVisible(h)) and u.GetWindowTextLengthW(h) > 0


def shell_pids() -> set:
    """PIDs que sao 'nossos' no modo Tauri: o nucleo e a casca (CREATIVE_AIX_SHELL_PID)."""
    pids = {os.getpid()}
    raw = os.environ.get("CREATIVE_AIX_SHELL_PID", "")
    if raw.isdigit():
        pids.add(int(raw))
    return pids
