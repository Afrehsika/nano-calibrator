"""Entry point for the Custom Drone Flight Controller Configurator."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import DARK_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("NanoFC Quad-X Configurator")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)

    profiles_dir = Path(__file__).resolve().parent / "profiles"
    window = MainWindow(profiles_dir=profiles_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

