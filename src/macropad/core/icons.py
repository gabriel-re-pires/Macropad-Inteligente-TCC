"""Conversão de imagens para o formato do display OLED (SSD1306, 1 bpp).

O display de 0,96" tem 128x64 pixels monocromáticos, portanto qualquer
imagem escolhida pelo usuário precisa ser reduzida e convertida para
1 bit por pixel. Usa-se difusão de erro (Floyd–Steinberg) para preservar
o máximo de detalhe; na prática, ícones simples e de alto contraste
(pictogramas, logos "flat") produzem o melhor resultado — a interface
orienta o usuário nesse sentido.

Formato de empacotamento ("xbm1"): varredura por linhas, 8 pixels por
byte, bit mais significativo = pixel mais à esquerda, 1 = pixel aceso.
"""

from __future__ import annotations

import base64
from pathlib import Path

from PIL import Image

from .models import SCREEN_H, SCREEN_W


def load_for_oled(path: str | Path, invert: bool = False) -> Image.Image:
    """Carrega uma imagem e a converte para 1 bpp no tamanho do display.

    A imagem é redimensionada mantendo a proporção e centralizada sobre
    um fundo preto de 128x64.
    """
    img = Image.open(path).convert("RGBA")
    # Achata transparência sobre fundo preto (comum em PNGs de ícones).
    background = Image.new("RGBA", img.size, (0, 0, 0, 255))
    img = Image.alpha_composite(background, img).convert("L")

    img.thumbnail((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (SCREEN_W, SCREEN_H), 0)
    offset = ((SCREEN_W - img.width) // 2, (SCREEN_H - img.height) // 2)
    canvas.paste(img, offset)

    mono = canvas.convert("1")  # Floyd–Steinberg por padrão
    if invert:
        mono = mono.point(lambda p: 255 - p)
    return mono


def pack_bits(mono: Image.Image) -> bytes:
    """Empacota uma imagem 1 bpp no formato ``xbm1`` (MSB primeiro)."""
    if mono.size != (SCREEN_W, SCREEN_H):
        raise ValueError(f"imagem deve ter {SCREEN_W}x{SCREEN_H}, tem {mono.size}")
    pixels = mono.load()
    if pixels is None:  # pragma: no cover — imagem válida sempre carrega
        raise ValueError("não foi possível acessar os pixels da imagem")
    data = bytearray()
    for y in range(SCREEN_H):
        for x0 in range(0, SCREEN_W, 8):
            byte = 0
            for bit in range(8):
                if pixels[x0 + bit, y]:
                    byte |= 0x80 >> bit
            data.append(byte)
    return bytes(data)


def icon_payload(path: str | Path) -> str:
    """Converte a imagem do perfil no payload base64 enviado ao firmware."""
    return base64.b64encode(pack_bits(load_for_oled(path))).decode("ascii")


def unpack_bits(data: bytes) -> Image.Image:
    """Inverso de :func:`pack_bits` (usado no preview e no simulador)."""
    expected = SCREEN_W * SCREEN_H // 8
    if len(data) != expected:
        raise ValueError(f"payload deve ter {expected} bytes, tem {len(data)}")
    mono = Image.new("1", (SCREEN_W, SCREEN_H), 0)
    pixels = mono.load()
    if pixels is None:  # pragma: no cover — imagem recém-criada sempre carrega
        raise ValueError("não foi possível acessar os pixels da imagem")
    i = 0
    for y in range(SCREEN_H):
        for x0 in range(0, SCREEN_W, 8):
            byte = data[i]
            i += 1
            for bit in range(8):
                if byte & (0x80 >> bit):
                    pixels[x0 + bit, y] = 255
    return mono
