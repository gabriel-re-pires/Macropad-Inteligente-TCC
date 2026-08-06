"""Persistência de perfis e configurações em JSON.

Os dados ficam em ``%APPDATA%/MacropadConfigurator`` (ou ``~/.config`` em
outros sistemas). As imagens de ícone escolhidas pelo usuário são copiadas
para o subdiretório ``icons/`` para que o perfil continue funcionando caso
o arquivo original seja movido.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from . import secrets
from .models import Action, Profile, Settings

_CONFIG_FILE = "config.json"

# Campos de Settings que não devem ficar legíveis no config.json.
_SECRET_FIELDS = ("ha_token", "obs_password")

log = logging.getLogger(__name__)


class SecretVault(Protocol):
    """Cofre de credenciais (ver :mod:`macropad.core.secrets`).

    Injetável para que os testes não toquem no Credential Manager real.
    """

    def store(self, name: str, value: str) -> bool: ...
    def load(self, name: str) -> str: ...


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "MacropadConfigurator"


class Store:
    """Carrega e salva o estado do aplicativo de forma atômica."""

    def __init__(
        self,
        data_dir: Path | None = None,
        vault: SecretVault | None = None,
    ) -> None:
        self.data_dir = data_dir or default_data_dir()
        self._vault: SecretVault = vault if vault is not None else secrets
        self.icons_dir = self.data_dir / "icons"
        self.settings = Settings()
        self.profiles: list[Profile] = []
        self.active_profile_id: str | None = None
        # Definido pela raiz de composição para levar falhas de gravação à
        # interface; sem ele, restam apenas as mensagens no log.
        self.on_error: Callable[[str], None] | None = None

    # ------------------------------------------------------------------ IO

    def load(self) -> None:
        """Carrega a configuração, aproveitando o máximo possível.

        Um arquivo parcialmente corrompido não deve custar todos os perfis
        do usuário: cada perfil inválido é descartado isoladamente e o
        arquivo original é preservado em ``.json.bak`` sempre que algo se
        perde. Falhar aqui nunca impede o aplicativo de abrir.
        """
        path = self.data_dir / _CONFIG_FILE
        if not path.exists():
            self._create_default()
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("configuração ilegível (%s); recomeçando do padrão", exc)
            self._backup(path)
            self._create_default()
            return
        if not isinstance(data, dict):
            log.warning("configuração não é um objeto JSON; recomeçando do padrão")
            self._backup(path)
            self._create_default()
            return

        self.settings, settings_ok = _settings_from_dict(data.get("settings"))
        self.profiles, discarded = _profiles_from_dict(data.get("profiles"))
        if not settings_ok or discarded:
            self._backup(path)

        self._load_secrets()

        active = data.get("active_profile_id")
        self.active_profile_id = active if isinstance(active, str) else None
        if not self.profiles:
            self._create_default_profile()
        if self.active_profile_id not in {p.id for p in self.profiles}:
            self.active_profile_id = self.profiles[0].id

    # ---------------------------------------------------------- segredos

    def _load_secrets(self) -> None:
        """Completa as credenciais a partir do cofre do sistema.

        Um valor ainda presente no arquivo (instalação anterior à mudança)
        tem precedência e é migrado para o cofre no próximo ``save()``.
        """
        for campo in _SECRET_FIELDS:
            if not getattr(self.settings, campo):
                setattr(self.settings, campo, self._vault.load(campo))

    def _store_secrets(self, data: dict[str, Any]) -> None:
        """Move as credenciais do dicionário a salvar para o cofre.

        O que for guardado no cofre sai do JSON; o que não puder ser
        guardado continua no arquivo, para não perder a configuração.
        """
        settings_data = data.get("settings")
        if not isinstance(settings_data, dict):
            return
        for campo in _SECRET_FIELDS:
            if self._vault.store(campo, getattr(self.settings, campo)):
                settings_data[campo] = ""

    def _backup(self, path: Path) -> None:
        """Preserva o arquivo original antes de sobrescrevê-lo.

        Se nem a cópia for possível, ainda é melhor abrir o aplicativo do
        que impedir seu uso.
        """
        with contextlib.suppress(OSError):
            shutil.copy(path, path.with_suffix(".json.bak"))

    def save(self) -> bool:
        """Grava a configuração de forma atômica. ``False`` se não conseguiu.

        Chamado a cada troca de perfil (inclusive pela tecla de modo), então
        uma falha de disco não pode derrubar o aplicativo: é registrada e
        reportada, e o macropad continua funcionando com o estado em
        memória.
        """
        data: dict[str, Any] = {
            "settings": self.settings.to_dict(),
            "active_profile_id": self.active_profile_id,
            "profiles": [p.to_dict() for p in self.profiles],
        }
        self._store_secrets(data)
        path = self.data_dir / _CONFIG_FILE
        tmp = path.with_suffix(".json.tmp")
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(path)
        except OSError as exc:
            log.error("falha ao salvar %s: %s", path, exc)
            # Não deixa para trás um arquivo temporário pela metade.
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            if self.on_error is not None:
                self.on_error(f"não foi possível salvar as configurações: {exc}")
            return False
        return True

    def _create_default(self) -> None:
        self.settings = Settings()
        self.profiles = []
        self._create_default_profile()
        self.active_profile_id = self.profiles[0].id
        self.save()

    def _create_default_profile(self) -> None:
        profile = Profile(name="Sistema")
        profile.bindings[0] = Action(
            type="hotkey", params={"keys": ["ctrl", "c"]}, label="Copiar"
        )
        profile.bindings[1] = Action(
            type="hotkey", params={"keys": ["ctrl", "v"]}, label="Colar"
        )
        self.profiles.append(profile)

    # ------------------------------------------------------------ profiles

    def profile_by_id(self, profile_id: str | None) -> Profile | None:
        for p in self.profiles:
            if p.id == profile_id:
                return p
        return None

    @property
    def active_profile(self) -> Profile | None:
        return self.profile_by_id(self.active_profile_id)

    def add_profile(self, name: str) -> Profile:
        profile = Profile(name=name)
        self.profiles.append(profile)
        self.save()
        return profile

    def remove_profile(self, profile_id: str) -> None:
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        if not self.profiles:
            self._create_default_profile()
        if self.active_profile_id == profile_id:
            self.active_profile_id = self.profiles[0].id
        self.save()

    def next_profile(self) -> Profile:
        """Perfil seguinte na ordem da lista (usado pela tecla de modo)."""
        ids = [p.id for p in self.profiles]
        current = self.active_profile_id
        # Sem perfil ativo (ou apontando para um já excluído): começa do
        # primeiro da lista.
        idx = ids.index(current) if current in ids else -1
        profile = self.profiles[(idx + 1) % len(self.profiles)]
        self.active_profile_id = profile.id
        self.save()
        return profile

    def import_icon(self, source: str, profile: Profile) -> str:
        """Copia a imagem escolhida para o diretório de dados e a associa ao perfil."""
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(source).suffix.lower() or ".png"
        dest = self.icons_dir / f"{profile.id}{ext}"
        shutil.copy(source, dest)
        profile.icon_path = str(dest)
        self.save()
        return str(dest)


# ------------------------------------------------- desserialização tolerante


def _settings_from_dict(raw: Any) -> tuple[Settings, bool]:
    """Devolve (configurações, ``True`` se vieram intactas do arquivo)."""
    if raw is None:
        return Settings(), True
    if not isinstance(raw, dict):
        log.warning("bloco 'settings' inválido; usando os padrões")
        return Settings(), False
    try:
        return Settings.from_dict(raw), True
    except (TypeError, ValueError) as exc:
        log.warning("configurações inválidas (%s); usando os padrões", exc)
        return Settings(), False


def _profiles_from_dict(raw: Any) -> tuple[list[Profile], int]:
    """Devolve (perfis válidos, quantidade descartada)."""
    if raw is None:
        return [], 0
    if not isinstance(raw, list):
        log.warning("bloco 'profiles' inválido; nenhum perfil carregado")
        return [], 1

    profiles: list[Profile] = []
    discarded = 0
    for index, item in enumerate(raw):
        try:
            profiles.append(Profile.from_dict(item))
        except (KeyError, TypeError, ValueError) as exc:
            discarded += 1
            log.warning("perfil na posição %d descartado (%s)", index, exc)
    return profiles, discarded
