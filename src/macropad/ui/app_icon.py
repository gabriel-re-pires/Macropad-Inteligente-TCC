"""Ícone do aplicativo, desenhado em código.

Desenhar em vez de carregar um arquivo evita depender de um recurso
externo no empacotamento e permite gerar qualquer resolução. É a mesma
fonte usada pela janela, pela bandeja e pelo ``.ico`` do executável (ver
``tools/make_icon.py``), então os três nunca divergem.

O desenho é uma miniatura do próprio macropad: o corpo arredondado e a
grade de 3x6 teclas.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap

from ..core.models import KEY_COLS, KEY_ROWS

# O desenho foi ajustado nesta resolução; as demais são proporcionais.
BASE_SIZE = 64

_CORPO = QColor("#14171e")
_BORDA = QColor("#2a2f3a")
_TECLA = QColor("#8cebff")


def render(size: int = BASE_SIZE) -> QPixmap:
    """Desenha o ícone na resolução pedida."""
    escala = size / BASE_SIZE
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    def e(valor: float) -> int:
        """Converte uma medida do desenho base para a resolução pedida."""
        return round(valor * escala)

    painter.setBrush(QBrush(_CORPO))
    painter.setPen(_BORDA)
    painter.drawRoundedRect(e(2), e(8), e(60), e(48), e(10), e(10))

    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(_TECLA))
    for row in range(KEY_ROWS):
        for col in range(KEY_COLS):
            painter.drawRoundedRect(
                e(8 + col * 9), e(16 + row * 12), e(6), e(8), e(2), e(2)
            )
    painter.end()
    return pixmap


def icon() -> QIcon:
    """Ícone com as resoluções que o Windows costuma pedir."""
    resultado = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        resultado.addPixmap(render(size))
    return resultado
