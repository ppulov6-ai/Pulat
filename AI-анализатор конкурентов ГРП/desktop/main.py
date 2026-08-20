from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("API_HOST", "127.0.0.1")
os.environ.setdefault("API_PORT", "8765")

import requests
import uvicorn
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backend.main import app


API_URL = "http://127.0.0.1:8765"


class EmbeddedBackend(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True, name="embedded-fastapi")
        config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


class Worker(QThread):
    success = pyqtSignal(object)
    failure = pyqtSignal(str)

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            self.success.emit(self.fn())
        except Exception as exc:
            self.failure.emit(str(exc))


class ApiClient:
    @staticmethod
    def _parse(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Backend вернул HTTP {response.status_code}") from exc
        if not response.ok:
            raise RuntimeError(str(payload.get("detail", payload)))
        return payload

    def health(self) -> dict[str, Any]:
        return self._parse(requests.get(f"{API_URL}/health", timeout=3))

    def analyze_text(self, text: str, company: str) -> dict[str, Any]:
        response = requests.post(
            f"{API_URL}/analyze_text",
            json={"text": text, "company_name": company or None},
            timeout=70,
        )
        return self._parse(response)

    def analyze_image(self, path: str, company: str) -> dict[str, Any]:
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        with open(path, "rb") as stream:
            response = requests.post(
                f"{API_URL}/analyze_image",
                files={"file": (Path(path).name, stream, mime)},
                data={"company_name": company},
                timeout=90,
            )
        return self._parse(response)

    def parse_site(self, competitor: str) -> dict[str, Any]:
        response = requests.post(
            f"{API_URL}/parse_demo",
            json={"competitor": competitor},
            timeout=120,
        )
        return self._parse(response)

    def history(self) -> dict[str, Any]:
        return self._parse(requests.get(f"{API_URL}/history", timeout=5))


STYLE = """
QMainWindow, QWidget { background: #0b0e12; color: #f4f6f8; font: 14px 'Segoe UI'; }
QTabWidget::pane { border: 1px solid #2a313a; border-radius: 8px; }
QTabBar::tab { background: #14191f; padding: 10px 18px; margin-right: 4px; }
QTabBar::tab:selected { background: #f4f6f8; color: #0b0e12; }
QLineEdit, QTextEdit, QComboBox { background: #151b22; border: 1px solid #303946; border-radius: 7px; padding: 8px; }
QPushButton { background: #f4f6f8; color: #0b0e12; border: 0; border-radius: 7px; padding: 9px 14px; font-weight: 600; }
QPushButton:disabled { background: #6a7178; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.client = ApiClient()
        self.worker: Worker | None = None
        self.image_path = ""
        self.setWindowTitle("Pulat GRP Competitor AI")
        self.resize(1050, 760)

        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("Pulat GRP Competitor AI")
        title.setStyleSheet("font-size: 28px; font-weight: 700; margin: 8px 0;")
        self.status = QLabel("Запуск локального backend…")
        self.status.setStyleSheet("color: #f0b44d;")
        layout.addWidget(title)
        layout.addWidget(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._text_tab(), "Текст")
        self.tabs.addTab(self._image_tab(), "Изображение")
        self.tabs.addTab(self._parse_tab(), "Сайт")
        self.tabs.addTab(self._history_tab(), "История")
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs, 2)

        layout.addWidget(QLabel("Результат"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 3)
        self.setCentralWidget(root)

        self.backend_check = Worker(self._wait_backend)
        self.backend_check.success.connect(self._backend_ready)
        self.backend_check.failure.connect(self._error)
        self.backend_check.start()

    def _text_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab)
        self.text_company = QLineEdit(); self.text_input = QTextEdit()
        button = QPushButton("Проанализировать")
        button.clicked.connect(lambda: self._run(lambda: self.client.analyze_text(self.text_input.toPlainText(), self.text_company.text())))
        form.addRow("Компания", self.text_company); form.addRow("Материал", self.text_input); form.addRow(button)
        return tab

    def _image_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab)
        self.image_company = QLineEdit(); self.image_label = QLabel("Файл не выбран")
        choose = QPushButton("Выбрать изображение"); choose.clicked.connect(self._choose_image)
        analyze = QPushButton("Проанализировать")
        analyze.clicked.connect(lambda: self._run(lambda: self.client.analyze_image(self.image_path, self.image_company.text())) if self.image_path else self._error("Выберите изображение"))
        row = QWidget(); box = QHBoxLayout(row); box.addWidget(choose); box.addWidget(self.image_label, 1)
        form.addRow("Компания", self.image_company); form.addRow(row); form.addRow(analyze)
        return tab

    def _parse_tab(self) -> QWidget:
        tab = QWidget(); form = QFormLayout(tab)
        self.competitor = QComboBox()
        for label, value in [("Halliburton", "halliburton"), ("Liberty Energy", "liberty"), ("Jereh", "jereh"), ("SLB", "slb")]:
            self.competitor.addItem(label, value)
        button = QPushButton("Открыть через Selenium и проанализировать")
        button.clicked.connect(lambda: self._run(lambda: self.client.parse_site(self.competitor.currentData())))
        form.addRow("Конкурент", self.competitor); form.addRow(button)
        return tab

    def _history_tab(self) -> QWidget:
        tab = QWidget(); layout = QVBoxLayout(tab)
        button = QPushButton("Обновить историю"); button.clicked.connect(self._load_history)
        layout.addWidget(button); layout.addWidget(QLabel("История отображается в поле результата ниже.")); layout.addStretch()
        return tab

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Изображение", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.image_path = path; self.image_label.setText(Path(path).name)

    def _tab_changed(self, index: int) -> None:
        if index == 3: self._load_history()

    def _load_history(self) -> None:
        self._run(self.client.history)

    def _run(self, fn: Callable[[], Any]) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.status.setText("Обработка…")
        self.worker = Worker(fn)
        self.worker.success.connect(self._show)
        self.worker.failure.connect(self._error)
        self.worker.start()

    def _show(self, payload: object) -> None:
        self.status.setText("Готово")
        self.status.setStyleSheet("color: #3ddc97;")
        self.output.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    def _error(self, message: str) -> None:
        self.status.setText("Ошибка")
        self.status.setStyleSheet("color: #ff6b6b;")
        self.output.setPlainText(f"Ошибка: {message}")

    def _wait_backend(self) -> dict[str, Any]:
        for _ in range(40):
            try:
                return self.client.health()
            except Exception:
                time.sleep(.25)
        raise RuntimeError("Backend не запустился")

    def _backend_ready(self, health: dict[str, Any]) -> None:
        text = "Backend готов; API ключ настроен" if health.get("api_configured") else "Backend готов; добавьте PROXY_API_KEY в .env"
        self.status.setText(text)
        self.status.setStyleSheet("color: #3ddc97;")


def main() -> None:
    backend = EmbeddedBackend(); backend.start()
    qt = QApplication(sys.argv); qt.setStyleSheet(STYLE)
    window = MainWindow(); window.show()
    code = qt.exec(); backend.stop(); sys.exit(code)


if __name__ == "__main__":
    main()
