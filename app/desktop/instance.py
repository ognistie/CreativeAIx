"""
Uma instancia so do app. Abrir de novo traz a janela que ja existe para a frente, em vez de
criar um segundo agente ouvindo o mesmo microfone e respondendo junto. O nome some com o
processo, entao um app que caiu nao impede de abrir de novo.
"""

from __future__ import annotations

import sys
import time
from typing import Callable, Optional

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "ognistie.AIFarmAgent.instance"
CONNECT_MS = 400
_mutex = None                        # handle vivo ate o processo sair (o Windows solta sozinho)


def claim(name: Optional[str] = None) -> Optional[bool]:
    """Mutex nomeado do Windows: True = somos a primeira instancia; False = ja ha outra (mesmo que ela ainda
    esteja carregando e sem servidor de instancia); None = sem mutex (outro sistema), segue so pelo servidor.
    Dois cliques quase juntos passavam pelos dois testes de servidor e abriam dois apps."""
    global _mutex
    name = name or "Local\\" + SERVER_NAME + ".mutex"     # segue o nome do servidor (os testes trocam)
    if sys.platform != "win32":
        return None
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        return None
    if ctypes.get_last_error() == 183:            # ERROR_ALREADY_EXISTS
        kernel.CloseHandle(ctypes.c_void_p(handle))
        return False
    _mutex = handle
    return True


def notify_running_wait(name: Optional[str] = None, seconds: float = 8.0) -> bool:
    """A outra instancia pode estar subindo: tenta avisar ate ela abrir o servidor."""
    name = name or SERVER_NAME
    end = time.monotonic() + seconds
    while True:
        if notify_running(name):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.2)


def notify_running(name: str = SERVER_NAME) -> bool:
    """-> True se ja ha um app aberto (e ele foi avisado para aparecer)."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(CONNECT_MS):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(CONNECT_MS)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """Fica escutando quem tentar abrir o app de novo."""

    def __init__(self, on_show: Callable[[], None], name: str = SERVER_NAME, parent=None):
        super().__init__(parent)
        self._on_show = on_show
        self._server = QLocalServer(self)
        QLocalServer.removeServer(name)
        self.listening = self._server.listen(name)
        self._server.newConnection.connect(self._accept)

    def _accept(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is not None:
            socket.disconnected.connect(socket.deleteLater)
            self._on_show()
