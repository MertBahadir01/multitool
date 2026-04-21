"""Focus Mode — Pomodoro timer with session logging."""
import os, json
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QListWidget, QProgressBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

DATA_FILE = os.path.join(os.path.expanduser("~"), ".multitool_focus.json")

def _load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except Exception: pass
    return []

def _save(log):
    try:
        with open(DATA_FILE, "w") as f: json.dump(log, f, indent=2)
    except Exception: pass


class FocusModeTool(QWidget):
    name        = "Focus Mode"
    description = "Pomodoro focus timer with session logging"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log     = _load()
        self._seconds = 0
        self._running = False
        self._mode    = "focus"   # focus | break
        self._session_start = None
        self._timer   = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._build_ui()
        self._reset_timer()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(20)

        # Settings
        cfg = QGroupBox("Settings")
        cl  = QHBoxLayout(cfg)
        cl.addWidget(QLabel("Focus (min):"))
        self.focus_spin = QSpinBox(); self.focus_spin.setRange(1,120); self.focus_spin.setValue(25)
        cl.addWidget(self.focus_spin)
        cl.addWidget(QLabel("  Break (min):"))
        self.break_spin = QSpinBox(); self.break_spin.setRange(1,60); self.break_spin.setValue(5)
        cl.addWidget(self.break_spin)
        cl.addStretch()
        lay.addWidget(cfg)

        # Clock display
        self.mode_lbl = QLabel("FOCUS")
        self.mode_lbl.setAlignment(Qt.AlignCenter)
        self.mode_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.mode_lbl.setStyleSheet("color: #00BFA5;")
        lay.addWidget(self.mode_lbl)

        self.clock_lbl = QLabel("25:00")
        self.clock_lbl.setAlignment(Qt.AlignCenter)
        self.clock_lbl.setFont(QFont("Segoe UI", 64, QFont.Bold))
        self.clock_lbl.setStyleSheet("color: #CCCCCC;")
        lay.addWidget(self.clock_lbl)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        lay.addWidget(self.bar)

        # Buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self.start_btn)
        reset_btn = QPushButton("Reset")
        reset_btn.setObjectName("secondary")
        reset_btn.clicked.connect(self._reset_timer)
        btn_row.addWidget(reset_btn)
        skip_btn = QPushButton("Skip to Break")
        skip_btn.setObjectName("secondary")
        skip_btn.clicked.connect(self._skip)
        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888888;")
        lay.addWidget(self.status_lbl)

        # Session log
        log_box = QGroupBox("Session Log")
        ll = QVBoxLayout(log_box)
        self.log_list = QListWidget()
        ll.addWidget(self.log_list)
        lay.addWidget(log_box)

        self._refresh_log()

    def _toggle(self):
        if self._running:
            self._timer.stop()
            self._running = False
            self.start_btn.setText("Resume")
            self.status_lbl.setText("Paused")
        else:
            if not self._session_start:
                self._session_start = datetime.now()
            self._timer.start(1000)
            self._running = True
            self.start_btn.setText("Pause")
            self.status_lbl.setText("Running...")

    def _tick(self):
        self._seconds -= 1
        self._update_display()
        if self._seconds <= 0:
            self._timer.stop()
            self._running = False
            self._complete_session()

    def _complete_session(self):
        if self._mode == "focus" and self._session_start:
            mins = self.focus_spin.value()
            entry = {"date": self._session_start.strftime("%Y-%m-%d %H:%M"), "minutes": mins}
            self._log.append(entry)
            _save(self._log)
            self._refresh_log()
            self.status_lbl.setText(f"Focus session complete! Take a {self.break_spin.value()} min break.")
            self._mode = "break"
        else:
            self.status_lbl.setText("Break over! Ready to focus.")
            self._mode = "focus"
        self._session_start = None
        self.start_btn.setText("Start")
        self._reset_timer()

    def _reset_timer(self):
        self._timer.stop()
        self._running = False
        self._session_start = None
        self.start_btn.setText("Start")
        if self._mode == "focus":
            self._seconds = self.focus_spin.value() * 60
            self._total   = self._seconds
            self.mode_lbl.setText("FOCUS")
            self.mode_lbl.setStyleSheet("color: #00BFA5;")
        else:
            self._seconds = self.break_spin.value() * 60
            self._total   = self._seconds
            self.mode_lbl.setText("BREAK")
            self.mode_lbl.setStyleSheet("color: #FFC107;")
        self._update_display()

    def _skip(self):
        self._timer.stop()
        self._running = False
        self._mode = "break" if self._mode == "focus" else "focus"
        self._reset_timer()

    def _update_display(self):
        m, s = divmod(max(self._seconds, 0), 60)
        self.clock_lbl.setText(f"{m:02d}:{s:02d}")
        pct = int((1 - self._seconds / max(self._total, 1)) * 100)
        self.bar.setValue(pct)

    def _refresh_log(self):
        self.log_list.clear()
        for e in reversed(self._log[-50:]):
            self.log_list.addItem(f"{e['date']}  —  {e['minutes']} min focus session")
