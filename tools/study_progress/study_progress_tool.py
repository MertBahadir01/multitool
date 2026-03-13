"""Progress Tracking Tool — charts for exam scores and normal test performance."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPolygonF
from PySide6.QtCore import QPointF, QRectF
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import ExamService, TimerService

SUBJECT_COLORS = [
    "#00BFA5", "#FF9800", "#9C27B0", "#F44336",
    "#2196F3", "#4CAF50", "#FF5722", "#607D8B",
]


class LineChartWidget(QWidget):
    """Simple line chart drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self._series: dict[str, list] = {}   # label → [values]
        self._x_labels: list[str] = []
        self._title = ""

    def set_data(self, series: dict, x_labels: list, title: str = ""):
        self._series = series
        self._x_labels = x_labels
        self._title = title
        self.update()

    def paintEvent(self, event):
        if not self._series or not self._x_labels:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        W, H = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
        cw = W - pad_l - pad_r
        ch = H - pad_t - pad_b

        # background
        painter.fillRect(0, 0, W, H, QColor("#1A1A1A"))

        # title
        if self._title:
            painter.setPen(QColor("#E0E0E0"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(pad_l, 24, self._title)

        # find y range
        all_vals = [v for vals in self._series.values() for v in vals]
        y_max = max(all_vals) if all_vals else 1
        y_max = max(y_max, 1)

        # grid lines
        painter.setPen(QPen(QColor("#333333"), 1))
        for i in range(5):
            y = pad_t + ch - (i / 4) * ch
            painter.drawLine(pad_l, int(y), pad_l + cw, int(y))
            painter.setPen(QColor("#666666"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(4, int(y) + 4, str(int(y_max * i / 4)))
            painter.setPen(QPen(QColor("#333333"), 1))

        # x labels
        n = len(self._x_labels)
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("Segoe UI", 8))
        for i, lbl in enumerate(self._x_labels):
            x = pad_l + (i / max(n - 1, 1)) * cw
            painter.drawText(int(x) - 20, H - 8, lbl[:10])

        # series
        for ci, (label, values) in enumerate(self._series.items()):
            if not values:
                continue
            color = QColor(SUBJECT_COLORS[ci % len(SUBJECT_COLORS)])
            pen = QPen(color, 2)
            painter.setPen(pen)
            pts = []
            for i, v in enumerate(values):
                x = pad_l + (i / max(n - 1, 1)) * cw
                y = pad_t + ch - (v / y_max) * ch
                pts.append(QPointF(x, y))
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            for p in pts:
                painter.drawEllipse(p, 4, 4)

        # legend
        lx = pad_l
        for ci, label in enumerate(self._series.keys()):
            color = QColor(SUBJECT_COLORS[ci % len(SUBJECT_COLORS)])
            painter.fillRect(lx, H - 30, 12, 12, color)
            painter.setPen(QColor("#CCCCCC"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(lx + 16, H - 20, label)
            lx += len(label) * 7 + 30

        painter.end()


class BarChartWidget(QWidget):
    """Simple bar chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._data: dict[str, float] = {}
        self._title = ""

    def set_data(self, data: dict, title: str = ""):
        self._data = data
        self._title = title
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
        painter.fillRect(0, 0, W, H, QColor("#1A1A1A"))
        if self._title:
            painter.setPen(QColor("#E0E0E0"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(pad_l, 24, self._title)
        items = list(self._data.items())
        max_v = max(v for _, v in items) if items else 1
        max_v = max(max_v, 1)
        cw = W - pad_l - pad_r
        ch = H - pad_t - pad_b
        bar_w = max(8, cw // max(len(items), 1) - 8)
        for i, (label, value) in enumerate(items):
            x = pad_l + i * (cw // max(len(items), 1)) + 4
            bar_h = int((value / max_v) * ch)
            y = pad_t + ch - bar_h
            color = QColor(SUBJECT_COLORS[i % len(SUBJECT_COLORS)])
            painter.fillRect(x, y, bar_w, bar_h, color)
            painter.setPen(QColor("#888888"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(x, H - 8, label[:8])
            painter.setPen(QColor("#E0E0E0"))
            painter.drawText(x, y - 4, str(int(value)))
        painter.end()


class StudyProgressTool(QWidget):
    name = "Progress Tracker"
    description = "Charts and analytics for exam scores and study time"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._exam_svc = ExamService(user) if user else None
        self._timer_svc = TimerService(user) if user else None
        self._build_ui()
        if self._exam_svc:
            self._refresh_all()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📈 Progress Tracker")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_all)
        hl.addWidget(refresh_btn)
        root.addWidget(hdr)

        tabs = QTabWidget()

        # TYT/AYT progress
        exam_tab = QWidget()
        el = QVBoxLayout(exam_tab)
        el.setContentsMargins(16, 16, 16, 16)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Exam Type:"))
        self.exam_filter = QComboBox()
        self.exam_filter.addItems(["TYT", "AYT", "All"])
        self.exam_filter.currentTextChanged.connect(self._refresh_exam_chart)
        filter_row.addWidget(self.exam_filter)
        filter_row.addWidget(QLabel("Subject:"))
        self.subject_filter = QComboBox()
        self.subject_filter.addItem("All Subjects")
        self.subject_filter.currentTextChanged.connect(self._refresh_exam_chart)
        filter_row.addWidget(self.subject_filter)
        filter_row.addStretch()
        el.addLayout(filter_row)
        self.exam_chart = LineChartWidget()
        el.addWidget(self.exam_chart, 1)
        self.exam_summary = QLabel("")
        self.exam_summary.setStyleSheet("color:#888; font-size:12px;")
        el.addWidget(self.exam_summary)
        tabs.addTab(exam_tab, "📊 TYT/AYT Progress")

        # Study time tab
        time_tab = QWidget()
        tl = QVBoxLayout(time_tab)
        tl.setContentsMargins(16, 16, 16, 16)
        self.time_chart = BarChartWidget()
        tl.addWidget(self.time_chart)
        tl.addWidget(QLabel("Study time per subject (minutes):"))
        self.time_table = QTableWidget(0, 2)
        self.time_table.setHorizontalHeaderLabels(["Subject", "Total Minutes"])
        self.time_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.time_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tl.addWidget(self.time_table, 1)
        tabs.addTab(time_tab, "⏱️ Study Time")

        # Strengths & Weaknesses
        sw_tab = QWidget()
        sl = QVBoxLayout(sw_tab)
        sl.setContentsMargins(16, 16, 16, 16)
        sl.setSpacing(12)
        sl.addWidget(QLabel("🟢 Strongest Subjects:"))
        self.strong_table = QTableWidget(0, 3)
        self.strong_table.setHorizontalHeaderLabels(["Subject", "Avg Correct", "Sessions"])
        self.strong_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.strong_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.strong_table.setMaximumHeight(200)
        sl.addWidget(self.strong_table)
        sl.addWidget(QLabel("🔴 Weakest Subjects (need more work):"))
        self.weak_table = QTableWidget(0, 3)
        self.weak_table.setHorizontalHeaderLabels(["Subject", "Avg Incorrect", "Sessions"])
        self.weak_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.weak_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.weak_table.setMaximumHeight(200)
        sl.addWidget(self.weak_table)
        sl.addStretch()
        tabs.addTab(sw_tab, "🎯 Strengths & Weaknesses")

        root.addWidget(tabs, 1)

    def _refresh_all(self):
        self._refresh_exam_chart()
        self._refresh_time_chart()
        self._refresh_sw()

    def _refresh_exam_chart(self):
        if not self._exam_svc:
            return
        exam_type = self.exam_filter.currentText()
        et = None if exam_type == "All" else exam_type
        sessions = self._exam_svc.get_sessions(et)
        if not sessions:
            self.exam_chart.set_data({}, [], "No data")
            return
        # collect all subjects
        all_subjects = set()
        for sess in sessions:
            for sc in self._exam_svc.get_scores(sess["id"]):
                all_subjects.add(sc["subject"])
        # update subject filter
        self.subject_filter.blockSignals(True)
        current_subj = self.subject_filter.currentText()
        self.subject_filter.clear()
        self.subject_filter.addItem("All Subjects")
        for s in sorted(all_subjects):
            self.subject_filter.addItem(s)
        idx = self.subject_filter.findText(current_subj)
        if idx >= 0:
            self.subject_filter.setCurrentIndex(idx)
        self.subject_filter.blockSignals(False)

        filter_subj = self.subject_filter.currentText()
        x_labels = [str(s["session_date"])[:10] for s in sessions]

        if filter_subj == "All Subjects":
            # one series per subject
            series = {}
            for subj in sorted(all_subjects):
                vals = []
                for sess in sessions:
                    scores = {sc["subject"]: sc for sc in self._exam_svc.get_scores(sess["id"])}
                    vals.append(scores.get(subj, {}).get("correct", 0))
                series[subj] = vals
        else:
            vals = []
            for sess in sessions:
                scores = {sc["subject"]: sc for sc in self._exam_svc.get_scores(sess["id"])}
                vals.append(scores.get(filter_subj, {}).get("correct", 0))
            series = {filter_subj: vals}

        self.exam_chart.set_data(series, x_labels, f"{exam_type} — Correct Answers Over Time")
        total_sessions = len(sessions)
        self.exam_summary.setText(f"Total sessions: {total_sessions}  |  Subjects tracked: {len(all_subjects)}")

    def _refresh_time_chart(self):
        if not self._timer_svc:
            return
        totals = self._timer_svc.get_totals_by_subject()
        data = {r["subject"]: r["total_minutes"] for r in totals}
        self.time_chart.set_data(data, "Study Time by Subject (minutes)")
        self.time_table.setRowCount(0)
        for r in totals:
            row = self.time_table.rowCount()
            self.time_table.insertRow(row)
            self.time_table.setItem(row, 0, QTableWidgetItem(r["subject"]))
            h = r["total_minutes"] // 60
            m = r["total_minutes"] % 60
            self.time_table.setItem(row, 1, QTableWidgetItem(f"{r['total_minutes']} min ({h}h {m}m)"))

    def _refresh_sw(self):
        if not self._exam_svc:
            return
        sessions = self._exam_svc.get_sessions()
        subject_data = {}
        for sess in sessions:
            for sc in self._exam_svc.get_scores(sess["id"]):
                subj = sc["subject"]
                if subj not in subject_data:
                    subject_data[subj] = []
                subject_data[subj].append(sc)
        if not subject_data:
            return
        summaries = []
        for subj, scores in subject_data.items():
            avg_c = sum(s["correct"] for s in scores) / len(scores)
            avg_i = sum(s["incorrect"] for s in scores) / len(scores)
            summaries.append({"subject": subj, "avg_c": avg_c, "avg_i": avg_i, "n": len(scores)})
        # strong = highest avg correct
        by_correct = sorted(summaries, key=lambda x: -x["avg_c"])
        self.strong_table.setRowCount(0)
        for s in by_correct[:5]:
            r = self.strong_table.rowCount()
            self.strong_table.insertRow(r)
            self.strong_table.setItem(r, 0, QTableWidgetItem(s["subject"]))
            self.strong_table.setItem(r, 1, QTableWidgetItem(f"{s['avg_c']:.1f}"))
            self.strong_table.setItem(r, 2, QTableWidgetItem(str(s["n"])))
        # weak = highest avg incorrect relative to correct
        by_weak = sorted(summaries, key=lambda x: -(x["avg_i"] / max(x["avg_c"], 0.1)))
        self.weak_table.setRowCount(0)
        for s in by_weak[:5]:
            r = self.weak_table.rowCount()
            self.weak_table.insertRow(r)
            self.weak_table.setItem(r, 0, QTableWidgetItem(s["subject"]))
            self.weak_table.setItem(r, 1, QTableWidgetItem(f"{s['avg_i']:.1f}"))
            self.weak_table.setItem(r, 2, QTableWidgetItem(str(s["n"])))
