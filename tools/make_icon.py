"""Gera o ``.ico`` do executável a partir do ícone desenhado em código.

Usa o mesmo :mod:`macropad.ui.app_icon` da janela e da bandeja, para que
o ícone do executável nunca divirja do que aparece no aplicativo.

    .venv\\Scripts\\python tools\\make_icon.py [destino.ico]
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

# Renderizar não exige uma sessão gráfica.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QBuffer
from PySide6.QtGui import QGuiApplication

from macropad.ui import app_icon

# Resoluções que o Explorer usa (ícone pequeno na barra até visão gigante).
SIZES = (16, 24, 32, 48, 64, 128, 256)
DEFAULT_OUTPUT = Path("build") / "macropad.ico"


def _to_pillow(size: int) -> Image.Image:
    """Renderiza no Qt e devolve a imagem equivalente no Pillow."""
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    if not app_icon.render(size).save(buffer, "PNG"):
        raise RuntimeError(f"falha ao renderizar o ícone em {size}px")
    return Image.open(io.BytesIO(buffer.data().data())).convert("RGBA")


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    destino.parent.mkdir(parents=True, exist_ok=True)

    QGuiApplication([sys.argv[0]])
    maior = _to_pillow(max(SIZES))
    # O Pillow monta o .ico multirresolução a partir da maior imagem.
    maior.save(destino, format="ICO", sizes=[(s, s) for s in SIZES])

    print(f"ícone gravado em {destino} ({destino.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
