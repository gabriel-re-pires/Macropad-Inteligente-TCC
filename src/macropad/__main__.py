"""Ponto de entrada: ``python -m macropad``."""

from __future__ import annotations

import logging
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME, ORG_NAME, __version__
    from .app import MacropadApp
    from .core import logs
    from .ui.main_window import MainWindow
    from .ui.style import STYLESHEET

    log_path = logs.setup()
    logging.getLogger(__name__).info(
        "%s %s iniciando (log: %s)", APP_NAME, __version__, log_path or "somente console"
    )

    start_minimized = "--minimized" in sys.argv

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setOrganizationName(ORG_NAME)
    qt_app.setStyleSheet(STYLESHEET)
    # Fechar a janela minimiza para a bandeja; sair de verdade é pelo menu.
    qt_app.setQuitOnLastWindowClosed(False)

    core = MacropadApp()
    window = MainWindow(core)
    if not start_minimized:
        window.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
