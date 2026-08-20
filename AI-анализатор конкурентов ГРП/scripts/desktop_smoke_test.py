from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from desktop.main import EmbeddedBackend, MainWindow


def main() -> None:
    backend = EmbeddedBackend()
    backend.start()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    QTimer.singleShot(1800, app.quit)
    exit_code = app.exec()
    backend.stop()
    backend.join(timeout=5)
    if exit_code != 0:
        raise SystemExit(exit_code)
    if backend.is_alive():
        raise RuntimeError("Встроенный backend не остановился")
    print("desktop_ui=ok embedded_backend=ok")


if __name__ == "__main__":
    main()

