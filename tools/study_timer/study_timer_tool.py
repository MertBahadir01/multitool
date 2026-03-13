"""Study Timer / Pomodoro Tool — focus/break cycles, per-subject tracking, DB logging."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QSpinBox, QTabWidget, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPen
from PySide6.QtCore import QRectF
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import TimerService, LessonsService


class CircleTimerWidget(QWidget):
    """Circular countdown display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self._total = 1
        self._remaining = 1
        self._color = QColor("#00BFA5")
        self._label = "Focus"

    def set(self, total: int, remaining: int, color: QColor, label: str):
        self._total = max(total, 1)
        self._remaining = remaining
        self._color = color
        self._label = label
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W = self.width()
        cx, cy = W // 2, W // 2
        r = W // 2 - 16
        # background circle
        painter.setPen(QPen(QColor("#2D2D2D"), 12))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        # progress arc
        span = int(-360 * 16 * self._remaining / self._total)
        painter.setPen(QPen(self._color, 12))
        painter.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 90 * 16, span)
        # time text
        mins = self._remaining // 60
        secs = self._remaining % 60
        painter.setPen(self._color)
        painter.setFont(QFont("Segoe UI", 26, QFont.Bold))
        painter.drawText(QRectF(0, cy - 20, W, 40), Qt.AlignCenter, f"{mins:02d}:{secs:02d}")
        # label
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(QRectF(0, cy + 24, W, 24), Qt.AlignCenter, self._label)
        painter.end()


