"""Composição das telas exibidas no display OLED do macropad.

Toda a composição acontece no host: o quadro é montado como imagem 1 bpp
com a mesma fonte do firmware (:mod:`oled_render`) e enviado pela
mensagem ``img``. O firmware só desenha bitmaps, o que mantém a lógica
de apresentação em Python — testável, e idêntica no preview, no simulador
e no hardware.

Telas:

``mapa``   nome do perfil em uma faixa invertida no topo e, abaixo, a
           abreviação de cada tecla desenhada na posição física da grade
           (:data:`~macropad.core.models.KEY_LAYOUT`). É a tela que
           materializa a proposta do TCC: as teclas ficam rotuladas pelo
           display, sem exigir memorização. Uma tecla pode ser destacada
           (invertida) por um instante quando pressionada.
``icone``  a imagem escolhida para o perfil (ou, sem imagem, seu nome
           centralizado, como a tela ``text`` do firmware).
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from PIL import Image

from . import icons, oled_render
from .models import (
    GRID_COLS,
    GRID_ROWS,
    KEY_LAYOUT,
    SCREEN_W,
    SHORT_LABEL_MAX,
    Profile,
)
from .oled_font import CELL_H, CELL_W

# Geometria do mapa de teclas (tamanho de fonte 1: células de 6x8).
_CELL_TEXT_W = SHORT_LABEL_MAX * CELL_W      # 18 px
_COL_PITCH = _CELL_TEXT_W + 6                # 24 px entre colunas
_ROW_PITCH = CELL_H + 4                      # 12 px entre linhas
_MAP_W = GRID_COLS * _COL_PITCH - 6          # 114 px
_MAP_X0 = (SCREEN_W - _MAP_W) // 2           # 7 px de margem
_MAP_Y0 = 14                                 # abaixo da faixa do título
_HEADER_H = CELL_H + 2                       # faixa invertida de 10 px

EMPTY_SHORT = " - "
MODE_SHORT = "MOD"


def keymap_frame(
    name: str,
    shorts: dict[int, str],
    mode_key: int | None = None,
    highlight: int | None = None,
) -> Image.Image:
    """Desenha a tela ``mapa``.

    ``shorts`` associa índice da tecla -> abreviação (até 3 caracteres);
    teclas ausentes aparecem como ``-``. ``highlight`` inverte a célula
    daquela tecla (retorno visual de tecla pressionada).
    """
    frame = oled_render.new_frame()

    title = _ascii(name)[: oled_render.TEXT_COLS]
    oled_render.fill_rect(frame, 0, 0, SCREEN_W, _HEADER_H, 255)
    oled_render.draw_text_centered(frame, 1, title, 1, color=0)

    for key, (row, col) in enumerate(KEY_LAYOUT):
        if key == mode_key:
            text = MODE_SHORT
        else:
            text = _ascii(shorts.get(key, "")) or EMPTY_SHORT
        text = text[:SHORT_LABEL_MAX].center(SHORT_LABEL_MAX)
        x = _MAP_X0 + col * _COL_PITCH
        y = _MAP_Y0 + row * _ROW_PITCH
        if key == highlight:
            oled_render.fill_rect(
                frame, x - 2, y - 2, _CELL_TEXT_W + 4, CELL_H + 4, 255
            )
            oled_render.draw_text(frame, x, y, text, 1, color=0)
        else:
            oled_render.draw_text(frame, x, y, text, 1, color=255)
    return frame


def profile_frame(
    profile: Profile,
    mode_key: int | None,
    display_mode: str = "mapa",
    highlight: int | None = None,
) -> Image.Image:
    """Quadro completo do perfil, conforme o modo de exibição configurado."""
    if display_mode == "icone":
        if profile.icon_path:
            try:
                return icons.load_for_oled(profile.icon_path)
            except (OSError, ValueError):
                pass  # imagem sumiu/corrompeu: cai para o nome
        return title_frame(profile.name)
    shorts = {key: action.display_short for key, action in profile.bindings.items()}
    return keymap_frame(profile.name, shorts, mode_key, highlight)


def title_frame(name: str) -> Image.Image:
    """Nome do perfil centralizado, no maior tamanho em que couber.

    A tela ``text`` do firmware usa sempre tamanho 2 para uma linha, o que
    corta nomes com mais de 10 caracteres. Como aqui o host compõe o quadro,
    nomes longos descem para o tamanho 1 e quebram em até três linhas.
    """
    text = _ascii(name).strip() or "?"
    if oled_render.text_width(text, 2) <= SCREEN_W:
        return oled_render.render_text_lines([text])
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= oled_render.TEXT_COLS:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word[: oled_render.TEXT_COLS]
    if current:
        lines.append(current)
    return oled_render.render_text_lines(lines[:3] or [text[: oled_render.TEXT_COLS]])


def frame_payload(frame: Image.Image) -> str:
    """Empacota um quadro 1 bpp no payload base64 da mensagem ``img``."""
    return base64.b64encode(icons.pack_bits(frame)).decode("ascii")


def frame_from_message(message: dict[str, Any]) -> Image.Image | None:
    """Reconstrói o quadro que o firmware exibiria para uma mensagem ``text``/``img``.

    Usado pelo preview e pelo simulador — por isso precisa reproduzir o
    firmware com exatidão, e não apenas "parecer".
    """
    kind = message.get("t")
    if kind == "text":
        return oled_render.render_text_lines(
            [str(ln) for ln in message.get("lines", [])]
        )
    if kind == "img":
        try:
            return icons.unpack_bits(base64.b64decode(message.get("d", "")))
        except (ValueError, binascii.Error):
            return None
    return None


def _ascii(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


__all__ = [
    "GRID_COLS",
    "GRID_ROWS",
    "frame_from_message",
    "frame_payload",
    "keymap_frame",
    "profile_frame",
]
