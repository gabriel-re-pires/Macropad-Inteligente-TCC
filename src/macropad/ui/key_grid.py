"""Grade visual das 18 teclas do macropad.

Cada botão mostra o rótulo da ação configurada no perfil em edição.
Clicar em uma tecla abre o editor de ações; o botão direito abre um menu
com as operações rápidas. A tecla de modo recebe um destaque visual, e a
tecla pressionada no dispositivo acende por um instante.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

from ..core.models import KEY_COLS, KEY_COUNT, Profile


class KeyGrid(QWidget):
    key_clicked = Signal(int)
    key_menu_requested = Signal(int)

    # Tempo que a tecla fica acesa após ser pressionada no dispositivo.
    FLASH_MS = 280

    def __init__(self) -> None:
        super().__init__()
        layout = QGridLayout(self)
        layout.setSpacing(8)
        self._buttons: list[QPushButton] = []
        self._flash_timers: dict[int, QTimer] = {}
        for i in range(KEY_COUNT):
            button = QPushButton()
            button.setObjectName("keyButton")
            button.setMinimumSize(96, 72)
            button.setProperty("pressed", False)
            button.clicked.connect(lambda checked=False, k=i: self.key_clicked.emit(k))
            button.setContextMenuPolicy(Qt.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda _pos, k=i: self.key_menu_requested.emit(k)
            )
            layout.addWidget(button, i // KEY_COLS, i % KEY_COLS)
            self._buttons.append(button)

    # ------------------------------------------------------------- destaque

    def flash(self, key: int) -> None:
        """Acende a tecla recém-pressionada no macropad (ou no simulador)."""
        if not 0 <= key < len(self._buttons):
            return
        self._set_pressed(key, True)
        timer = self._flash_timers.get(key)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda k=key: self._set_pressed(k, False))
            self._flash_timers[key] = timer
        # start() reinicia a contagem: teclas repetidas seguem acesas.
        timer.start(self.FLASH_MS)

    def _set_pressed(self, key: int, pressed: bool) -> None:
        button = self._buttons[key]
        button.setProperty("pressed", pressed)
        _repolish(button)

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
            _repolish(button)
            tooltip = "Tecla de modo: alterna o perfil ativo" if is_mode else (
                action.label or "" if action else "Sem ação — clique para configurar"
            )
            button.setToolTip(tooltip)


def _repolish(button: QPushButton) -> None:
    """Reaplica a folha de estilo após mudar uma propriedade dinâmica."""
    button.style().unpolish(button)
    button.style().polish(button)
