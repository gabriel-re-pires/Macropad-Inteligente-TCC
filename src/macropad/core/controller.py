"""Controlador central: liga o dispositivo, os perfis e o motor de ações.

Fluxo principal (executa a cada tecla pressionada no macropad):

    evento "key down" -> é a tecla de modo?  -> alterna o perfil ativo
                                                e atualiza o display
                      -> senão               -> resolve a ação no perfil
                                                ativo e a enfileira no
                                                ActionRunner; destaca a
                                                tecla no display por um
                                                instante (retorno visual)

O controlador não conhece Qt nem pyserial: recebe eventos já decodificados
e fala com o dispositivo por meio da interface ``DeviceLink``. O único
serviço de tempo de que precisa (desfazer o destaque da tecla) é
injetado como ``schedule(segundos, função)``. Isso o torna testável de
forma isolada (ver ``tests/test_controller.py``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..actions.executor import ActionRunner
from ..device import protocol
from . import display
from .models import Profile
from .store import Store

log = logging.getLogger(__name__)

Scheduler = Callable[[float, Callable[[], None]], None]


class Controller:
    # Tempo em que a tecla pressionada fica invertida no mapa do display.
    FEEDBACK_S = 0.25

    def __init__(
        self,
        store: Store,
        runner: ActionRunner,
        send: Callable[[dict[str, Any]], None],
        on_profile_changed: Callable[[Profile], None] | None = None,
        schedule: Scheduler | None = None,
    ) -> None:
        self._store = store
        self._runner = runner
        self._send = send
        self._on_profile_changed = on_profile_changed or (lambda p: None)
        self._schedule = schedule
        # Último payload enviado: evita reenviar 1,4 KB quando nada mudou.
        self._last_payload: str | None = None
        self._highlighted: int | None = None

    # ------------------------------------------------------------ eventos

    def handle_message(self, message: dict[str, Any]) -> None:
        """Processa uma mensagem vinda do dispositivo (ou do simulador)."""
        kind = message.get("t")
        if kind == "hello":
            # O dispositivo (re)iniciou ou acabou de nos ver: o que ele tem
            # na tela não é o nosso quadro, então o reenvio é forçado.
            self.push_display(force=True)
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
        self._feedback(key)
        action = profile.action_for(key)
        if action is None:
            log.debug("tecla %d sem ação no perfil %s", key, profile.name)
            return
        self._runner.submit(action)

    def _feedback(self, key: int) -> None:
        """Destaca a tecla no mapa do display e agenda o retorno ao normal."""
        settings = self._store.settings
        if not settings.key_feedback or settings.display_mode != "mapa":
            return
        self._highlighted = key
        self.push_display(highlight=key)
        if self._schedule is None:
            return

        def clear() -> None:
            if self._highlighted == key:
                self._highlighted = None
                self.push_display()

        self._schedule(self.FEEDBACK_S, clear)

    # ------------------------------------------------------------- perfil

    def switch_mode(self) -> None:
        """Avança para o próximo perfil (tecla de modo)."""
        profile = self._store.next_profile()
        self._highlighted = None
        self.push_display()
        self._on_profile_changed(profile)

    def activate_profile(self, profile_id: str) -> None:
        """Ativa um perfil escolhido na interface."""
        if self._store.profile_by_id(profile_id) is None:
            return
        self._store.active_profile_id = profile_id
        self._store.save()
        self._highlighted = None
        self.push_display()
        profile = self._store.active_profile
        if profile is not None:
            self._on_profile_changed(profile)

    # ------------------------------------------------------------ display

    def current_frame(self, highlight: int | None = None):
        """Quadro que o display deve mostrar agora (também usado pelo preview)."""
        profile = self._store.active_profile
        if profile is None:
            return None
        settings = self._store.settings
        return display.profile_frame(
            profile, settings.mode_key, settings.display_mode, highlight
        )

    def push_display(self, highlight: int | None = None, force: bool = False) -> None:
        """Envia ao display o quadro do perfil ativo.

        Quadros idênticos ao último enviado são suprimidos (a troca de
        perfil pela interface, por exemplo, dispara vários ``refresh``),
        exceto quando ``force`` — após um ``hello`` o dispositivo pode ter
        reiniciado e perdido a tela.
        """
        frame = self.current_frame(highlight)
        if frame is None:
            return
        payload = display.frame_payload(frame)
        if not force and payload == self._last_payload:
            return
        self._last_payload = payload
        self._send(protocol.msg_image(payload))
