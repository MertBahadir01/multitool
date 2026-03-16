"""
Clock App — World Clocks · Stopwatch · Countdown Timer · Alarms
All plain QWidget, no DB, no encryption.
Alarms stored in-memory for the session (can be persisted via QSettings).
"""

import datetime
from zoneinfo import ZoneInfo, available_timezones

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QFrame, QListWidget, QListWidgetItem, QScrollArea,
    QDialog, QDialogButtonBox, QComboBox, QSpinBox, QLineEdit,
    QFormLayout, QGridLayout, QSizePolicy, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, QTime, QDateTime, Signal
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush
from PySide6.QtCore import QRectF, QPointF
import math

# ── popular timezone presets ──────────────────────────────────────────────────
POPULAR_ZONES = [
    ("Istanbul",        "Europe/Istanbul"),
    ("London",          "Europe/London"),
    ("New York",        "America/New_York"),
    ("Los Angeles",     "America/Los_Angeles"),
    ("Tokyo",           "Asia/Tokyo"),
    ("Dubai",           "Asia/Dubai"),
    ("Paris",           "Europe/Paris"),
    ("Sydney",          "Australia/Sydney"),
    ("Moscow",          "Europe/Moscow"),
    ("Beijing",         "Asia/Shanghai"),
]


# ── Analog Clock Face ─────────────────────────────────────────────────────────
class AnalogClock(QWidget):
    def __init__(self, tz_name="UTC", city="UTC", parent=None):
        super().__init__(parent)
        self.tz_name = tz_name
        self.city = city
        self.setFixedSize(140, 160)

    def set_zone(self, tz_name, city):
        self.tz_name = tz_name
        self.city = city
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy, r = W // 2, H // 2 - 10, min(W, H - 30) // 2 - 4

        try:
            now = datetime.datetime.now(ZoneInfo(self.tz_name))
        except Exception:
            now = datetime.datetime.utcnow()

        h, m, s = now.hour % 12, now.minute, now.second

        # face
        painter.setPen(QPen(QColor("#3E3E3E"), 2))
        painter.setBrush(QBrush(QColor("#252525")))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # hour ticks
        painter.setPen(QPen(QColor("#555555"), 1))
        for i in range(12):
            angle = math.radians(i * 30)
            x1 = cx + (r - 6) * math.sin(angle)
            y1 = cy - (r - 6) * math.cos(angle)
            x2 = cx + r * math.sin(angle)
            y2 = cy - r * math.cos(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # hour hand
        ha = math.radians((h * 30) + (m * 0.5))
        painter.setPen(QPen(QColor("#E0E0E0"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(cx, cy),
                         QPointF(cx + (r * 0.5) * math.sin(ha), cy - (r * 0.5) * math.cos(ha)))

        # minute hand
        ma = math.radians(m * 6)
        painter.setPen(QPen(QColor("#CCCCCC"), 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(cx, cy),
                         QPointF(cx + (r * 0.72) * math.sin(ma), cy - (r * 0.72) * math.cos(ma)))

        # second hand
        sa = math.radians(s * 6)
        painter.setPen(QPen(QColor("#00BFA5"), 1, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(cx, cy),
                         QPointF(cx + (r * 0.85) * math.sin(sa), cy - (r * 0.85) * math.cos(sa)))

        # center dot
        painter.setBrush(QBrush(QColor("#00BFA5")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 3, 3)

        # city label
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(0, cy + r + 4, W, 20), Qt.AlignCenter, self.city)

        time_str = now.strftime("%H:%M")
        painter.setPen(QColor("#AAAAAA"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(0, cy + r + 18, W, 16), Qt.AlignCenter, time_str)

        painter.end()


# ── World Clocks Page ─────────────────────────────────────────────────────────
class WorldClocksPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._clocks = []  # list of (AnalogClock, tz_name, city)
        self._active_zones = list(POPULAR_ZONES[:6])
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("🌍 World Clocks"))
        hdr.addStretch()
        add_btn = QPushButton("➕ Add Clock")
        add_btn.clicked.connect(self._add_clock_dialog)
        hdr.addWidget(add_btn)
        root.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(16)
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self._grid_widget)
        root.addWidget(scroll, 1)
        self._rebuild_grid()

    def _rebuild_grid(self):
        # clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._clocks = []
        for i, (city, tz) in enumerate(self._active_zones):
            clock = AnalogClock(tz, city)
            self._clocks.append(clock)
            self._grid.addWidget(clock, i // 4, i % 4)

    def _tick(self):
        for clock in self._clocks:
            clock.update()

    def _add_clock_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add World Clock")
        dlg.setFixedWidth(360)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        city_edit = QLineEdit()
        city_edit.setPlaceholderText("e.g. Berlin")
        form.addRow("City name:", city_edit)
        tz_combo = QComboBox()
        tz_combo.setEditable(True)
        # popular first
        for c, tz in POPULAR_ZONES:
            tz_combo.addItem(f"{c} — {tz}", tz)
        tz_combo.addItem("─────────────────", "")
        for tz in sorted(available_timezones()):
            tz_combo.addItem(tz, tz)
        form.addRow("Timezone:", tz_combo)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        city = city_edit.text().strip() or tz_combo.currentText().split("—")[0].strip()
        tz = tz_combo.currentData() or tz_combo.currentText().strip()
        if city and tz:
            self._active_zones.append((city, tz))
            self._rebuild_grid()


# ── Stopwatch Page ─────────────────────────────────────────────────────────────
class StopwatchPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._elapsed = 0      # milliseconds
        self._running = False
        self._laps = []
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._tick)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 20)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignTop)

        self._display = QLabel("00:00.00")
        self._display.setFont(QFont("Courier New", 52, QFont.Bold))
        self._display.setAlignment(Qt.AlignCenter)
        self._display.setStyleSheet("color:#00BFA5; letter-spacing:4px;")
        root.addWidget(self._display)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(16)

        self._start_btn = QPushButton("▶  Start")
        self._start_btn.setFixedSize(120, 44)
        self._start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self._start_btn)

        self._lap_btn = QPushButton("🏁  Lap")
        self._lap_btn.setFixedSize(100, 44)
        self._lap_btn.clicked.connect(self._lap)
        self._lap_btn.setObjectName("secondary")
        btn_row.addWidget(self._lap_btn)

        self._reset_btn = QPushButton("⏹  Reset")
        self._reset_btn.setFixedSize(100, 44)
        self._reset_btn.setObjectName("secondary")
        self._reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self._reset_btn)
        root.addLayout(btn_row)

        self._lap_list = QListWidget()
        self._lap_list.setStyleSheet("background:#252525; border-radius:8px; font-size:13px;")
        root.addWidget(self._lap_list, 1)

    def _fmt(self, ms):
        mins = ms // 60000
        secs = (ms % 60000) // 1000
        cs   = (ms % 1000) // 10
        return f"{mins:02d}:{secs:02d}.{cs:02d}"

    def _tick(self):
        self._elapsed += 10
        self._display.setText(self._fmt(self._elapsed))

    def _toggle(self):
        if self._running:
            self._timer.stop()
            self._running = False
            self._start_btn.setText("▶  Resume")
        else:
            self._timer.start()
            self._running = True
            self._start_btn.setText("⏸  Pause")

    def _lap(self):
        if self._elapsed == 0:
            return
        n = len(self._laps) + 1
        t = self._fmt(self._elapsed)
        self._laps.append(t)
        item = QListWidgetItem(f"  Lap {n:02d}   {t}")
        self._lap_list.insertItem(0, item)

    def _reset(self):
        self._timer.stop()
        self._running = False
        self._elapsed = 0
        self._laps.clear()
        self._lap_list.clear()
        self._display.setText("00:00.00")
        self._start_btn.setText("▶  Start")


