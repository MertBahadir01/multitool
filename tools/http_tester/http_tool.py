import requests, json, time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTextEdit, QTabWidget, QGroupBox, QTableWidget, QTableWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

class RequestWorker(QThread):
    result = Signal(dict)
    error = Signal(str)
    def __init__(self, method, url, headers, body):
        super().__init__()
        self.method, self.url, self.headers, self.body = method, url, headers, body
    def run(self):
        try:
            t = time.time()
            r = requests.request(self.method, self.url, headers=self.headers,
                                  data=self.body.encode() if self.body else None, timeout=30)
            elapsed = (time.time() - t) * 1000
            self.result.emit({"status": r.status_code, "reason": r.reason, "headers": dict(r.headers),
                               "body": r.text, "elapsed": elapsed})
        except Exception as e:
            self.error.emit(str(e))

class HTTPTesterTool(QWidget):
    name = "HTTP Request Tester"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("📡 HTTP Request Tester")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.method = QComboBox(); self.method.addItems(["GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"])
        self.method.setFixedWidth(100)
        row.addWidget(self.method)
        self.url_input = QLineEdit(); self.url_input.setPlaceholderText("https://api.example.com/endpoint")
        row.addWidget(self.url_input)
        send = QPushButton("Send"); send.clicked.connect(self._send)
        row.addWidget(send)
        layout.addLayout(row)

        tabs = QTabWidget()
        # Headers tab
        hdr_w = QWidget(); hl = QVBoxLayout(hdr_w)
        hl.addWidget(QLabel("Headers (one per line: Key: Value)"))
        self.headers_input = QTextEdit()
        self.headers_input.setPlaceholderText("Content-Type: application/json\nAuthorization: Bearer token")
        hl.addWidget(self.headers_input)
        tabs.addTab(hdr_w, "Headers")
        # Body tab
        body_w = QWidget(); bl = QVBoxLayout(body_w)
        bl.addWidget(QLabel("Request Body:"))
        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText('{"key": "value"}')
        bl.addWidget(self.body_input)
        tabs.addTab(body_w, "Body")
        layout.addWidget(tabs)

        layout.addWidget(QLabel("Response:"))
        self.response = QTextEdit(); self.response.setReadOnly(True)
        self.response.setFont(QFont("Courier New", 11))
        layout.addWidget(self.response)

    def _parse_headers(self):
        headers = {}
        for line in self.headers_input.toPlainText().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
        return headers

    def _send(self):
        url = self.url_input.text().strip()
        if not url: return
        self.response.setPlainText("Sending request...")
        self._worker = RequestWorker(self.method.currentText(), url,
                                      self._parse_headers(), self.body_input.toPlainText())
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(lambda e: self.response.setPlainText(f"Error: {e}"))
        self._worker.start()

    def _on_result(self, data):
        lines = [f"Status: {data['status']} {data['reason']}", f"Time: {data['elapsed']:.0f}ms", "",
                 "=== Headers ==="]
        for k, v in data['headers'].items(): lines.append(f"{k}: {v}")
        lines += ["", "=== Body ==="]
        try:
            body = json.dumps(json.loads(data['body']), indent=2)
        except: body = data['body']
        lines.append(body)
        self.response.setPlainText("\n".join(lines))
