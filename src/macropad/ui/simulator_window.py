"""Janela do dispositivo virtual (simulador).

Reproduz o macropad físico: o "display" OLED em cima e as 18 teclas
embaixo. Clicar em uma tecla gera os mesmos eventos de protocolo que o
hardware geraria — todo o restante do software se comporta de forma
idêntica.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.models import KEY_COLS, KEY_COUNT
from ..device.simulator import SimulatorLink
from .oled_preview import OledPreview


class SimulatorWindow(QWidget):
    def __init__(self, link: SimulatorLink) -> None:
        super().__init__()
        self.setWindowTitle("Macropad — Simulador")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self._link = link

        layout = QVBoxLayout(self)
        title = QLabel("Dispositivo virtual")
        title.setObjectName("panelTitle")
        layout.addWidget(title, alignment=Qt.AlignHCenter)

        self._oled = OledPreview()
        layout.addWidget(self._oled, alignment=Qt.AlignHCenter)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i in range(KEY_COUNT):
            button = QPushButton(str(i + 1))
            button.setObjectName("keyButton")
            button.setFixedSize(56, 48)
            button.clicked.connect(lambda checked=False, k=i: self._link.press_key(k))
            grid.addWidget(button, i // KEY_COLS, i % KEY_COLS)
        layout.addLayout(grid)

        # O display virtual espelha tudo o que o host envia ao "firmware".
        link.on_display = self._oled.show_message

    def closeEvent(self, event) -> None:  # noqa: N802 — API Qt
        self._link.on_display = None
        super().closeEvent(event)
