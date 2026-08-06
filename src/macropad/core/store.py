"""Persistência de perfis e configurações em JSON.

Os dados ficam em ``%APPDATA%/MacropadConfigurator`` (ou ``~/.config`` em
outros sistemas). As imagens de ícone escolhidas pelo usuário são copiadas
para o subdiretório ``icons/`` para que o perfil continue funcionando caso
o arquivo original seja movido.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
from pathlib import Path

from .models import Action, Profile, Settings

_CONFIG_FILE = "config.json"


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "MacropadConfigurator"


class Store:
    """Carrega e salva o estado do aplicativo de forma atômica."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.icons_dir = self.data_dir / "icons"
        self.settings = Settings()
        self.profiles: list[Profile] = []
        self.active_profile_id: str | None = None

    # ------------------------------------------------------------------ IO

    def load(self) -> None:
        path = self.data_dir / _CONFIG_FILE
        if not path.exists():
            self._create_default()
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Arquivo corrompido: preserva uma cópia e recomeça do zero.
            # Se nem a cópia for possível, ainda assim é melhor abrir com a
            # configuração padrão do que impedir o uso do aplicativo.
            with contextlib.suppress(OSError):
                shutil.copy(path, path.with_suffix(".json.bak"))
            self._create_default()
            return
        self.settings = Settings.from_dict(data.get("settings", {}))
        self.profiles = [Profile.from_dict(p) for p in data.get("profiles", [])]
        self.active_profile_id = data.get("active_profile_id")
        if not self.profiles:
            self._create_default_profile()
        if self.active_profile_id not in {p.id for p in self.profiles}:
            self.active_profile_id = self.profiles[0].id

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "settings": self.settings.to_dict(),
            "active_profile_id": self.active_profile_id,
            "profiles": [p.to_dict() for p in self.profiles],
        }
        path = self.data_dir / _CONFIG_FILE
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

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
