"""Dispositivo virtual para desenvolvimento e demonstração sem hardware.

Implementa a mesma interface do :class:`~macropad.device.link.SerialLink`,
mas os eventos de tecla vêm de uma janela com 18 botões e o "display"
é um widget que renderiza os mesmos frames que o firmware receberia —
útil para validar o software antes de o firmware ficar pronto e para a
banca do TCC.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.models import KEY_COUNT, SCREEN_H, SCREEN_W


class SimulatorLink:
    """Enlace virtual: espelha o protocolo em memória."""

    def __init__(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_state: Callable[[bool, str], None],
    ) -> None:
        self._on_message = on_message
        self._on_state = on_state
        self._connected = False
        self._on_display: Callable[[dict[str, Any]], None] | None = None
        # Último frame recebido do host. O dispositivo real mantém na tela
        # o que lhe foi enviado, então o simulador também precisa guardá-lo:
        # a janela costuma ser criada depois de o enlace iniciar e perderia
        # o primeiro frame (o do perfil ativo, enviado em resposta ao hello).
        self._last_display: dict[str, Any] | None = None

    @property
    def on_display(self) -> Callable[[dict[str, Any]], None] | None:
        """Callback da janela do simulador que desenha o display."""
        return self._on_display

    @on_display.setter
    def on_display(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self._on_display = callback
        # Uma janela que abre agora deve ver o que já está "na tela".
        if callback is not None and self._last_display is not None:
            callback(self._last_display)

    def start(self) -> None:
        self._connected = True
        self._on_state(True, "Simulador")
        self._on_message(
            {
                "t": "hello",
                "fw": "sim",
                "keys": KEY_COUNT,
                "screen": {"w": SCREEN_W, "h": SCREEN_H},
            }
        )

    def stop(self) -> None:
        if self._connected:
            self._connected = False
            self._on_state(False, "Simulador")

    @property
    def connected(self) -> bool:
        return self._connected

    def send(self, message: dict[str, Any]) -> None:
        """Mensagens host->dispositivo viram atualizações do display virtual."""
        if message.get("t") not in ("text", "img"):
            return
        # Guarda antes de desenhar: o frame precisa sobreviver mesmo que
        # ainda não haja janela conectada.
        self._last_display = message
        if self._on_display is not None:
            self._on_display(message)

    # ------------------------------------------------- lado "hardware"

    def press_key(self, key: int) -> None:
        """Chamado pela janela do simulador quando um botão é clicado."""
        if self._connected:
            self._on_message({"t": "key", "k": key, "e": "down"})
            self._on_message({"t": "key", "k": key, "e": "up"})
