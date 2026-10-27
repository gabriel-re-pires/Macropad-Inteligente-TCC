"""Widget que reproduz o conteúdo do display OLED do macropad.

Usado tanto no preview da janela principal quanto no simulador. Os quadros
são reconstruídos a partir das mesmas mensagens do protocolo ("text" e
"img") com a mesma fonte e o mesmo algoritmo do firmware
(:mod:`macropad.core.oled_render`), de modo que o que se vê aqui é, pixel a
pixel, o que o SSD1306 mostra.
"""

from __future__ import annotations

from typing import Any

from PIL import Image
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel

from ..core import display, oled_render
from ..core.models import SCREEN_H, SCREEN_W

_SCALE = 2  # fator de ampliação do preview


class OledPreview(QLabel):
    """QLabel que exibe um quadro 1 bpp com o visual do OLED."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(SCREEN_W * _SCALE + 16, SCREEN_H * _SCALE + 16)
        self.setStyleSheet(
            "background-color: #10131a; border: 2px solid #2a2f3a; border-radius: 6px;"
        )
        self.show_frame(oled_render.render_text_lines(["macropad"]))

    def show_message(self, message: dict[str, Any]) -> None:
        frame = display.frame_from_message(message)
        if frame is not None:
            self.show_frame(frame)

    def show_frame(self, frame: Image.Image) -> None:
        # Pixels acesos em ciano, lembrando os OLEDs SSD1306 mais comuns.
        rgb = Image.new("RGB", frame.size, (16, 19, 26))
        lit = Image.new("RGB", frame.size, (140, 235, 255))
        rgb.paste(lit, mask=frame)
        data = rgb.tobytes()
        image = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            SCREEN_W * _SCALE, SCREEN_H * _SCALE
        )
        canvas = QPixmap(self.size())
        canvas.fill("#10131a")
        painter = QPainter(canvas)
        painter.drawPixmap(8, 8, pixmap)
        painter.end()
        self.setPixmap(canvas)
