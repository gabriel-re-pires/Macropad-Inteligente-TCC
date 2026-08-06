"""Diálogo de configurações globais.

- Tecla de modo: escolhida na lista ou capturada pressionando a tecla
  física no próprio macropad ("defina no próprio teclado").
- Integração Home Assistant: URL + token de longa duração, com teste.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..actions.base import ActionError
from ..core.models import KEY_COUNT, Settings
from ..integrations import home_assistant, obs


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None, settings: Settings) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumWidth(460)
        self._settings = settings
        # Ativado enquanto o usuário estiver "capturando" a tecla de modo.
        self.capturing_mode_key = False

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Desabilitada", None)
        for i in range(KEY_COUNT):
            self._mode_combo.addItem(f"Tecla {i + 1}", i)
        index = self._mode_combo.findData(settings.mode_key)
        self._mode_combo.setCurrentIndex(max(index, 0))
        form.addRow("Tecla de modo:", self._mode_combo)

        self._capture_button = QPushButton("Capturar do macropad…")
        self._capture_button.setToolTip(
            "Clique e em seguida pressione, no macropad, a tecla que "
            "alternará os perfis."
        )
        self._capture_button.clicked.connect(self._start_capture)
        form.addRow("", self._capture_button)

        general_title = QLabel("Comportamento")
        general_title.setObjectName("panelTitle")
        form.addRow(general_title)
        self._auto_switch_check = QCheckBox(
            "Trocar de perfil automaticamente pelo aplicativo em foco"
        )
        self._auto_switch_check.setToolTip(
            "Vincule aplicativos a um perfil pelo botão “Apps vinculados…” "
            "no painel de perfis. A tecla de modo continua funcionando e "
            "prevalece até o foco mudar para outro app vinculado."
        )
        self._auto_switch_check.setChecked(settings.auto_switch_enabled)
        form.addRow(self._auto_switch_check)
        self._autostart_check = QCheckBox(
            "Iniciar com o Windows (em segundo plano, na bandeja)"
        )
        self._autostart_check.setChecked(settings.start_with_windows)
        form.addRow(self._autostart_check)

        ha_title = QLabel("Home Assistant")
        ha_title.setObjectName("panelTitle")
        form.addRow(ha_title)
        self._ha_url = QLineEdit(settings.ha_url)
        self._ha_url.setPlaceholderText("http://homeassistant.local:8123")
        form.addRow("URL:", self._ha_url)
        self._ha_token = QLineEdit(settings.ha_token)
        self._ha_token.setEchoMode(QLineEdit.Password)
        self._ha_token.setPlaceholderText("Token de acesso de longa duração")
        form.addRow("Token:", self._ha_token)
        test_button = QPushButton("Testar conexão")
        test_button.clicked.connect(self._test_ha)
        form.addRow("", test_button)

        obs_title = QLabel("OBS Studio (WebSocket)")
        obs_title.setObjectName("panelTitle")
        form.addRow(obs_title)
        self._obs_host = QLineEdit(settings.obs_host)
        self._obs_host.setPlaceholderText("localhost")
        form.addRow("Host:", self._obs_host)
        self._obs_port = QSpinBox()
        self._obs_port.setRange(1, 65535)
        self._obs_port.setValue(settings.obs_port)
        form.addRow("Porta:", self._obs_port)
        self._obs_password = QLineEdit(settings.obs_password)
        self._obs_password.setEchoMode(QLineEdit.Password)
        self._obs_password.setPlaceholderText(
            "Senha do WebSocket (Ferramentas → Configurações do WebSocket)"
        )
        form.addRow("Senha:", self._obs_password)
        obs_test = QPushButton("Testar conexão")
        obs_test.clicked.connect(self._test_obs)
        form.addRow("", obs_test)

        layout.addLayout(form)

        note = QLabel(
            "O token fica salvo em texto no arquivo de configuração local; "
            "use um token exclusivo para o macropad e revogue-o se necessário."
        )
        note.setWordWrap(True)
        note.setObjectName("hint")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------- captura

    def _start_capture(self) -> None:
        self.capturing_mode_key = True
        self._capture_button.setText("Pressione uma tecla no macropad…")
        self._capture_button.setEnabled(False)

    def key_captured(self, key: int) -> None:
        """Chamado pela janela principal quando o dispositivo envia uma tecla."""
        if not self.capturing_mode_key:
            return
        self.capturing_mode_key = False
        index = self._mode_combo.findData(key)
        if index >= 0:
            self._mode_combo.setCurrentIndex(index)
        self._capture_button.setText("Capturar do macropad…")
        self._capture_button.setEnabled(True)

    # -------------------------------------------------------------- HA

    def _test_ha(self) -> None:
        url = self._ha_url.text().strip()
        token = self._ha_token.text().strip()
        if not url or not token:
            QMessageBox.warning(self, "Home Assistant", "Preencha URL e token.")
            return
        try:
            message = home_assistant.check_connection(url, token)
        except ActionError as exc:
            QMessageBox.critical(self, "Home Assistant", f"Falha no teste: {exc}")
            return
        QMessageBox.information(self, "Home Assistant", f"Conectado: {message}")

    def _test_obs(self) -> None:
        try:
            message = obs.check_connection(
                self._obs_host.text().strip() or "localhost",
                self._obs_port.value(),
                self._obs_password.text(),
            )
        except ActionError as exc:
            QMessageBox.critical(self, "OBS Studio", f"Falha no teste: {exc}")
            return
        QMessageBox.information(self, "OBS Studio", f"Conectado: {message}")

    def _accept(self) -> None:
        self._settings.mode_key = self._mode_combo.currentData()
        self._settings.auto_switch_enabled = self._auto_switch_check.isChecked()
        self._settings.start_with_windows = self._autostart_check.isChecked()
        self._settings.ha_url = self._ha_url.text().strip()
        self._settings.ha_token = self._ha_token.text().strip()
        self._settings.obs_host = self._obs_host.text().strip() or "localhost"
        self._settings.obs_port = self._obs_port.value()
        self._settings.obs_password = self._obs_password.text()
        self.accept()
