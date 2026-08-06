"""Inicialização automática com o Windows.

Registra o aplicativo em ``HKCU\\...\\Run`` apontando para o ``pythonw.exe``
do ambiente virtual com ``-m macropad --minimized`` (inicia direto na
bandeja, sem janela). Sem privilégios de administrador.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MacropadConfigurator"


def _command() -> str:
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else python
    return f'"{exe}" -m macropad --minimized'


def apply(enabled: bool) -> None:
    """Cria ou remove a entrada de inicialização conforme a configuração."""
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enabled:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _command())
        else:
            # Já ausente da chave Run: desabilitar é idempotente.
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteValue(key, _VALUE_NAME)


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
