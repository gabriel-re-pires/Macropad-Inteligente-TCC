"""Gera o executável distribuível do Macropad Configurator.

    .venv\\Scripts\\python tools\\build_exe.py

Produz ``dist/MacropadConfigurator.exe`` — um arquivo único, sem console,
que roda em um Windows sem Python instalado. É o que se leva para a
apresentação.

Detalhes que o empacotamento exige:

* ``keyring`` e ``pynput`` escolhem seu backend em tempo de execução,
  importando módulos que o PyInstaller não vê na análise estática; por
  isso são coletados por inteiro.
* O ícone é gerado antes, a partir do mesmo desenho usado pela janela
  (ver ``make_icon.py``).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ICONE = RAIZ / "build" / "macropad.ico"
NOME = "MacropadConfigurator"


def _run(argv: list[str], descricao: str) -> None:
    print(f"\n>>> {descricao}")
    resultado = subprocess.run(argv, cwd=RAIZ)
    if resultado.returncode != 0:
        raise SystemExit(f"falhou: {descricao} (código {resultado.returncode})")


def main() -> int:
    if shutil.which("pyinstaller") is None and not (
        Path(sys.executable).with_name("pyinstaller.exe").exists()
    ):
        raise SystemExit(
            'PyInstaller não encontrado. Instale com: pip install -e ".[dev]"'
        )

    _run([sys.executable, str(RAIZ / "tools" / "make_icon.py")], "gerando o ícone")

    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            NOME,
            "--icon",
            str(ICONE),
            "--paths",
            str(RAIZ / "src"),
            # Backends resolvidos em tempo de execução.
            "--collect-submodules",
            "keyring.backends",
            "--collect-submodules",
            "pynput",
            # O esptool resolve a classe do chip pelo nome e lê o stub de
            # gravação de arquivos JSON de dados — nada disso aparece na
            # análise estática do PyInstaller.
            "--collect-submodules",
            "esptool",
            "--collect-data",
            "esptool",
            # Módulos Qt pesados que o aplicativo não usa.
            "--exclude-module",
            "PySide6.QtWebEngineCore",
            "--exclude-module",
            "PySide6.QtWebEngineWidgets",
            "--exclude-module",
            "PySide6.Qt3DCore",
            "--exclude-module",
            "PySide6.QtMultimedia",
            "--exclude-module",
            "tkinter",
            str(RAIZ / "tools" / "entrypoint.py"),
        ],
        "empacotando com o PyInstaller",
    )

    exe = RAIZ / "dist" / f"{NOME}.exe"
    if not exe.exists():
        raise SystemExit("o PyInstaller terminou sem produzir o executável")
    print(f"\nPronto: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
