from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from mouse_draw_app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
