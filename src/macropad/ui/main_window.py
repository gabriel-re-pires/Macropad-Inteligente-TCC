"""Janela principal do configurador."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from ..app import AUTO_PORT, SIMULATOR_PORT, MacropadApp
from ..core import autostart, icons
from ..core.models import Action, Profile
from ..device import protocol
from ..device.link import available_ports
from .action_editor import ActionEditorDialog
from .key_grid import KeyGrid
from .oled_preview import OledPreview
from .profile_panel import ProfilePanel
from .settings_dialog import SettingsDialog
from .simulator_window import SimulatorWindow


class MainWindow(QMainWindow):
    def __init__(self, core: MacropadApp) -> None:
        super().__init__()
        self._core = core
        self._editing_profile_id: str | None = core.store.active_profile_id
        self._settings_dialog: SettingsDialog | None = None
        self._simulator_window: SimulatorWindow | None = None
        # Ação copiada pelo menu de contexto da grade, para colar em outra tecla.
        self._clipboard_action: Action | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(_app_icon())
        self.resize(1080, 640)
        self._quitting = False
        self._tray_notified = False
        self._setup_tray()

        # ------------------------------------------------------ barra superior
        top = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_label = QLabel("Desconectado — procurando o macropad…")
        self._set_connected(False, "")
        top.addWidget(self._status_dot)
        top.addWidget(self._status_label)
        top.addStretch(1)
        top.addWidget(QLabel("Conexão:"))
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(220)
        self._reload_ports()
        self._port_combo.currentIndexChanged.connect(self._on_port_selected)
        top.addWidget(self._port_combo)
        refresh = QPushButton("Atualizar portas")
        refresh.clicked.connect(self._reload_ports)
        top.addWidget(refresh)
        settings_btn = QPushButton("Configurações…")
        settings_btn.clicked.connect(self._open_settings)
        top.addWidget(settings_btn)

        # --------------------------------------------------------- conteúdo
        self._profile_panel = ProfilePanel(core.store)
        self._profile_panel.profile_selected.connect(self._on_edit_profile)
        self._profile_panel.activate_requested.connect(core.controller.activate_profile)
        self._profile_panel.profiles_changed.connect(self._refresh_all)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        preview_row = QHBoxLayout()
        preview_col = QVBoxLayout()
        preview_title = QLabel("Display do macropad (perfil ativo)")
        preview_title.setObjectName("hint")
        self._oled = OledPreview()
        preview_col.addWidget(preview_title, alignment=Qt.AlignHCenter)
        preview_col.addWidget(self._oled, alignment=Qt.AlignHCenter)
        preview_row.addStretch(1)
        preview_row.addLayout(preview_col)
        preview_row.addStretch(1)
        right_layout.addLayout(preview_row)

        self._grid_title = QLabel("")
        self._grid_title.setObjectName("panelTitle")
        right_layout.addWidget(self._grid_title, alignment=Qt.AlignHCenter)
        self._grid = KeyGrid()
        self._grid.key_clicked.connect(self._on_key_clicked)
        self._grid.key_menu_requested.connect(self._on_key_menu)
        right_layout.addWidget(self._grid, stretch=1)

        self._splitter = splitter = QSplitter()
        splitter.addWidget(self._profile_panel)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 820])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addLayout(top)
        central_layout.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        # ------------------------------------------------------------ sinais
        core.bridge.state.connect(self._set_connected)
        core.bridge.message.connect(self._on_device_message)
        core.bridge.action_error.connect(self._on_action_error)
        core.bridge.profile_changed.connect(self._on_active_profile_changed)

        # ---------------------------------------------------------- atalhos
        QShortcut(QKeySequence("Ctrl+,"), self, self._open_settings)
        QShortcut(QKeySequence("F5"), self, self._reload_ports)

        self._restore_layout()
        self._refresh_all()
        self._start_initial_link()

    # -------------------------------------------------------------- layout

    def _restore_layout(self) -> None:
        """Recupera posição, tamanho e divisão da sessão anterior."""
        settings = QSettings()
        geometry = settings.value("janela/geometria")
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter_state = settings.value("janela/divisor")
        if splitter_state is not None:
            self._splitter.restoreState(splitter_state)

    def _save_layout(self) -> None:
        settings = QSettings()
        settings.setValue("janela/geometria", self.saveGeometry())
        settings.setValue("janela/divisor", self._splitter.saveState())

    # ------------------------------------------------------------- bandeja

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(_app_icon(), self)
        self._tray.setToolTip(APP_NAME)
        menu = QMenu()
        open_action = QAction("Abrir configurador", menu)
        open_action.triggered.connect(self.show_from_tray)
        menu.addAction(open_action)
        menu.addSeparator()
        # O aplicativo passa a maior parte do tempo oculto na bandeja: trocar
        # de perfil daqui evita ter que reabrir a janela.
        self._tray_profiles_menu = menu.addMenu("Trocar perfil")
        menu.addSeparator()
        quit_action = QAction("Sair", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        # A referência precisa sobreviver: o QMenu não tem pai.
        self._tray_menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda reason: self.show_from_tray()
            if reason == QSystemTrayIcon.Trigger
            else None
        )
        self._tray.show()

    def show_from_tray(self) -> None:
        """Restaura e foca a janela (bandeja ou segunda instância aberta)."""
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        """Encerra de verdade (fechar a janela apenas minimiza à bandeja)."""
        self._quitting = True
        self.close()

    # ------------------------------------------------------------- conexão

    def _reload_ports(self) -> None:
        self._port_combo.blockSignals(True)
        current = self._port_combo.currentText()
        self._port_combo.clear()
        self._port_combo.addItem(AUTO_PORT)
        for device, description in available_ports():
            self._port_combo.addItem(f"{device} — {description}", device)
        self._port_combo.addItem(SIMULATOR_PORT)
        index = self._port_combo.findText(current)
        if index >= 0:
            self._port_combo.setCurrentIndex(index)
        self._port_combo.blockSignals(False)

    def _start_initial_link(self) -> None:
        preferred = self._core.store.settings.serial_port
        if preferred:
            for i in range(self._port_combo.count()):
                if self._port_combo.itemData(i) == preferred:
                    self._port_combo.setCurrentIndex(i)
                    break
        self._on_port_selected()

    def _on_port_selected(self) -> None:
        text = self._port_combo.currentText()
        data = self._port_combo.currentData()
        if self._simulator_window is not None:
            self._simulator_window.close()
            self._simulator_window = None
        if text == SIMULATOR_PORT:
            self._core.use_port(SIMULATOR_PORT)
            simulator = self._core.simulator
            if simulator is not None:
                self._simulator_window = SimulatorWindow(simulator)
                self._simulator_window.show()
        elif text == AUTO_PORT:
            self._core.use_port(None)
        else:
            self._core.use_port(data)

    def _set_connected(self, connected: bool, port: str) -> None:
        color = "#41d98d" if connected else "#e05b5b"
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        if connected:
            self._status_label.setText(f"Conectado ({port})")
        else:
            self._status_label.setText("Desconectado — procurando o macropad…")
        if hasattr(self, "_tray"):
            state = f"conectado ({port})" if connected else "desconectado"
            self._tray.setToolTip(f"{APP_NAME} — {state}")

    # ------------------------------------------------------------- eventos

    def _on_device_message(self, message: dict[str, Any]) -> None:
        if message.get("t") != "key" or message.get("e") != "down":
            return
        key = int(message.get("k", -1))
        dialog = self._settings_dialog
        if dialog is not None and dialog.capturing_mode_key:
            dialog.key_captured(key)
            return
        # Acende a tecla na grade: confirma visualmente que o dispositivo
        # chegou até o software, mesmo quando a ação não tem efeito visível.
        self._grid.flash(key)
        self.statusBar().showMessage(f"Tecla {key + 1} pressionada", 1500)

    def _on_action_error(self, message: str) -> None:
        """Reporta a falha de uma ação onde o usuário possa vê-la.

        A barra de status não serve quando a janela está oculta na bandeja
        — que é o estado normal de uso —, então nesse caso a notificação
        vai pelo ícone da bandeja.
        """
        self.statusBar().showMessage(f"Erro: {message}", 6000)
        if not self.isVisible() and self._tray.isVisible():
            self._tray.showMessage(APP_NAME, message, QSystemTrayIcon.Warning, 5000)

    def _on_active_profile_changed(self, profile: Profile) -> None:
        self.statusBar().showMessage(f"Perfil ativo: {profile.name}", 3000)
        self._refresh_all()

    def _on_edit_profile(self, profile_id: str) -> None:
        self._editing_profile_id = profile_id
        self._refresh_grid()

    def _on_key_clicked(self, key: int) -> None:
        profile = self._core.store.profile_by_id(self._editing_profile_id)
        if profile is None:
            return
        if key == self._core.store.settings.mode_key:
            self.statusBar().showMessage(
                "Esta é a tecla de modo — altere em Configurações para reutilizá-la.",
                5000,
            )
            return
        dialog = ActionEditorDialog(
            self, key, profile.action_for(key), runner=self._core.runner
        )
        if dialog.exec() != ActionEditorDialog.Accepted:
            return
        if dialog.remove_requested:
            profile.bindings.pop(key, None)
        elif dialog.result_action is not None:
            profile.bindings[key] = dialog.result_action
        self._core.store.save()
        self._refresh_grid()

    def _on_key_menu(self, key: int) -> None:
        """Menu de contexto da tecla: operações rápidas sem abrir o editor."""
        profile = self._core.store.profile_by_id(self._editing_profile_id)
        if profile is None:
            return
        if key == self._core.store.settings.mode_key:
            self.statusBar().showMessage(
                "Esta é a tecla de modo — altere em Configurações para reutilizá-la.",
                5000,
            )
            return

        action = profile.action_for(key)
        menu = QMenu(self)

        editar = menu.addAction("Editar…")
        testar = menu.addAction("Testar (3 s)")
        menu.addSeparator()
        copiar = menu.addAction("Copiar ação")
        colar = menu.addAction("Colar ação")
        menu.addSeparator()
        limpar = menu.addAction("Limpar tecla")

        for item in (testar, copiar, limpar):
            item.setEnabled(action is not None)
        colar.setEnabled(self._clipboard_action is not None)

        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        if chosen is editar:
            self._on_key_clicked(key)
        elif chosen is testar and action is not None:
            self._test_action(action)
        elif chosen is copiar and action is not None:
            self._clipboard_action = copy.deepcopy(action)
            self.statusBar().showMessage(
                f"Ação da tecla {key + 1} copiada.", 3000
            )
        elif chosen is colar and self._clipboard_action is not None:
            profile.bindings[key] = copy.deepcopy(self._clipboard_action)
            self._core.store.save()
            self._refresh_grid()
        elif chosen is limpar:
            profile.bindings.pop(key, None)
            self._core.store.save()
            self._refresh_grid()

    def _test_action(self, action: Action) -> None:
        """Executa a ação após um intervalo, como faz o editor.

        O atraso existe para o usuário levar o foco à janela alvo: um
        atalho como Ctrl+C iria para o configurador se disparasse já.
        """
        self.statusBar().showMessage(
            "Executando em 3 segundos — leve o foco à janela alvo…", 3000
        )
        QTimer.singleShot(3000, lambda: self._core.runner.submit(action))

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self, self._core.store.settings, self._core.store.profiles
        )
        self._settings_dialog = dialog
        accepted = dialog.exec() == SettingsDialog.Accepted
        self._settings_dialog = None
        if accepted:
            self._core.store.save()
            try:
                autostart.apply(self._core.store.settings.start_with_windows)
            except OSError:
                self.statusBar().showMessage(
                    "Não foi possível atualizar a inicialização com o Windows.", 6000
                )
            self._refresh_all()

    # ------------------------------------------------------------ refresh

    def _refresh_all(self) -> None:
        self._profile_panel.refresh()
        self._refresh_grid()
        self._refresh_preview()
        self._refresh_tray_profiles()

    def _refresh_tray_profiles(self) -> None:
        """Reconstrói o submenu de perfis da bandeja."""
        menu = self._tray_profiles_menu
        menu.clear()
        profiles = self._core.store.profiles
        menu.setEnabled(bool(profiles))
        active_id = self._core.store.active_profile_id
        for profile in profiles:
            action = menu.addAction(profile.name)
            action.setCheckable(True)
            action.setChecked(profile.id == active_id)
            action.triggered.connect(
                lambda _checked=False, pid=profile.id: (
                    self._core.controller.activate_profile(pid)
                )
            )

    def _refresh_grid(self) -> None:
        profile = self._core.store.profile_by_id(self._editing_profile_id)
        if profile is None:
            profile = self._core.store.active_profile
            self._editing_profile_id = profile.id if profile else None
        self._grid_title.setText(
            f"Atalhos do perfil: {profile.name}" if profile else ""
        )
        self._grid.refresh(profile, self._core.store.settings.mode_key)

    def _refresh_preview(self) -> None:
        """Espelha na UI o que o display físico está mostrando."""
        profile = self._core.store.active_profile
        if profile is None:
            return
        if profile.icon_path:
            try:
                payload = icons.icon_payload(profile.icon_path)
                self._oled.show_message(protocol.msg_image(payload))
                return
            except (OSError, ValueError):
                pass
        self._oled.show_message(protocol.msg_text([profile.name]))

    # ------------------------------------------------------------ ciclo

    def closeEvent(self, event) -> None:  # noqa: N802 — API Qt
        # Nos dois caminhos (esconder ou sair) o layout atual é o que o
        # usuário quer reencontrar na próxima abertura.
        self._save_layout()
        if not self._quitting and self._tray.isVisible():
            # Fechar a janela apenas esconde: o macropad continua funcionando.
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self._tray_notified = True
                self._tray.showMessage(
                    APP_NAME,
                    "Continuo rodando em segundo plano — o macropad segue "
                    "funcionando. Use o ícone da bandeja para reabrir ou sair.",
                    QSystemTrayIcon.Information,
                    5000,
                )
            return
        if self._simulator_window is not None:
            self._simulator_window.close()
        self._tray.hide()
        self._core.shutdown()
        super().closeEvent(event)
        # Com setQuitOnLastWindowClosed(False), o loop de eventos precisa
        # ser encerrado explicitamente.
        from PySide6.QtWidgets import QApplication

        QApplication.quit()


def _app_icon() -> QIcon:
    """Desenha o ícone do aplicativo (grade 3x6 de teclas) em tempo real."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QBrush(QColor("#14171e")))
    painter.setPen(QColor("#2a2f3a"))
    painter.drawRoundedRect(2, 8, 60, 48, 10, 10)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor("#8cebff")))
    for row in range(3):
        for col in range(6):
            painter.drawRoundedRect(8 + col * 9, 16 + row * 12, 6, 8, 2, 2)
    painter.end()
    return QIcon(pixmap)
