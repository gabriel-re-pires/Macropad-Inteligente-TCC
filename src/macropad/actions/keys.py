"""Mapeamento de nomes amigáveis de tecla para objetos ``pynput``.

Os atalhos são persistidos como listas de nomes (ex.: ``["ctrl",
"shift", "p"]``) para que o arquivo de configuração seja legível e
independente de plataforma.
"""

from __future__ import annotations

from pynput.keyboard import Key, KeyCode

# Aliases aceitos na configuração -> atributo de pynput.keyboard.Key.
_SPECIAL: dict[str, Key] = {
    "ctrl": Key.ctrl,
    "control": Key.ctrl,
    "alt": Key.alt,
    "altgr": Key.alt_gr,
    "shift": Key.shift,
    "win": Key.cmd,
    "windows": Key.cmd,
    "cmd": Key.cmd,
    "super": Key.cmd,
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "esc": Key.esc,
    "escape": Key.esc,
    "space": Key.space,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "del": Key.delete,
    "insert": Key.insert,
    "home": Key.home,
    "end": Key.end,
    "pageup": Key.page_up,
    "pagedown": Key.page_down,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "capslock": Key.caps_lock,
    "printscreen": Key.print_screen,
    "pause": Key.pause,
    "menu": Key.menu,
}
_SPECIAL.update({f"f{i}": getattr(Key, f"f{i}") for i in range(1, 21)})

MODIFIERS = {"ctrl", "control", "alt", "altgr", "shift", "win", "windows", "cmd", "super"}

# Teclas de mídia do Windows (códigos de tecla virtual).
MEDIA_VK = {
    "play_pause": 0xB3,
    "next_track": 0xB0,
    "prev_track": 0xB1,
    "stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "volume_mute": 0xAD,
}

MEDIA_TITLES = {
    "play_pause": "Tocar/Pausar",
    "next_track": "Próxima faixa",
    "prev_track": "Faixa anterior",
    "stop": "Parar",
    "volume_up": "Aumentar volume",
    "volume_down": "Diminuir volume",
    "volume_mute": "Mudo",
}


def resolve(name: str) -> Key | KeyCode:
    """Converte um nome de tecla no objeto pynput correspondente."""
    name = name.strip().lower()
    if name in _SPECIAL:
        return _SPECIAL[name]
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise ValueError(f"tecla desconhecida: {name!r}")


def is_valid(name: str) -> bool:
    try:
        resolve(name)
        return True
    except ValueError:
        return False
