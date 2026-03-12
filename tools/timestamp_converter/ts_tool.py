import time
from datetime import datetime, timezone
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QTextEdit)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

class TimestampConverterTool(QWidget):
    name = "Timestamp Converter"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_now)
        self._timer.start(1000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🕒 Timestamp Converter")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        grp_now = QGroupBox("Current Time")
        gl = QVBoxLayout(grp_now)
        self.now_lbl = QLabel()
        self.now_lbl.setFont(QFont("Courier New", 13))
        gl.addWidget(self.now_lbl)
        layout.addWidget(grp_now)

        grp = QGroupBox("Unix Timestamp → Human Readable")
        gl2 = QVBoxLayout(grp)
        r = QHBoxLayout()
        self.ts_input = QLineEdit(); self.ts_input.setPlaceholderText("Enter Unix timestamp (e.g. 1700000000)")
        r.addWidget(self.ts_input)
        conv = QPushButton("Convert"); conv.clicked.connect(self._convert_ts)
        r.addWidget(conv)
        gl2.addLayout(r)
        self.ts_result = QTextEdit(); self.ts_result.setReadOnly(True)
        self.ts_result.setFont(QFont("Courier New", 12)); self.ts_result.setMaximumHeight(100)
        gl2.addWidget(self.ts_result)
        layout.addWidget(grp)

        grp2 = QGroupBox("Date → Unix Timestamp")
        gl3 = QVBoxLayout(grp2)
        r2 = QHBoxLayout()
        self.dt_input = QLineEdit(); self.dt_input.setPlaceholderText("YYYY-MM-DD HH:MM:SS")
        r2.addWidget(self.dt_input)
        conv2 = QPushButton("Convert"); conv2.clicked.connect(self._convert_dt)
        r2.addWidget(conv2)
        gl3.addLayout(r2)
        self.dt_result = QLabel("")
        self.dt_result.setFont(QFont("Courier New", 13))
        gl3.addWidget(self.dt_result)
        layout.addWidget(grp2)
        layout.addStretch()
        self._update_now()

    def _update_now(self):
        now = datetime.now()
        utc = datetime.now(timezone.utc)
        ts = int(time.time())
        self.now_lbl.setText(f"Local: {now.strftime('%Y-%m-%d %H:%M:%S')}  |  UTC: {utc.strftime('%Y-%m-%d %H:%M:%S')}  |  Unix: {ts}")

    def _convert_ts(self):
        try:
            ts = int(self.ts_input.text().strip())
            dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            dt_local = datetime.fromtimestamp(ts)
            self.ts_result.setPlainText(f"UTC:   {dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}\nLocal: {dt_local.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            self.ts_result.setPlainText(f"Error: {e}")

    def _convert_dt(self):
        try:
            dt = datetime.strptime(self.dt_input.text().strip(), "%Y-%m-%d %H:%M:%S")
            ts = int(dt.timestamp())
            self.dt_result.setText(f"Unix Timestamp: {ts}")
        except Exception as e:
            self.dt_result.setText(f"Error: {e} (use YYYY-MM-DD HH:MM:SS)")
