"""Painel lateral de perfis ("saves") do usuário.

Permite criar, renomear, excluir, reordenar implicitamente (ordem da
lista = ordem de alternância da tecla de modo), ativar e associar um
ícone a cada perfil.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.store import Store


class ProfilePanel(QWidget):
    profile_selected = Signal(str)   # perfil escolhido para EDIÇÃO
    activate_requested = Signal(str)  # perfil a ATIVAR no dispositivo
    profiles_changed = Signal()

    def __init__(self, store: Store) -> None:
        super().__init__()
        self._store = store

        layout = QVBoxLayout(self)
        title = QLabel("Perfis")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setIconSize(QSize(28, 28))
        self._list.currentItemChanged.connect(self._on_selection)
        self._list.itemDoubleClicked.connect(
            lambda item: self.activate_requested.emit(item.data(Qt.UserRole))
        )
        layout.addWidget(self._list, stretch=1)

        hint = QLabel("Clique duplo ativa o perfil.\nA tecla de modo segue a ordem da lista.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row1 = QHBoxLayout()
        for text, slot in (("Novo", self._new), ("Renomear", self._rename), ("Excluir", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row1.addWidget(b)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        icon_btn = QPushButton("Definir ícone…")
        icon_btn.clicked.connect(self._set_icon)
        clear_btn = QPushButton("Remover ícone")
        clear_btn.clicked.connect(self._clear_icon)
        row2.addWidget(icon_btn)
        row2.addWidget(clear_btn)
        layout.addLayout(row2)

        apps_btn = QPushButton("Apps vinculados…")
        apps_btn.setToolTip(
            "Aplicativos que ativam este perfil automaticamente ao ganharem "
            "o foco (habilite a troca automática em Configurações)."
        )
        apps_btn.clicked.connect(self._edit_auto_apps)
        layout.addWidget(apps_btn)

        activate_btn = QPushButton("Ativar perfil selecionado")
        activate_btn.setObjectName("primary")
        activate_btn.clicked.connect(self._activate)
        layout.addWidget(activate_btn)

        self.refresh()

    # ---------------------------------------------------------------- API

    def refresh(self) -> None:
        current = self.selected_profile_id()
        self._list.blockSignals(True)
        self._list.clear()
        for profile in self._store.profiles:
            item = QListWidgetItem(profile.name)
            item.setData(Qt.UserRole, profile.id)
            if profile.icon_path:
                pixmap = QPixmap(profile.icon_path)
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
            if profile.id == self._store.active_profile_id:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setText(f"{profile.name}  ●")
            self._list.addItem(item)
            if profile.id == current:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        if self._list.currentRow() < 0 and self._list.count() > 0:
            self._list.setCurrentRow(0)

    def selected_profile_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.UserRole) if item else None

    # ------------------------------------------------------------- eventos

    def _on_selection(self, current: QListWidgetItem | None, _prev=None) -> None:
        if current is not None:
            self.profile_selected.emit(current.data(Qt.UserRole))

    def _new(self) -> None:
        name, ok = QInputDialog.getText(self, "Novo perfil", "Nome do perfil:")
        if ok and name.strip():
            profile = self._store.add_profile(name.strip())
            self.refresh()
            self._select(profile.id)
            self.profiles_changed.emit()

    def _rename(self) -> None:
        profile = self._store.profile_by_id(self.selected_profile_id())
        if profile is None:
            return
        name, ok = QInputDialog.getText(
            self, "Renomear perfil", "Novo nome:", text=profile.name
        )
        if ok and name.strip():
            profile.name = name.strip()
            self._store.save()
            self.refresh()
            self.profiles_changed.emit()

    def _delete(self) -> None:
        profile = self._store.profile_by_id(self.selected_profile_id())
        if profile is None:
            return
        answer = QMessageBox.question(
            self,
            "Excluir perfil",
            f"Excluir o perfil “{profile.name}” e todos os seus atalhos?",
        )
        if answer == QMessageBox.Yes:
            self._store.remove_profile(profile.id)
            self.refresh()
            self.profiles_changed.emit()

    def _set_icon(self) -> None:
        profile = self._store.profile_by_id(self.selected_profile_id())
        if profile is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher ícone (prefira pictogramas simples de alto contraste)",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if path:
            self._store.import_icon(path, profile)
            self.refresh()
            self.profiles_changed.emit()

    def _clear_icon(self) -> None:
        profile = self._store.profile_by_id(self.selected_profile_id())
        if profile is None:
            return
        profile.icon_path = None
        self._store.save()
        self.refresh()
        self.profiles_changed.emit()

    def _edit_auto_apps(self) -> None:
        from .auto_apps_dialog import AutoAppsDialog

        profile = self._store.profile_by_id(self.selected_profile_id())
        if profile is None:
            return
        dialog = AutoAppsDialog(self, profile)
        if dialog.exec() == AutoAppsDialog.Accepted:
            self._store.save()

    def _activate(self) -> None:
        profile_id = self.selected_profile_id()
        if profile_id:
            self.activate_requested.emit(profile_id)

    def _select(self, profile_id: str) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole) == profile_id:
                self._list.setCurrentRow(i)
                return
