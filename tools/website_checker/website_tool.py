"""
Website Status Checker Tool
"""
import requests
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from core.plugin_manager import ToolInterface


class StatusWorker(QThread):
    result = Signal(str, int, float, str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        url = self.url
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            start = time.time()
            resp = requests.get(url, timeout=10, allow_redirects=True)
            elapsed = (time.time() - start) * 1000
            self.result.emit(url, resp.status_code, elapsed, resp.headers.get("Server", "Unknown"))
        except requests.ConnectionError:
            self.result.emit(url, 0, 0, "Connection Failed")
        except requests.Timeout:
            self.result.emit(url, -1, 10000, "Timeout")
        except Exception as e:
            self.result.emit(url, -2, 0, str(e))


class WebsiteCheckerTool(ToolInterface):
    name = "Website Checker"
    description = "Check if websites are online and measure response time"
    icon = "✅"
    category = "Networking"

    def get_widget(self):
        return WebsiteCheckerWidget()


class WebsiteCheckerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("✅ Website Status Checker")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Single check
        single_group = QGroupBox("Check Single Website")
        single_layout = QHBoxLayout(single_group)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.returnPressed.connect(self._check_single)
        check_btn = QPushButton("Check")
        check_btn.clicked.connect(self._check_single)
        single_layout.addWidget(self.url_input, 1)
        single_layout.addWidget(check_btn)
        layout.addWidget(single_group)

        # Bulk check
        bulk_group = QGroupBox("Bulk Check (one URL per line)")
        bulk_layout = QVBoxLayout(bulk_group)
        self.bulk_input = QLineEdit()
        self.bulk_input.setPlaceholderText("google.com, github.com, example.com")
        bulk_btn = QPushButton("Check All")
        bulk_btn.clicked.connect(self._check_bulk)
        bulk_layout.addWidget(self.bulk_input)
        bulk_layout.addWidget(bulk_btn)
        layout.addWidget(bulk_group)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["URL", "Status", "Response Time", "Server"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 130)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        clear_btn = QPushButton("Clear Results")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.clicked.connect(self.table.setRowCount)
        clear_btn.clicked.connect(lambda: self.table.setRowCount(0))
        layout.addWidget(clear_btn)

    def _check_single(self):
        url = self.url_input.text().strip()
        if url:
            self._check_url(url)

    def _check_bulk(self):
        text = self.bulk_input.text()
        urls = [u.strip() for u in text.replace(',', '\n').split('\n') if u.strip()]
        for url in urls:
            self._check_url(url)

    def _check_url(self, url):
        # Add pending row
        row = self.table.rowCount()
        self.table.insertRow(row)
        display_url = url if url.startswith("http") else "https://" + url
        self.table.setItem(row, 0, QTableWidgetItem(display_url))
        pending = QTableWidgetItem("Checking...")
        pending.setForeground(QColor("#FF9800"))
        self.table.setItem(row, 1, pending)
        self.table.setItem(row, 2, QTableWidgetItem("–"))
        self.table.setItem(row, 3, QTableWidgetItem("–"))

        worker = StatusWorker(url)
        worker.result.connect(lambda u, s, t, srv, r=row: self._update_row(r, u, s, t, srv))
        worker.start()
        self._workers.append(worker)

    def _update_row(self, row, url, status, response_time, server):
        self.table.setItem(row, 0, QTableWidgetItem(url))
        if status == 200:
            status_item = QTableWidgetItem("✓ 200 OK")
            status_item.setForeground(QColor("#4CAF50"))
        elif status > 0:
            status_item = QTableWidgetItem(f"⚠ {status}")
            status_item.setForeground(QColor("#FF9800"))
        elif status == -1:
            status_item = QTableWidgetItem("⏱ Timeout")
            status_item.setForeground(QColor("#F44336"))
        else:
            status_item = QTableWidgetItem("✗ Down")
            status_item.setForeground(QColor("#F44336"))

        self.table.setItem(row, 1, status_item)
        time_str = f"{response_time:.0f} ms" if response_time > 0 else "–"
        self.table.setItem(row, 2, QTableWidgetItem(time_str))
        self.table.setItem(row, 3, QTableWidgetItem(server))
