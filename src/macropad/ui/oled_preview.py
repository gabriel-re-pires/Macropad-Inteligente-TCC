"""Widget que reproduz o conteúdo do display OLED do macropad.

Usado tanto no preview da janela principal quanto no simulador. Renderiza
os mesmos frames do protocolo ("text" e "img") em um canvas 128x64
ampliado, imitando a aparência do SSD1306.
"""

from __future__ import annotations

import base64
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel

from ..core import icons
from ..core.models import SCREEN_H, SCREEN_W

_SCALE = 2  # fator de ampliação do preview


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        # Sem a fonte do sistema: a embutida do Pillow tem tamanho fixo,
        # mas o preview continua legível.
        return ImageFont.load_default()


def render_text_frame(lines: list[str]) -> Image.Image:
    """Aproxima a renderização de texto que o firmware fará no display."""
    frame = Image.new("1", (SCREEN_W, SCREEN_H), 0)
    draw = ImageDraw.Draw(frame)
    lines = [ln for ln in lines if ln][:3] or [" "]
    size = 22 if len(lines) == 1 else 14
    font = _font(size)
    total_h = 0
    heights: list[int] = []
    for ln in lines:
        box = draw.textbbox((0, 0), ln, font=font)
        # textbbox devolve float; as posições no display são em pixels.
        heights.append(int(box[3] - box[1]))
        total_h += int(box[3] - box[1]) + 4
    y: int = max((SCREEN_H - total_h) // 2, 0)
    for ln, h in zip(lines, heights, strict=True):
        box = draw.textbbox((0, 0), ln, font=font)
        w = box[2] - box[0]
        draw.text(((SCREEN_W - w) // 2 - box[0], y - box[1]), ln, fill=255, font=font)
        y += h + 4
    return frame


def frame_from_message(message: dict[str, Any]) -> Image.Image | None:
    """Converte uma mensagem de display do protocolo em um frame 1 bpp."""
    kind = message.get("t")
    if kind == "text":
        return render_text_frame(list(message.get("lines", [])))
    if kind == "img":
        try:
            return icons.unpack_bits(base64.b64decode(message.get("d", "")))
        except (ValueError, base64.binascii.Error):
            return None
    return None


class OledPreview(QLabel):
    """QLabel que exibe um frame 1 bpp com o visual do OLED."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(SCREEN_W * _SCALE + 16, SCREEN_H * _SCALE + 16)
        self.setStyleSheet(
            "background-color: #10131a; border: 2px solid #2a2f3a; border-radius: 6px;"
        )
        self.show_frame(render_text_frame(["macropad"]))

    def show_message(self, message: dict[str, Any]) -> None:
        frame = frame_from_message(message)
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
