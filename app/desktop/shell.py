"""
Pecas do app desktop usadas pelo host (desktop/web_host.py) e pelos scripts: identidade na barra de
tarefas, fonte do sistema, icone da marca, encerramento por sinal e encerramento com limite de tempo.
"""

from __future__ import annotations

import os
import signal
import threading
import time

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap

APP_ID = "ognistie.AIFarmAgent"       # o atalho (scripts/install_shortcuts.py) usa a mesma identidade
SHUTDOWN_LIMIT_S = 5.0                # limpeza que travar nao segura o agente vivo


def _setup_fonts(app: QGuiApplication) -> None:
    """Fonte do sistema (Segoe UI Variable no Windows 11). Se nao existir,
    o Qt escolhe a sans-serif padrao."""
    # Windows 10 nao tem Segoe UI Variable; Cascadia vem com o Terminal.
    QFont.insertSubstitutions("Segoe UI Variable Text", ["Segoe UI Variable", "Segoe UI"])
    QFont.insertSubstitutions("Segoe UI Variable Display", ["Segoe UI Variable", "Segoe UI"])
    QFont.insertSubstitutions("Cascadia Mono", ["Consolas", "Courier New"])
    default = QFont("Segoe UI Variable Text", 10)
    default.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(default)


def brand_pixmap(size: int) -> QPixmap:
    """A marca do app (quatro quadrados, o ultimo na cor de destaque) desenhada num tamanho."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    pad = size * 0.08
    gap = max(1.0, size * 0.10)
    cell = (size - 2 * pad - gap) / 2
    for i in range(4):
        x = pad + (i % 2) * (cell + gap)
        y = pad + (i // 2) * (cell + gap)
        p.setBrush(QColor("#0A7CFF" if i == 3 else "#1D1D1F"))
        p.drawRoundedRect(QRectF(x, y, cell, cell), cell * 0.28, cell * 0.28)
    p.end()
    return pix


def _brand_icon() -> QIcon:
    """Icone da janela/barra de tarefas."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        icon.addPixmap(brand_pixmap(size))
    return icon


def _quit_on_signals(app: QGuiApplication) -> None:
    """Ctrl+C e fechar o terminal encerram o app. O loop do Qt nao devolve o controle ao Python
    sozinho, entao o timer da a chance de o sinal ser atendido."""
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: app.quit())
    tick = QTimer(app)
    tick.timeout.connect(lambda: None)
    tick.start(200)


def _shutdown(bridge) -> None:
    """Fechar o app: microfone, voz, sessao paga e tarefa param aqui. Se algo travar, o limite
    encerra o processo de qualquer jeito."""
    def give_up() -> None:
        time.sleep(SHUTDOWN_LIMIT_S)
        os._exit(0)
    threading.Thread(target=give_up, daemon=True, name="shutdown-limit").start()
    try:
        bridge.shutdown()
    except Exception as exc:
        print(f"[desktop] falha ao encerrar: {type(exc).__name__}: {exc}")
