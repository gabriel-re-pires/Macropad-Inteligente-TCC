"""Grade visual das 18 teclas do macropad.

Cada botão mostra o rótulo da ação configurada no perfil em edição.
Clicar em uma tecla abre o editor de ações. A tecla de modo recebe um
destaque visual.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

from ..core.models import KEY_COLS, KEY_COUNT, Profile


class KeyGrid(QWidget):
    key_clicked = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        layout = QGridLayout(self)
        layout.setSpacing(8)
        self._buttons: list[QPushButton] = []
        for i in range(KEY_COUNT):
            button = QPushButton()
            button.setObjectName("keyButton")
            button.setMinimumSize(96, 72)
            button.clicked.connect(lambda checked=False, k=i: self.key_clicked.emit(k))
            layout.addWidget(button, i // KEY_COLS, i % KEY_COLS)
            self._buttons.append(button)

    def refresh(self, profile: Profile | None, mode_key: int | None) -> None:
        for i, button in enumerate(self._buttons):
            action = profile.action_for(i) if profile else None
            is_mode = i == mode_key
            if is_mode:
                text = f"{i + 1}\nMODO"
            elif action is not None:
                label = action.label or action.type
                text = f"{i + 1}\n{label}"
            else:
                text = f"{i + 1}\n—"
            button.setText(text)
            button.setProperty("modeKey", is_mode)
            button.setProperty("bound", action is not None)
            # Reaplica o estilo após mudar as propriedades dinâmicas.
            button.style().unpolish(button)
            button.style().polish(button)
            tooltip = "Tecla de modo: alterna o perfil ativo" if is_mode else (
                action.label or "" if action else "Sem ação — clique para configurar"
            )
            button.setToolTip(tooltip)
