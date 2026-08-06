"""Ponte entre threads de backend e a thread da interface Qt.

Os callbacks do enlace serial e do motor de ações executam em threads
próprias; emitir sinais Qt a partir delas é seguro (a conexão vira
"queued" automaticamente) e entrega os eventos na thread da UI.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal


class DeviceBridge(QObject):
    message = Signal(dict)          # mensagem decodificada do dispositivo
    state = Signal(bool, str)       # (conectado?, nome da porta)
    action_error = Signal(str)      # erro reportado pelo ActionRunner
    profile_changed = Signal(object)  # Profile ativado (pela tecla de modo ou UI)

    def emit_message(self, message: dict[str, Any]) -> None:
        self.message.emit(message)

    def emit_state(self, connected: bool, port: str) -> None:
        self.state.emit(connected, port)