# ── Countdown Page ────────────────────────────────────────────────────────────
class CountdownPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._remaining = 0
        self._running = False
        
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        
        self._build_ui()

    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(20)
        self.layout.setAlignment(Qt.AlignCenter)

        # --- 1. INPUT AREA (Spinboxes) ---
        self.input_container = QWidget()
        self.input_layout = QHBoxLayout(self.input_container)
        self.spins = {}
        
        for label_text, key, max_val in [("Hours", "h", 99), ("Minutes", "m", 59), ("Seconds", "s", 59)]:
            col = QVBoxLayout()
            spin = QSpinBox()
            spin.setRange(0, max_val)
            spin.setFixedSize(90, 70) # Increased width to prevent blocking
            spin.setAlignment(Qt.AlignCenter)
            spin.setStyleSheet("""
                QSpinBox {
                    font-size: 28px; font-weight: bold; background: #252525;
                    color: #00BFA5; border: 2px solid #333; border-radius: 10px;
                }
                QSpinBox::up-button, QSpinBox::down-button { width: 0px; } 
            """)
            self.spins[key] = spin
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
            lbl.setAlignment(Qt.AlignCenter)
            
            col.addWidget(spin)
            col.addWidget(lbl)
            self.input_layout.addLayout(col)
            if label_text != "Seconds":
                self.input_layout.addWidget(QLabel(":", styleSheet="font-size:30px; color:#444;"))

        self.layout.addWidget(self.input_container, alignment=Qt.AlignCenter)

        # --- 2. THE BIG COUNTDOWN (Hidden by default) ---
        self._display = QLabel("00:00:00")
        # Explicitly setting a massive font size for the countdown
        self._display.setStyleSheet("""
            QLabel {
                font-family: 'Courier New', monospace;
                font-size: 80px; 
                font-weight: 900;
                color: #00BFA5;
                letter-spacing: 10px;
                margin: 20px 0px;
            }
        """)
        self._display.hide()
        self.layout.addWidget(self._display, alignment=Qt.AlignCenter)

        # --- 3. LABEL & CONTROLS ---
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("Label (e.g. Focus Session)")
        self._label_edit.setFixedWidth(280)
        self._label_edit.setStyleSheet("background:#1A1A1A; color:#EEE; padding:8px; border-radius:5px; border:1px solid #333;")
        self.layout.addWidget(self._label_edit, alignment=Qt.AlignCenter)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("START")
        self._start_btn.setFixedSize(150, 50)
        self._start_btn.setStyleSheet("background:#00BFA5; color:#121212; font-weight:bold; border-radius:25px; font-size:16px;")
        self._start_btn.clicked.connect(self._toggle)

        self._reset_btn = QPushButton("RESET")
        self._reset_btn.setFixedSize(100, 50)
        self._reset_btn.setStyleSheet("background:#333; color:white; border-radius:25px;")
        self._reset_btn.clicked.connect(self._reset)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._reset_btn)
        self.layout.addLayout(btn_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #555; font-size: 14px;")
        self.layout.addWidget(self._status_lbl, alignment=Qt.AlignCenter)

    def _toggle(self):
        if self._running:
            self._timer.stop()
            self._running = False
            self._start_btn.setText("RESUME")
        else:
            if self._remaining <= 0:
                self._remaining = (self.spins['h'].value() * 3600 + 
                                  self.spins['m'].value() * 60 + 
                                  self.spins['s'].value())
            
            if self._remaining > 0:
                # SWAP UI MODES
                self.input_container.hide() # Hide small spinboxes
                self._display.show()        # Show BIG text
                self._timer.start()
                self._running = True
                self._start_btn.setText("PAUSE")
                self._status_lbl.setText(f"Running: {self._label_edit.text() or 'Timer'}")
                self._update_display()

    def _update_display(self):
        h, rem = divmod(self._remaining, 3600)
        m, s = divmod(rem, 60)
        self._display.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            self._update_display()
        else:
            self._timer.stop()
            self._running = False
            self._display.setStyleSheet("font-size: 80px; color: #FF5252; font-weight: bold;")
            QMessageBox.information(self, "Done", "Time is up!")

    def _reset(self):
        self._timer.stop()
        self._running = False
        self._remaining = 0
        self._display.hide()
        self.input_container.show()
        self._start_btn.setText("START")
        self._status_lbl.setText("")

# ── Alarms Page ────────────────────────────────────────────────────────────────
class AlarmsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._alarms = []   # list of {"hour":int, "minute":int, "label":str, "enabled":bool, "fired":bool}
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_alarms)
        self._timer.start(10000)  # check every 10s

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("⏰ Alarms"))
        hdr.addStretch()
        add_btn = QPushButton("➕ Add Alarm")
        add_btn.clicked.connect(self._add_alarm)
        hdr.addWidget(add_btn)
        root.addLayout(hdr)

        self._alarm_list = QListWidget()
        self._alarm_list.setStyleSheet("background:#252525; border-radius:8px; font-size:14px;")
        root.addWidget(self._alarm_list, 1)

        del_btn = QPushButton("🗑️ Delete Selected Alarm")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_alarm)
        root.addWidget(del_btn)

    def _refresh(self):
        self._alarm_list.clear()
        for a in self._alarms:
            icon = "🔔" if a["enabled"] else "🔕"
            status = "On" if a["enabled"] else "Off"
            text = f"  {icon}  {a['hour']:02d}:{a['minute']:02d}  —  {a['label'] or 'Alarm'}   [{status}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, a)
            self._alarm_list.addItem(item)

    def _add_alarm(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Alarm")
        dlg.setFixedWidth(320)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        h_spin = QSpinBox(); h_spin.setRange(0, 23); h_spin.setValue(8)
        m_spin = QSpinBox(); m_spin.setRange(0, 59); m_spin.setValue(0)
        label_edit = QLineEdit(); label_edit.setPlaceholderText("Alarm label…")
        form.addRow("Hour:", h_spin)
        form.addRow("Minute:", m_spin)
        form.addRow("Label:", label_edit)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        self._alarms.append({
            "hour": h_spin.value(), "minute": m_spin.value(),
            "label": label_edit.text().strip(), "enabled": True, "fired": False
        })
        self._refresh()

    def _delete_alarm(self):
        row = self._alarm_list.currentRow()
        if row >= 0:
            self._alarms.pop(row)
            self._refresh()

    def _check_alarms(self):
        now = datetime.datetime.now()
        for a in self._alarms:
            if a["enabled"] and not a["fired"] and a["hour"] == now.hour and a["minute"] == now.minute:
                a["fired"] = True
                QMessageBox.information(self, "⏰ Alarm!", f"Alarm: {a['label'] or a['hour']:02d}:{a['minute']:02d}")
        # reset fired after minute passes
        for a in self._alarms:
            if a["fired"] and not (a["hour"] == now.hour and a["minute"] == now.minute):
                a["fired"] = False


# ── Main Clock Tool ───────────────────────────────────────────────────────────
class ClockTool(QWidget):
    name = "Clock"
    description = "World clocks, stopwatch, countdown timer and alarms"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("🕐 Clock")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        self._time_lbl = QLabel("")
        self._time_lbl.setFont(QFont("Courier New", 16, QFont.Bold))
        self._time_lbl.setStyleSheet("color:#00BFA5;")
        hl.addWidget(self._time_lbl)
        root.addWidget(hdr)

        tabs = QTabWidget()
        tabs.addTab(WorldClocksPage(), "🌍 World Clocks")
        tabs.addTab(StopwatchPage(),   "⏱️ Stopwatch")
        tabs.addTab(CountdownPage(),   "⏳ Countdown")
        tabs.addTab(AlarmsPage(),      "⏰ Alarms")
        root.addWidget(tabs, 1)

        self._hdr_timer = QTimer(self)
        self._hdr_timer.timeout.connect(self._update_time)
        self._hdr_timer.start(1000)
        self._update_time()

    def _update_time(self):
        self._time_lbl.setText(datetime.datetime.now().strftime("%H:%M:%S  —  %a %d %b %Y"))
