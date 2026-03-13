"""Exam Logging Tool — TYT/AYT session logging, per-subject scores, improvement tracking."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QDialogButtonBox,
    QTextEdit, QMessageBox, QFrame, QTabWidget, QListWidget, QListWidgetItem,
    QScrollArea
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import ExamService

EXAM_TYPES = ["TYT", "AYT", "YDT", "Practice", "Other"]

TYT_SUBJECTS = ["Turkish", "Math", "Science", "Social Studies"]
AYT_SUBJECTS = ["Math", "Physics", "Chemistry", "Biology",
                 "Literature", "History", "Geography", "Philosophy"]


class SessionDialog(QDialog):
    def __init__(self, parent=None, exam_types=None):
        super().__init__(parent)
        self.setWindowTitle("New Exam Session")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        form = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(exam_types or EXAM_TYPES)
        form.addRow("Exam Type:", self.type_combo)
        self.date_edit = QLineEdit(QDate.currentDate().toString("yyyy-MM-dd"))
        form.addRow("Date (YYYY-MM-DD):", self.date_edit)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Session notes…")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {
            "type": self.type_combo.currentText(),
            "date": self.date_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class ScoreDialog(QDialog):
    def __init__(self, parent=None, exam_type="TYT"):
        super().__init__(parent)
        self.setWindowTitle(f"Add Subject Scores — {exam_type}")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        subjects = TYT_SUBJECTS if exam_type == "TYT" else AYT_SUBJECTS
        form = QFormLayout()
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(subjects)
        self.subject_combo.setEditable(True)
        form.addRow("Subject:", self.subject_combo)
        self.correct_spin = QSpinBox(); self.correct_spin.setRange(0, 200)
        form.addRow("Correct:", self.correct_spin)
        self.incorrect_spin = QSpinBox(); self.incorrect_spin.setRange(0, 200)
        form.addRow("Incorrect:", self.incorrect_spin)
        self.empty_spin = QSpinBox(); self.empty_spin.setRange(0, 200)
        form.addRow("Empty:", self.empty_spin)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {
            "subject": self.subject_combo.currentText().strip(),
            "correct": self.correct_spin.value(),
            "incorrect": self.incorrect_spin.value(),
            "empty": self.empty_spin.value(),
        }


class StudyExamsTool(QWidget):
    name = "Exam Logging"
    description = "Log TYT/AYT exam sessions and track subject performance"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = ExamService(user) if user else None
        self._current_session = None
        self._build_ui()
        if self._svc:
            self._refresh_sessions()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📊 Exam Logging")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        new_btn = QPushButton("➕ New Session")
        new_btn.clicked.connect(self._add_session)
        hl.addWidget(new_btn)
        del_btn = QPushButton("🗑️ Delete Session")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_session)
        hl.addWidget(del_btn)
        root.addWidget(hdr)

        tabs = QTabWidget()

        # Sessions tab
        sess_tab = QWidget()
        sl = QVBoxLayout(sess_tab)
        sl.setContentsMargins(16, 16, 16, 16)
        sl.setSpacing(10)

        self.sessions_table = QTableWidget(0, 3)
        self.sessions_table.setHorizontalHeaderLabels(["Date", "Exam Type", "Notes"])
        self.sessions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.itemSelectionChanged.connect(self._on_session_select)
        sl.addWidget(self.sessions_table)

        sl.addWidget(QLabel("Scores for selected session:"))
        self.scores_table = QTableWidget(0, 4)
        self.scores_table.setHorizontalHeaderLabels(["Subject", "✅ Correct", "❌ Incorrect", "⬜ Empty"])
        self.scores_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.scores_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sl.addWidget(self.scores_table)

        score_btns = QHBoxLayout()
        add_score_btn = QPushButton("➕ Add Score")
        add_score_btn.clicked.connect(self._add_score)
        score_btns.addWidget(add_score_btn)
        score_btns.addStretch()
        sl.addLayout(score_btns)
        tabs.addTab(sess_tab, "📋 Sessions")

        # Weak areas tab
        weak_tab = QWidget()
        wl = QVBoxLayout(weak_tab)
        wl.setContentsMargins(16, 16, 16, 16)
        wl.setSpacing(10)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Exam Type:"))
        self.weak_filter = QComboBox()
        self.weak_filter.addItems(["All"] + EXAM_TYPES)
        self.weak_filter.currentTextChanged.connect(self._refresh_weak_areas)
        filter_row.addWidget(self.weak_filter)
        filter_row.addStretch()
        wl.addLayout(filter_row)
        self.weak_table = QTableWidget(0, 5)
        self.weak_table.setHorizontalHeaderLabels(["Subject", "Avg Correct", "Avg Incorrect", "Sessions", "Trend"])
        self.weak_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.weak_table.setEditTriggers(QTableWidget.NoEditTriggers)
        wl.addWidget(self.weak_table, 1)
        tabs.addTab(weak_tab, "🎯 Weak Areas")

        root.addWidget(tabs, 1)

    def _refresh_sessions(self):
        sessions = self._svc.get_sessions()
        self._sessions = sessions
        self.sessions_table.setRowCount(0)
        for s in sessions:
            r = self.sessions_table.rowCount()
            self.sessions_table.insertRow(r)
            self.sessions_table.setItem(r, 0, QTableWidgetItem(str(s["session_date"])[:10]))
            self.sessions_table.setItem(r, 1, QTableWidgetItem(s["exam_type"]))
            self.sessions_table.setItem(r, 2, QTableWidgetItem(s.get("notes", "") or ""))
        self._refresh_weak_areas()

    def _on_session_select(self):
        row = self.sessions_table.currentRow()
        if row < 0 or row >= len(self._sessions):
            return
        self._current_session = self._sessions[row]
        self._refresh_scores()

    def _refresh_scores(self):
        if not self._current_session:
            return
        scores = self._svc.get_scores(self._current_session["id"])
        self.scores_table.setRowCount(0)
        for s in scores:
            r = self.scores_table.rowCount()
            self.scores_table.insertRow(r)
            self.scores_table.setItem(r, 0, QTableWidgetItem(s["subject"]))
            self.scores_table.setItem(r, 1, QTableWidgetItem(str(s["correct"])))
            inc_item = QTableWidgetItem(str(s["incorrect"]))
            if s["incorrect"] > s["correct"]:
                inc_item.setForeground(QColor("#F44336"))
            self.scores_table.setItem(r, 2, inc_item)
            self.scores_table.setItem(r, 3, QTableWidgetItem(str(s["empty"])))

    def _add_session(self):
        dlg = SessionDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        self._svc.add_session(d["type"], d["date"], d["notes"])
        self._refresh_sessions()

    def _delete_session(self):
        if not self._current_session:
            return
        if QMessageBox.question(self, "Delete", "Delete this session and all its scores?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_session(self._current_session["id"])
        self._current_session = None
        self.scores_table.setRowCount(0)
        self._refresh_sessions()

    def _add_score(self):
        if not self._current_session:
            QMessageBox.information(self, "No Session", "Select a session first.")
            return
        dlg = ScoreDialog(self, self._current_session["exam_type"])
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        self._svc.add_score(self._current_session["id"], d["subject"], d["correct"], d["incorrect"], d["empty"])
        self._refresh_scores()
        self._refresh_weak_areas()

    def _refresh_weak_areas(self):
        if not self._svc:
            return
        filter_type = self.weak_filter.currentText()
        exam_type = None if filter_type == "All" else filter_type
        # collect all subjects
        all_sessions = self._svc.get_sessions(exam_type)
        subject_data = {}
        for sess in all_sessions:
            for sc in self._svc.get_scores(sess["id"]):
                subj = sc["subject"]
                if subj not in subject_data:
                    subject_data[subj] = []
                subject_data[subj].append(sc)
        self.weak_table.setRowCount(0)
        for subj, scores in sorted(subject_data.items()):
            avg_c = sum(s["correct"] for s in scores) / len(scores)
            avg_i = sum(s["incorrect"] for s in scores) / len(scores)
            trend = "📈" if len(scores) >= 2 and scores[-1]["correct"] > scores[0]["correct"] else (
                    "📉" if len(scores) >= 2 and scores[-1]["correct"] < scores[0]["correct"] else "➡️")
            r = self.weak_table.rowCount()
            self.weak_table.insertRow(r)
            self.weak_table.setItem(r, 0, QTableWidgetItem(subj))
            self.weak_table.setItem(r, 1, QTableWidgetItem(f"{avg_c:.1f}"))
            inc_item = QTableWidgetItem(f"{avg_i:.1f}")
            if avg_i > avg_c:
                inc_item.setForeground(QColor("#F44336"))
            self.weak_table.setItem(r, 2, inc_item)
            self.weak_table.setItem(r, 3, QTableWidgetItem(str(len(scores))))
            self.weak_table.setItem(r, 4, QTableWidgetItem(trend))
