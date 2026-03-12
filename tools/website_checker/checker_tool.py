import requests, time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

class CheckWorker(QThread):
    result = Signal(str, int, float, str)
    def __init__(self, urls): super().__init__(); self.urls = urls
    def run(self):
        for url in self.urls:
            u = url if url.startswith("http") else f"https://{url}"
            try:
                t = time.time()
                r = requests.get(u, timeout=10, allow_redirects=True)
                elapsed = (time.time() - t) * 1000
                self.result.emit(url, r.status_code, elapsed, r.reason)
            except Exception as e:
                self.result.emit(url, 0, 0, str(e))

class WebsiteCheckerTool(QWidget):
    name = "Website Status Checker"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("✅ Website Status Checker")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Enter URLs (one per line):"))
        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText("google.com\nhttps://github.com\nexample.org")
        self.urls_input.setMaximumHeight(120)
        layout.addWidget(self.urls_input)

        check = QPushButton("Check All URLs")
        check.clicked.connect(self._check)
        layout.addWidget(check)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["URL", "Status", "Response (ms)", "Message"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 250); self.table.setColumnWidth(1, 80); self.table.setColumnWidth(2, 120)
        layout.addWidget(self.table)
        layout.addStretch()

    def _check(self):
        urls = [u.strip() for u in self.urls_input.toPlainText().split("\n") if u.strip()]
        if not urls: return
        self.table.setRowCount(0)
        self._worker = CheckWorker(urls)
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, url, status, ms, msg):
        row = self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(url))
        status_item = QTableWidgetItem(str(status) if status else "ERR")
        if 200 <= status < 300:
            status_item.setForeground(QColor("#4CAF50"))
        elif status >= 400:
            status_item.setForeground(QColor("#F44336"))
        else:
            status_item.setForeground(QColor("#FF9800"))
        self.table.setItem(row, 1, status_item)
        self.table.setItem(row, 2, QTableWidgetItem(f"{ms:.0f}" if ms else "N/A"))
        self.table.setItem(row, 3, QTableWidgetItem(msg))

# HTTP Tester
#cat > /home/claude/multitool_studio/tools/http_tester/__init__.py << 'EOF'
#from .http_tool import HTTPTesterTool
#TOOL_META = {"id": "http_tester", "name": "HTTP Request Tester", "category": "network", "widget_class": HTTPTesterTool}
