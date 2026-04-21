"""Typing Speed Test — measures WPM and accuracy."""
import random, time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QProgressBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCharFormat, QColor

PASSAGES = [
    "The quick brown fox jumps over the lazy dog near the riverbank on a sunny afternoon.",
    "Programming is the art of telling another human what one wants the computer to do.",
    "Simplicity is the ultimate sophistication. Do more with less and focus on what matters.",
    "The only way to do great work is to love what you do and never stop learning new things.",
    "Success is not final, failure is not fatal: it is the courage to continue that counts.",
    "In the middle of every difficulty lies opportunity. Keep pushing forward no matter what.",
    "Technology is best when it brings people together and solves real problems in the world.",
    "A journey of a thousand miles begins with a single step taken in the right direction.",
    "The future belongs to those who believe in the beauty of their dreams and act on them.",
    "Knowledge is power. Information is liberating. Education is the premise of progress.",
]


class TypingSpeedTestTool(QWidget):
    name        = "Typing Speed Test"
    description = "Measure your typing speed in WPM with accuracy tracking"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = None
        self._target     = ""
        self._timer      = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._elapsed    = 0
        self._build_ui()
        self._new_test()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        sub = QLabel("Type the passage below as fast and accurately as you can.")
        sub.setStyleSheet("color: #888888;")
        lay.addWidget(sub)

        # Stats bar
        stats_row = QHBoxLayout()
        self.wpm_lbl  = QLabel("WPM: —")
        self.wpm_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.wpm_lbl.setStyleSheet("color: #00BFA5;")
        stats_row.addWidget(self.wpm_lbl)

        self.acc_lbl  = QLabel("Accuracy: —")
        self.acc_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.acc_lbl.setStyleSheet("color: #8BC34A;")
        stats_row.addWidget(self.acc_lbl)

        self.time_lbl = QLabel("Time: 0s")
        self.time_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.time_lbl.setStyleSheet("color: #FFC107;")
        stats_row.addWidget(self.time_lbl)
        stats_row.addStretch()
        lay.addLayout(stats_row)

        # Target passage
        target_box = QGroupBox("Target Passage")
        tl = QVBoxLayout(target_box)
        self.target_lbl = QLabel()
        self.target_lbl.setWordWrap(True)
        self.target_lbl.setFont(QFont("Segoe UI", 13))
        self.target_lbl.setStyleSheet("color: #CCCCCC; padding: 8px;")
        tl.addWidget(self.target_lbl)
        lay.addWidget(target_box)

        # Input
        input_box = QGroupBox("Your Input")
        il = QVBoxLayout(input_box)
        self.input_area = QTextEdit()
        self.input_area.setFont(QFont("Courier New", 13))
        self.input_area.setFixedHeight(100)
        self.input_area.setPlaceholderText("Start typing here...")
        self.input_area.textChanged.connect(self._on_type)
        il.addWidget(self.input_area)
        lay.addWidget(input_box)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        lay.addWidget(self.progress)

        self.result_lbl = QLabel("")
        self.result_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.result_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.result_lbl)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New Test")
        new_btn.clicked.connect(self._new_test)
        btn_row.addWidget(new_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

    def _new_test(self):
        self._timer.stop()
        self._start_time = None
        self._elapsed    = 0
        self._target     = random.choice(PASSAGES)
        self.target_lbl.setText(self._target)
        self.input_area.blockSignals(True)
        self.input_area.clear()
        self.input_area.blockSignals(False)
        self.input_area.setReadOnly(False)
        self.wpm_lbl.setText("WPM: —")
        self.acc_lbl.setText("Accuracy: —")
        self.time_lbl.setText("Time: 0s")
        self.progress.setValue(0)
        self.result_lbl.setText("")
        self.input_area.setFocus()

    def _on_type(self):
        typed = self.input_area.toPlainText()
        if not typed:
            return
        if self._start_time is None:
            self._start_time = time.time()
            self._timer.start(500)

        # Progress
        pct = int(len(typed) / len(self._target) * 100)
        self.progress.setValue(min(pct, 100))

        # Live WPM
        elapsed = time.time() - self._start_time
        words   = len(typed.split())
        wpm     = int(words / (elapsed / 60)) if elapsed > 0 else 0
        self.wpm_lbl.setText(f"WPM: {wpm}")

        # Accuracy
        correct = sum(1 for a, b in zip(typed, self._target) if a == b)
        acc     = int(correct / max(len(typed), 1) * 100)
        self.acc_lbl.setText(f"Accuracy: {acc}%")
        self.acc_lbl.setStyleSheet(f"color: {'#00BFA5' if acc >= 90 else '#FFC107' if acc >= 70 else '#F44336'}; font-size: 16px; font-weight: bold;")

        # Done?
        if typed == self._target:
            self._timer.stop()
            self.input_area.setReadOnly(True)
            self.result_lbl.setText(f"Done!  {wpm} WPM  |  {acc}% accuracy  |  {elapsed:.1f}s")
            self.result_lbl.setStyleSheet("color: #00BFA5;")

    def _tick(self):
        if self._start_time:
            self._elapsed = int(time.time() - self._start_time)
            self.time_lbl.setText(f"Time: {self._elapsed}s")
