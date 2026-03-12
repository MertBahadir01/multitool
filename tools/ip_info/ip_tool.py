import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

class FetchWorker(QThread):
    result = Signal(dict)
    error = Signal(str)
    def __init__(self, ip): super().__init__(); self.ip = ip
    def run(self):
        try:
            url = f"https://ipapi.co/{self.ip}/json/" if self.ip else "https://ipapi.co/json/"
            r = requests.get(url, timeout=10)
            self.result.emit(r.json())
        except Exception as e:
            self.error.emit(str(e))

class IPInfoTool(QWidget):
    name = "IP Info Lookup"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🌍 IP Info Lookup")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.ip_input = QLineEdit(); self.ip_input.setPlaceholderText("Enter IP (leave blank for your IP)")
        row.addWidget(self.ip_input)
        lookup = QPushButton("Lookup"); lookup.clicked.connect(self._lookup)
        row.addWidget(lookup)
        layout.addLayout(row)

        self.result = QTextEdit(); self.result.setReadOnly(True)
        self.result.setFont(QFont("Courier New", 12))
        layout.addWidget(self.result)
        layout.addStretch()

    def _lookup(self):
        self.result.setPlainText("Looking up...")
        ip = self.ip_input.text().strip()
        self._worker = FetchWorker(ip)
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(lambda e: self.result.setPlainText(f"Error: {e}"))
        self._worker.start()

    def _on_result(self, data):
        if "error" in data:
            self.result.setPlainText(f"Error: {data.get('reason', 'Unknown')}")
            return
        lines = []
        fields = [("IP", "ip"), ("City", "city"), ("Region", "region"), ("Country", "country_name"),
                  ("Postal", "postal"), ("Latitude", "latitude"), ("Longitude", "longitude"),
                  ("Timezone", "timezone"), ("ISP", "org"), ("ASN", "asn")]
        for label, key in fields:
            val = data.get(key, "N/A")
            lines.append(f"{label:<15}: {val}")
        self.result.setPlainText("\n".join(lines))
