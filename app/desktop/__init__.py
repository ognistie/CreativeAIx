"""
Creative AIx — Camada Desktop.

A interface React (ui/dist) roda em janelas Qt com QtWebEngine e fala com o nucleo por um servidor local
(JSON-RPC sobre WebSocket com token). Nao modifica nenhum agente, nem core/, nem memory/.

Pontos de entrada:
- `desktop.web_host:run()` abre a janela principal e o mini chat.
- `main.py` (raiz) delega a este modulo.
"""

__version__ = "1.0.0"
