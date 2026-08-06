"""Controlador central: liga o dispositivo, os perfis e o motor de ações.

Fluxo principal (executa a cada tecla pressionada no macropad):

    evento "key down" -> é a tecla de modo?  -> alterna o perfil ativo
                                                e atualiza o display
                      -> senão               -> resolve a ação no perfil
                                                ativo e a enfileira no
                                                ActionRunner

O controlador não conhece Qt nem pyserial: recebe eventos já decodificados
e fala com o dispositivo por meio da interface ``DeviceLink``. Isso o
torna testável de forma isolada (ver ``tests/test_controller.py``).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..actions.executor import ActionRunner
from ..device import protocol
from . import icons
from .models import Profile
from .store import Store

log = logging.getLogger(__name__)


class Controller:
    def __init__(
        self,
        store: Store,
        runner: ActionRunner,
        send: Callable[[dict[str, Any]], None],
        on_profile_changed: Callable[[Profile], None] | None = None,
    ) -> None:
        self._store = store
        self._runner = runner
        self._send = send
        self._on_profile_changed = on_profile_changed or (lambda p: None)

    # ------------------------------------------------------------ eventos

    def handle_message(self, message: dict[str, Any]) -> None:
        """Processa uma mensagem vinda do dispositivo (ou do simulador)."""
        kind = message.get("t")
        if kind == "hello":
            self.push_display()
        elif kind == "key" and message.get("e") == "down":
            self._handle_key(int(message.get("k", -1)))
        elif kind == "_mode_switch":
            # Mensagem interna gerada pela ação "mode_switch" (ver app.py).
            self.switch_mode()

    def _handle_key(self, key: int) -> None:
        if key == self._store.settings.mode_key:
            self.switch_mode()
            return
        profile = self._store.active_profile
        if profile is None:
            return
        action = profile.action_for(key)
        if action is None:
            log.debug("tecla %d sem ação no perfil %s", key, profile.name)
            return
        self._runner.submit(action)

    # ------------------------------------------------------------- perfil

    def switch_mode(self) -> None:
        """Avança para o próximo perfil (tecla de modo)."""
        profile = self._store.next_profile()
        self.push_display()
        self._on_profile_changed(profile)

    def activate_profile(self, profile_id: str) -> None:
        """Ativa um perfil escolhido na interface."""
        if self._store.profile_by_id(profile_id) is None:
            return
        self._store.active_profile_id = profile_id
        self._store.save()
        self.push_display()
        profile = self._store.active_profile
        if profile is not None:
            self._on_profile_changed(profile)

    # ------------------------------------------------------------ display

    def push_display(self) -> None:
        """Envia ao display o ícone do perfil ativo (ou seu nome, sem ícone)."""
        profile = self._store.active_profile
        if profile is None:
            return
        if profile.icon_path:
            try:
                payload = icons.icon_payload(profile.icon_path)
                self._send(protocol.msg_image(payload))
                return
            except (OSError, ValueError) as exc:
                log.warning("falha ao converter ícone de %s: %s", profile.name, exc)
        self._send(protocol.msg_text([profile.name]))
