"""Raiz de composição do aplicativo.

Monta as dependências (store -> runner -> controller -> enlace) e
gerencia a troca entre o enlace serial e o simulador. As camadas de
domínio não conhecem Qt; a comunicação com a UI passa pelo
:class:`~macropad.ui.bridge.DeviceBridge`.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QTimer

from .actions.base import ActionContext
from .actions.executor import ActionRunner
from .core.controller import Controller
from .core.store import Store
from .device.link import DeviceLink, SerialLink
from .device.simulator import SimulatorLink
from .integrations import foreground
from .ui.bridge import DeviceBridge

log = logging.getLogger(__name__)

SIMULATOR_PORT = "Simulador"
AUTO_PORT = "Automático"


class MacropadApp:
    def __init__(self) -> None:
        self.store = Store()
        self.store.load()

        self.bridge = DeviceBridge()
        # Falhas ao gravar a configuração aparecem na barra de status, pelo
        # mesmo canal já usado pelos erros de ação.
        self.store.on_error = self.bridge.action_error.emit
        self.runner = ActionRunner(
            context=ActionContext(
                settings=self.store.settings,
                request_mode_switch=self._request_mode_switch,
            ),
            on_error=self.bridge.action_error.emit,
        )
        self.controller = Controller(
            store=self.store,
            runner=self.runner,
            send=self._send,
            on_profile_changed=self.bridge.profile_changed.emit,
        )
        # Eventos do dispositivo chegam pela ponte já na thread da UI.
        self.bridge.message.connect(self.controller.handle_message)

        self.link: DeviceLink | None = None
        self.simulator: SimulatorLink | None = None
        # Última escolha de enlace, para restaurar depois de uma pausa
        # (a gravação do firmware precisa da porta serial livre).
        self._port_choice: str | None = None
        self._paused = False

        # Troca automática de perfil pelo aplicativo em foco (edge-triggered:
        # só reage quando o foco MUDA, então uma troca manual pela tecla de
        # modo prevalece até o usuário focar outro app vinculado).
        self._last_exe: str | None = None
        self._foreground_timer = QTimer()
        self._foreground_timer.setInterval(1000)
        self._foreground_timer.timeout.connect(self._poll_foreground)
        self._foreground_timer.start()

    # ------------------------------------------------------------- enlace

    def use_port(self, port: str | None) -> None:
        """Ativa o enlace escolhido: automático, uma COM específica ou o simulador."""
        self._stop_link()
        self._port_choice = port
        self._paused = False
        if port == SIMULATOR_PORT:
            self.simulator = SimulatorLink(
                on_message=self.bridge.emit_message,
                on_state=self.bridge.emit_state,
            )
            self.link = self.simulator
        else:
            self.simulator = None
            preferred = None if port in (None, AUTO_PORT) else port
            self.store.settings.serial_port = preferred
            self.store.save()
            self.link = SerialLink(
                on_message=self.bridge.emit_message,
                on_state=self.bridge.emit_state,
                preferred_port=preferred,
            )
        self.link.start()

    def pause_link(self) -> bool:
        """Solta a porta serial para que outra ferramenta possa usá-la.

        A gravação do firmware precisa de acesso exclusivo à COM; enquanto
        o enlace estiver rodando, o esptool encontraria a porta ocupada.
        O simulador não usa porta alguma, então não é pausado.

        Devolve ``True`` se havia um enlace serial ativo — nesse caso o
        chamador deve chamar :meth:`resume_link` ao terminar.
        """
        if self._paused or not isinstance(self.link, SerialLink):
            return False
        log.info("pausando o enlace serial")
        self.link.stop()
        self.link = None
        self._paused = True
        return True

    def resume_link(self) -> None:
        """Reativa o enlace pausado por :meth:`pause_link`."""
        if not self._paused:
            return
        log.info("retomando o enlace serial")
        self.use_port(self._port_choice)

    def _stop_link(self) -> None:
        if self.link is not None:
            self.link.stop()
            self.link = None
            self.simulator = None

    def _send(self, message: dict[str, Any]) -> None:
        if self.link is not None:
            self.link.send(message)

    # ------------------------------------------------------------ diverso

    def _poll_foreground(self) -> None:
        exe = foreground.foreground_exe()
        if exe == self._last_exe:
            return
        self._last_exe = exe
        if not self.store.settings.auto_switch_enabled:
            return
        profile = foreground.match_profile(self.store.profiles, exe)
        if profile is not None and profile.id != self.store.active_profile_id:
            self.controller.activate_profile(profile.id)

    def _request_mode_switch(self) -> None:
        """Chamado pela ação "mode_switch" (thread de ações)."""
        # Repassa para a thread da UI através da ponte.
        self.bridge.message.emit({"t": "_mode_switch"})

    def shutdown(self) -> None:
        self._foreground_timer.stop()
        self._stop_link()
        self.runner.stop()
        self.store.save()
