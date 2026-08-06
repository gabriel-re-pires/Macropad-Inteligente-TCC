"""Painel lateral de perfis ("saves") do usuário.

Permite criar, renomear, excluir, reordenar implicitamente (ordem da
lista = ordem de alternância da tecla de modo), ativar e associar um
ícone a cada perfil.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from ..core import profile_io
from ..core.store import Store


def _nome_de_arquivo(nome: str) -> str:
    """Nome de perfil -> nome de arquivo seguro no Windows."""
    limpo = re.sub(r'[<>:"/\\|?*]', "_", nome).strip(" .")
    return limpo or "perfil"


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
        # Arrastar reordena a lista — e a ordem da lista é a ordem em que a
        # tecla de modo percorre os perfis.
        self._list.setDragDropMode(QAbstractItemView.InternalMove)
        self._list.setDefaultDropAction(Qt.MoveAction)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list, stretch=1)

        hint = QLabel(
            "Clique duplo ativa o perfil. Arraste para reordenar.\n"
            "A tecla de modo segue a ordem da lista."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row1 = QHBoxLayout()
        for text, slot in (
            ("Novo", self._new),
            ("Renomear", self._rename),
            ("Excluir", self._delete),
        ):
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

        row3 = QHBoxLayout()
        export_btn = QPushButton("Exportar…")
        export_btn.setToolTip("Salva o perfil selecionado em um arquivo .json.")
        export_btn.clicked.connect(self._export)
        import_btn = QPushButton("Importar…")
        import_btn.setToolTip("Acrescenta um perfil vindo de um arquivo .json.")
        import_btn.clicked.connect(self._import)
        row3.addWidget(export_btn)
        row3.addWidget(import_btn)
        layout.addLayout(row3)

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

    def _on_rows_moved(self, *_args) -> None:
        """Persiste a nova ordem depois de um arrastar-e-soltar."""
        ordem = [
            self._list.item(i).data(Qt.UserRole) for i in range(self._list.count())
        ]
        por_id = {p.id: p for p in self._store.profiles}
        reordenados = [por_id[pid] for pid in ordem if pid in por_id]
        # Rede de segurança: nenhum perfil pode sumir por não estar na lista.
        vistos = set(ordem)
        reordenados += [p for p in self._store.profiles if p.id not in vistos]

        self._store.profiles = reordenados
        self._store.save()
        self.profiles_changed.emit()

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

    # ------------------------------------------------- exportar/importar

    def _export(self) -> None:
        profile = self._store.profile_by_id(self.selected_profile_id())
        if profile is None:
            return
        sugestao = f"{_nome_de_arquivo(profile.name)}.json"
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar perfil", sugestao, "Perfil do macropad (*.json)"
        )
        if not caminho:
            return
        try:
            self._store.export_profile(profile, Path(caminho))
        except OSError as exc:
            QMessageBox.critical(self, "Exportar perfil", f"Falha ao gravar: {exc}")
            return
        QMessageBox.information(
            self, "Exportar perfil", f"Perfil “{profile.name}” exportado."
        )

    def _import(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Importar perfil", "", "Perfil do macropad (*.json)"
        )
        if not caminho:
            return
        try:
            texto = Path(caminho).read_text(encoding="utf-8")
            importado = profile_io.from_json(texto)
        except OSError as exc:
            QMessageBox.critical(self, "Importar perfil", f"Falha ao ler: {exc}")
            return
        except profile_io.ProfileFileError as exc:
            QMessageBox.critical(self, "Importar perfil", f"Arquivo inválido: {exc}")
            return

        if not self._confirmar_acoes_sensiveis(importado):
            return

        profile = self._store.add_imported_profile(importado)
        self.refresh()
        self._select(profile.id)
        self.profiles_changed.emit()

    def _confirmar_acoes_sensiveis(self, importado) -> bool:
        """Mostra o que o perfil executaria antes de aceitá-lo.

        Um perfil vindo de terceiros pode conter ações que rodam comandos
        de shell ou abrem programas com os privilégios de quem importa.
        """
        if not importado.sensitive:
            return True
        linhas = "\n".join(
            f"  • Tecla {tecla + 1}: {alvo or '(sem alvo)'}"
            for tecla, alvo in importado.sensitive[:10]
        )
        restantes = len(importado.sensitive) - 10
        if restantes > 0:
            linhas += f"\n  • … e mais {restantes}"
        answer = QMessageBox.warning(
            self,
            "Importar perfil",
            f"O perfil “{importado.profile.name}” executa comandos ou abre "
            f"programas nesta máquina:\n\n{linhas}\n\n"
            "Importe apenas de fontes confiáveis. Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

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
