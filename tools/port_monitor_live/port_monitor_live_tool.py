"""Port Monitor Live — shows active network connections, refreshed every few seconds."""
import psutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QSpinBox, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor


_STATUS_COLORS = {
    "ESTABLISHED": "#00BFA5",
    "LISTEN":      "#8BC34A",
    "TIME_WAIT":   "#FFC107",
    "CLOSE_WAIT":  "#FF9800",
    "SYN_SENT":    "#03A9F4",
    "FIN_WAIT1":   "#9C27B0",
    "FIN_WAIT2":   "#9C27B0",
}


class PortMonitorLiveTool(QWidget):
    name        = "Port Monitor Live"
    description = "Live view of active network ports and connections"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._paused = False
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("Start Live")
        self.start_btn.clicked.connect(self._toggle)
        ctrl.addWidget(self.start_btn)

        ctrl.addWidget(QLabel("Refresh (s):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.valueChanged.connect(lambda v: self._timer.setInterval(v * 1000))
        ctrl.addWidget(self.interval_spin)

        ctrl.addWidget(QLabel("Filter:"))
        self.filter_in = QLineEdit()
        self.filter_in.setPlaceholderText("port / pid / status...")
        self.filter_in.setFixedWidth(180)
        self.filter_in.textChanged.connect(self._refresh)
        ctrl.addWidget(self.filter_in)

        ctrl.addStretch()
        self.count_lbl = QLabel("0 connections")
        self.count_lbl.setStyleSheet("color: #888888;")
        ctrl.addWidget(self.count_lbl)
        lay.addLayout(ctrl)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Local Addr", "Local Port", "Remote Addr", "Remote Port", "Status", "PID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.table)

        note = QLabel("Requires: pip install psutil")
        note.setStyleSheet("color: #555555; font-size: 11px;")
        lay.addWidget(note)

    def _toggle(self):
        if self._timer.isActive():
            self._timer.stop()
            self.start_btn.setText("Start Live")
        else:
            self._timer.start(self.interval_spin.value() * 1000)
            self.start_btn.setText("Stop Live")
            self._refresh()

    def _refresh(self):
        query = self.filter_in.text().lower()
        try:
            conns = psutil.net_connections(kind="inet")
        except Exception as e:
            self.count_lbl.setText(f"Error: {e}")
            return

        rows = []
        for c in conns:
            la = c.laddr.ip if c.laddr else ""
            lp = str(c.laddr.port) if c.laddr else ""
            ra = c.raddr.ip if c.raddr else ""
            rp = str(c.raddr.port) if c.raddr else ""
            st = c.status or ""
            pid = str(c.pid) if c.pid else ""
            if query and not any(query in x.lower() for x in [la, lp, ra, rp, st, pid]):
                continue
            rows.append((la, lp, ra, rp, st, pid))

        self.table.setRowCount(len(rows))
        for r, (la, lp, ra, rp, st, pid) in enumerate(rows):
            for c, val in enumerate([la, lp, ra, rp, st, pid]):
                item = QTableWidgetItem(val)
                if c == 4:
                    color = _STATUS_COLORS.get(st, "#888888")
                    item.setForeground(QColor(color))
                self.table.setItem(r, c, item)
        self.count_lbl.setText(f"{len(rows)} connections")

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
