"""Detecção do aplicativo em primeiro plano (Windows).

Usada pela troca automática de perfil: quando o executável em foco muda
e corresponde ao ``auto_apps`` de um perfil, esse perfil é ativado.

A detecção é *edge-triggered* (só reage à MUDANÇA de foco), de modo que
uma troca manual pela tecla de modo prevalece até o usuário focar outro
aplicativo vinculado.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from ..core.models import Profile

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def foreground_exe() -> str | None:
    """Nome do executável da janela em foco (minúsculo, ex.: ``code.exe``)."""
    if sys.platform != "win32":
        return None
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    handle = _kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
    )
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buffer))
        if not _kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            return None
        path = buffer.value
    finally:
        _kernel32.CloseHandle(handle)
    return path.rsplit("\\", 1)[-1].lower() if path else None


def match_profile(profiles: list[Profile], exe: str | None) -> Profile | None:
    """Encontra o primeiro perfil vinculado ao executável dado."""
    if not exe:
        return None
    exe = exe.lower()
    for profile in profiles:
        if exe in profile.auto_apps:
            return profile
    return None
