"""Modelos de domínio do macropad.

Um :class:`Profile` (o "save" do usuário) associa cada uma das teclas
físicas a uma :class:`Action`. As ações são descritas por um tipo e um
dicionário de parâmetros, o que permite adicionar novos tipos de ação
sem alterar o modelo (padrão Strategy + Registry, ver ``actions/``).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# Layout físico do macropad (18 teclas: 3 linhas x 6 colunas).
KEY_COUNT = 18
KEY_ROWS = 3
KEY_COLS = 6

# Resolução do display OLED 0,96" (SSD1306).
SCREEN_W = 128
SCREEN_H = 64


@dataclass
class Action:
    """Uma ação executável associada a uma tecla.

    ``type``   identifica o executor registrado (ex.: ``hotkey``, ``text``,
               ``command``, ``launch``, ``media``, ``macro``, ``home_assistant``).
    ``params`` são os parâmetros específicos daquele tipo.
    ``label``  é o nome curto exibido na tecla dentro do configurador.
    """

    type: str
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "params": self.params, "label": self.label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        return cls(
            type=data["type"],
            params=dict(data.get("params", {})),
            label=data.get("label", ""),
        )


@dataclass
class Profile:
    """Um conjunto nomeado de atalhos ("save") selecionável pela tecla de modo.

    ``icon_path`` aponta para a imagem escolhida pelo usuário; quando ausente,
    o display do macropad exibe o nome do perfil. ``auto_apps`` lista os
    executáveis (ex.: ``code.exe``) que ativam este perfil automaticamente
    quando ganham o foco (se a troca automática estiver habilitada).
    """

    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    icon_path: str | None = None
    bindings: dict[int, Action] = field(default_factory=dict)
    auto_apps: list[str] = field(default_factory=list)

    def action_for(self, key: int) -> Action | None:
        return self.bindings.get(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "icon_path": self.icon_path,
            "bindings": {str(k): a.to_dict() for k, a in self.bindings.items()},
            "auto_apps": self.auto_apps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Reconstrói o perfil. Lança ``KeyError`` se não houver nome.

        Teclas e apps inválidos são descartados individualmente: um dado
        corrompido não deve custar o perfil inteiro.
        """
        name = data["name"]
        return cls(
            name=name,
            id=data.get("id") or uuid.uuid4().hex,
            icon_path=data.get("icon_path"),
            bindings=_bindings_from_dict(data.get("bindings"), name),
            auto_apps=_auto_apps_from_dict(data.get("auto_apps"), name),
        )


def _bindings_from_dict(raw: Any, profile_name: Any) -> dict[int, Action]:
    if not isinstance(raw, dict):
        return {}
    bindings: dict[int, Action] = {}
    for key, action in raw.items():
        try:
            bindings[int(key)] = Action.from_dict(action)
        except (KeyError, TypeError, ValueError):
            log.warning(
                "perfil %r: tecla %r descartada (definição inválida)",
                profile_name,
                key,
            )
    return bindings


def _auto_apps_from_dict(raw: Any, profile_name: Any) -> list[str]:
    # Uma string aqui seria iterada caractere a caractere; só lista serve.
    if not isinstance(raw, list):
        if raw is not None:
            log.warning("perfil %r: apps vinculados descartados", profile_name)
        return []
    return [str(app).lower() for app in raw]


@dataclass
class Settings:
    """Configurações globais do aplicativo (independem de perfil)."""

    # Índice (0..17) da tecla que alterna o perfil ativo; None = desabilitado.
    mode_key: int | None = None
    # Porta serial preferida (ex.: "COM5"); None = detecção automática.
    serial_port: str | None = None
    # Troca automática de perfil pelo aplicativo em foco.
    auto_switch_enabled: bool = False
    # Registrar o aplicativo para iniciar junto com o Windows (na bandeja).
    start_with_windows: bool = False
    # Integração Home Assistant.
    ha_url: str = ""
    ha_token: str = ""
    # Integração OBS Studio (obs-websocket v5).
    obs_host: str = "localhost"
    obs_port: int = 4455
    obs_password: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_key": self.mode_key,
            "serial_port": self.serial_port,
            "auto_switch_enabled": self.auto_switch_enabled,
            "start_with_windows": self.start_with_windows,
            "ha_url": self.ha_url,
            "ha_token": self.ha_token,
            "obs_host": self.obs_host,
            "obs_port": self.obs_port,
            "obs_password": self.obs_password,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        return cls(
            mode_key=data.get("mode_key"),
            serial_port=data.get("serial_port"),
            auto_switch_enabled=bool(data.get("auto_switch_enabled", False)),
            start_with_windows=bool(data.get("start_with_windows", False)),
            ha_url=data.get("ha_url", ""),
            ha_token=data.get("ha_token", ""),
            obs_host=data.get("obs_host", "localhost"),
            obs_port=int(data.get("obs_port", 4455)),
            obs_password=data.get("obs_password", ""),
        )