class StudyTimerTool(QWidget):
    name = "Study Timer"
    description = "Pomodoro timer with per-subject session logging"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = TimerService(user) if user else None
        self._les_svc = LessonsService(user) if user else None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._running = False
        self._is_break = False
        self._remaining = 0
        self._focus_mins = 25
        self._break_mins = 5
        self._session_mins = 0
        self._session_subject = ""
        self._elapsed_focus = 0
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("⏱️ Study Timer")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        root.addWidget(hdr)

        tabs = QTabWidget()

        # Timer tab
        timer_tab = QWidget()
        tl = QVBoxLayout(timer_tab)
        tl.setContentsMargins(24, 24, 24, 24)
        tl.setSpacing(16)
        tl.setAlignment(Qt.AlignTop)

        # Settings row
        settings = QHBoxLayout()
        settings.addWidget(QLabel("Focus (min):"))
        self.focus_spin = QSpinBox()
        self.focus_spin.setRange(1, 120)
        self.focus_spin.setValue(25)
        self.focus_spin.valueChanged.connect(self._on_settings_change)
        settings.addWidget(self.focus_spin)
        settings.addWidget(QLabel("Break (min):"))
        self.break_spin = QSpinBox()
        self.break_spin.setRange(1, 60)
        self.break_spin.setValue(5)
        self.break_spin.valueChanged.connect(self._on_settings_change)
        settings.addWidget(self.break_spin)
        settings.addWidget(QLabel("Subject:"))
        self.subject_combo = QComboBox()
        self.subject_combo.setEditable(True)
        self.subject_combo.addItems(["General", "Math", "Physics", "Chemistry",
                                      "Biology", "History", "Geography", "Turkish", "English"])
        if self._les_svc:
            for les in self._les_svc.get_lessons():
                self.subject_combo.addItem(les["name"])
        settings.addWidget(self.subject_combo, 1)
        tl.addLayout(settings)

        # Circle + controls
        center = QHBoxLayout()
        center.setAlignment(Qt.AlignCenter)
        center_col = QVBoxLayout()
        center_col.setAlignment(Qt.AlignCenter)
        center_col.setSpacing(20)

        self.circle = CircleTimerWidget()
        center_col.addWidget(self.circle, alignment=Qt.AlignCenter)

        self.status_lbl = QLabel("Ready to focus 🎯")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color:#888; font-size:13px;")
        center_col.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(12)
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setFixedSize(100, 40)
        self.start_btn.clicked.connect(self._toggle_timer)
        btn_row.addWidget(self.start_btn)
        self.reset_btn = QPushButton("⏹ Reset")
        self.reset_btn.setFixedSize(100, 40)
        self.reset_btn.setObjectName("secondary")
        self.reset_btn.clicked.connect(self._reset_timer)
        btn_row.addWidget(self.reset_btn)
        self.skip_btn = QPushButton("⏭ Skip")
        self.skip_btn.setFixedSize(100, 40)
        self.skip_btn.setObjectName("secondary")
        self.skip_btn.clicked.connect(self._skip_phase)
        btn_row.addWidget(self.skip_btn)
        center_col.addLayout(btn_row)
        center.addLayout(center_col)
        tl.addLayout(center)

        self.session_lbl = QLabel("Session: 0 min focused today")
        self.session_lbl.setAlignment(Qt.AlignCenter)
        self.session_lbl.setStyleSheet("color:#00BFA5; font-size:13px;")
        tl.addWidget(self.session_lbl)
        tl.addStretch()
        tabs.addTab(timer_tab, "⏱️ Timer")

        # History tab
        hist_tab = QWidget()
        hl2 = QVBoxLayout(hist_tab)
        hl2.setContentsMargins(16, 16, 16, 16)
        self.hist_table = QTableWidget(0, 4)
        self.hist_table.setHorizontalHeaderLabels(["Subject", "Duration", "Type", "Date"])
        self.hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hl2.addWidget(self.hist_table, 1)
        tabs.addTab(hist_tab, "📋 History")

        root.addWidget(tabs, 1)
        self._reset_timer()

    def _on_settings_change(self):
        if not self._running:
            self._focus_mins = self.focus_spin.value()
            self._break_mins = self.break_spin.value()
            self._reset_timer()

    def _reset_timer(self):
        self._timer.stop()
        self._running = False
        self._is_break = False
        self._focus_mins = self.focus_spin.value()
        self._break_mins = self.break_spin.value()
        self._remaining = self._focus_mins * 60
        self.start_btn.setText("▶ Start")
        self.status_lbl.setText("Ready to focus 🎯")
        self.circle.set(self._remaining, self._remaining, QColor("#00BFA5"), "Focus")

    def _toggle_timer(self):
        if self._running:
            self._timer.stop()
            self._running = False
            self.start_btn.setText("▶ Resume")
            self.status_lbl.setText("Paused")
        else:
            self._running = True
            self._session_subject = self.subject_combo.currentText()
            self._timer.start(1000)
            self.start_btn.setText("⏸ Pause")
            phase = "Break" if self._is_break else "Focus"
            self.status_lbl.setText(f"{'☕ Taking a break…' if self._is_break else '🎯 Focusing…'}")

    def _tick(self):
        self._remaining -= 1
        if not self._is_break:
            self._elapsed_focus += 1
        color = QColor("#FF9800") if self._is_break else QColor("#00BFA5")
        label = "Break" if self._is_break else "Focus"
        total = (self._break_mins if self._is_break else self._focus_mins) * 60
        self.circle.set(total, self._remaining, color, label)
        if self._remaining <= 0:
            self._phase_complete()

    def _phase_complete(self):
        self._timer.stop()
        self._running = False
        if not self._is_break:
            # log focus session
            mins = self._focus_mins
            if self._svc:
                self._svc.log_session(self._session_subject, mins, "focus")
            self._load_history()
            self._is_break = True
            self._remaining = self._break_mins * 60
            self.start_btn.setText("▶ Start Break")
            self.status_lbl.setText("✅ Focus complete! Start break when ready.")
        else:
            self._is_break = False
            self._remaining = self._focus_mins * 60
            self.start_btn.setText("▶ Start Focus")
            self.status_lbl.setText("☕ Break done! Ready for next session.")
        color = QColor("#FF9800") if self._is_break else QColor("#00BFA5")
        total = (self._break_mins if self._is_break else self._focus_mins) * 60
        self.circle.set(total, self._remaining, color, "Break" if self._is_break else "Focus")

    def _skip_phase(self):
        self._timer.stop()
        self._running = False
        if not self._is_break:
            elapsed_mins = max(1, (self._focus_mins * 60 - self._remaining) // 60)
            if self._svc and elapsed_mins > 0:
                self._svc.log_session(self._session_subject, elapsed_mins, "focus")
            self._load_history()
        self._is_break = not self._is_break
        self._remaining = (self._break_mins if self._is_break else self._focus_mins) * 60
        self.start_btn.setText("▶ Start")
        color = QColor("#FF9800") if self._is_break else QColor("#00BFA5")
        total = self._remaining
        self.circle.set(total, total, color, "Break" if self._is_break else "Focus")

    def _load_history(self):
        if not self._svc:
            return
        sessions = self._svc.get_sessions(limit=100)
        self.hist_table.setRowCount(0)
        today_focus = 0
        import datetime
        today = datetime.date.today().isoformat()
        for s in sessions:
            if s.get("session_type") == "focus" and str(s.get("created_at", ""))[:10] == today:
                today_focus += s["duration_minutes"]
            r = self.hist_table.rowCount()
            self.hist_table.insertRow(r)
            self.hist_table.setItem(r, 0, QTableWidgetItem(s["subject"]))
            self.hist_table.setItem(r, 1, QTableWidgetItem(f"{s['duration_minutes']} min"))
            self.hist_table.setItem(r, 2, QTableWidgetItem(s.get("session_type", "focus")))
            self.hist_table.setItem(r, 3, QTableWidgetItem(str(s.get("created_at", ""))[:16]))
        h = today_focus // 60
        m = today_focus % 60
        self.session_lbl.setText(f"Today: {today_focus} min focused ({h}h {m}m)")
