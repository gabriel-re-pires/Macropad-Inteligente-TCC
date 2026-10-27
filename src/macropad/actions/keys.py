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


# ------------------------------------------------------- gravação (Qt)

# Teclas especiais do Qt -> nome aceito por ``resolve``.
_QT_SPECIAL: dict[int, str] = {
    0x01000004: "enter",     # Qt.Key_Return
    0x01000005: "enter",     # Qt.Key_Enter
    0x01000001: "tab",       # Qt.Key_Tab
    0x01000000: "esc",       # Qt.Key_Escape
    0x20: "space",           # Qt.Key_Space
    0x01000003: "backspace",
    0x01000007: "delete",
    0x01000006: "insert",
    0x01000010: "home",
    0x01000011: "end",
    0x01000016: "pageup",
    0x01000017: "pagedown",
    0x01000013: "up",
    0x01000015: "down",
    0x01000012: "left",
    0x01000014: "right",
    0x01000024: "capslock",
    0x01000009: "printscreen",
    0x01000008: "pause",
    0x01000055: "menu",
}
_QT_SPECIAL.update({0x01000030 + i: f"f{i + 1}" for i in range(20)})  # Key_F1..F20

_QT_MODIFIERS = (
    (0x04000000, "ctrl"),   # Qt.ControlModifier
    (0x08000000, "alt"),    # Qt.AltModifier
    (0x02000000, "shift"),  # Qt.ShiftModifier
    (0x10000000, "win"),    # Qt.MetaModifier
)


def names_from_qt(sequence: object) -> list[str]:
    """Converte uma ``QKeySequence`` gravada na UI para a lista de nomes.

    Recebe ``object`` para manter este módulo livre de Qt: só usa o
    ``toCombined()`` do primeiro ``QKeyCombination``. Devolve lista vazia
    para combinações sem tecla principal (só modificadores) ou com tecla
    que o pynput não representa.
    """
    try:
        combined = int(sequence[0].toCombined())  # type: ignore[index]
    except (IndexError, AttributeError, TypeError):
        return []
    modifiers = combined & 0xFE000000
    key = combined & 0x01FFFFFF
    names = [name for flag, name in _QT_MODIFIERS if modifiers & flag]
    if key in _QT_SPECIAL:
        names.append(_QT_SPECIAL[key])
    elif 0x20 < key < 0x7F:
        names.append(chr(key).lower())
    else:
        return []
    return names
