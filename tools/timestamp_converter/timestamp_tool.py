"""
Timestamp Converter Tool
"""
import time
from datetime import datetime, timezone
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QComboBox, QFrame
)
from PySide6.QtCore import Qt, QTimer
from core.plugin_manager import ToolInterface


class TimestampTool(ToolInterface):
    name = "Timestamp Converter"
    description = "Convert between Unix timestamps and human-readable dates"
    icon = "⏱️"
    category = "Developer Tools"

    def get_widget(self):
        return TimestampWidget()


class TimestampWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._start_clock()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        title = QLabel("⏱️ Timestamp Converter")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Live clock
        clock_frame = QFrame()
        clock_frame.setObjectName("card")
        clock_frame.setStyleSheet("QFrame { background: #1A1A2E; border-radius: 12px; padding: 16px; }")
        clock_layout = QVBoxLayout(clock_frame)

        self.current_ts = QLabel("")
        self.current_ts.setStyleSheet("color: #00BFA5; font-size: 28px; font-weight: bold; font-family: 'Courier New';")
        self.current_ts.setAlignment(Qt.AlignCenter)

        self.current_dt = QLabel("")
        self.current_dt.setStyleSheet("color: #AAAAAA; font-size: 13px;")
        self.current_dt.setAlignment(Qt.AlignCenter)

        clock_layout.addWidget(QLabel("Current Unix Timestamp", alignment=Qt.AlignCenter))
        clock_layout.addWidget(self.current_ts)
        clock_layout.addWidget(self.current_dt)
        layout.addWidget(clock_frame)

        # Unix → Human
        unix_group = QGroupBox("Unix Timestamp → Human Date")
        unix_layout = QVBoxLayout(unix_group)
        unix_row = QHBoxLayout()
        self.unix_input = QLineEdit()
        self.unix_input.setPlaceholderText("Enter Unix timestamp (e.g. 1700000000)")
        self.ts_unit = QComboBox()
        self.ts_unit.addItems(["Seconds", "Milliseconds"])
        convert_btn = QPushButton("Convert")
        convert_btn.clicked.connect(self._ts_to_human)
        unix_row.addWidget(self.unix_input, 1)
        unix_row.addWidget(self.ts_unit)
        unix_row.addWidget(convert_btn)
        unix_layout.addLayout(unix_row)
        self.unix_result = QLabel("")
        self.unix_result.setStyleSheet("color: #00BFA5; font-family: 'Courier New'; font-size: 13px;")
        unix_layout.addWidget(self.unix_result)
        layout.addWidget(unix_group)

        # Human → Unix
        human_group = QGroupBox("Human Date → Unix Timestamp")
        human_layout = QVBoxLayout(human_group)
        human_row = QHBoxLayout()
        self.human_input = QLineEdit()
        self.human_input.setPlaceholderText("YYYY-MM-DD HH:MM:SS (e.g. 2024-01-15 12:30:00)")
        convert2_btn = QPushButton("Convert")
        convert2_btn.clicked.connect(self._human_to_ts)
        human_row.addWidget(self.human_input, 1)
        human_row.addWidget(convert2_btn)
        human_layout.addLayout(human_row)

        now_btn = QPushButton("Use Current Time")
        now_btn.setObjectName("btn_secondary")
        now_btn.clicked.connect(self._use_now)
        human_layout.addWidget(now_btn)

        self.human_result = QLabel("")
        self.human_result.setStyleSheet("color: #00BFA5; font-family: 'Courier New'; font-size: 13px;")
        human_layout.addWidget(self.human_result)
        layout.addWidget(human_group)

        # Formats reference
        ref_group = QGroupBox("Common Formats")
        ref_layout = QVBoxLayout(ref_group)
        formats = [
            ("ISO 8601", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("RFC 2822", datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")),
            ("US Format", datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")),
            ("EU Format", datetime.now().strftime("%d.%m.%Y %H:%M:%S")),
        ]
        for fmt_name, fmt_val in formats:
            row = QHBoxLayout()
            name_lbl = QLabel(fmt_name + ":")
            name_lbl.setStyleSheet("color: #777777; min-width: 100px;")
            val_lbl = QLabel(fmt_val)
            val_lbl.setStyleSheet("color: #CCCCCC; font-family: 'Courier New';")
            row.addWidget(name_lbl)
            row.addWidget(val_lbl)
            row.addStretch()
            ref_layout.addLayout(row)
        layout.addWidget(ref_group)
        layout.addStretch()

    def _start_clock(self):
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        ts = int(time.time())
        dt = datetime.now()
        self.current_ts.setText(str(ts))
        self.current_dt.setText(dt.strftime("%A, %B %d, %Y  %H:%M:%S"))

    def _ts_to_human(self):
        try:
            val = float(self.unix_input.text().strip())
            if self.ts_unit.currentIndex() == 1:
                val /= 1000
            dt = datetime.fromtimestamp(val)
            dt_utc = datetime.fromtimestamp(val, tz=timezone.utc)
            result = (
                f"Local:    {dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"UTC:      {dt_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"ISO 8601: {dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
            self.unix_result.setText(result)
        except Exception as e:
            self.unix_result.setText(f"Error: {e}")
            self.unix_result.setStyleSheet("color: #F44336;")

    def _human_to_ts(self):
        text = self.human_input.text().strip()
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(text, fmt)
                ts = int(dt.timestamp())
                ts_ms = ts * 1000
                self.human_result.setText(
                    f"Unix (seconds):      {ts}\n"
                    f"Unix (milliseconds): {ts_ms}\n"
                    f"Parsed as:           {dt.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.human_result.setStyleSheet("color: #00BFA5; font-family: 'Courier New'; font-size: 13px;")
                return
            except ValueError:
                continue
        self.human_result.setText("Could not parse date. Use format: YYYY-MM-DD HH:MM:SS")
        self.human_result.setStyleSheet("color: #F44336;")

    def _use_now(self):
        self.human_input.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
