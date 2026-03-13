"""Goal Setting & Reminders Tool — short/long-term goals, deadlines, progress tracking."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QTextEdit, QComboBox, QDialogButtonBox,
    QCheckBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QFont, QColor
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import GoalService


class GoalDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Goal")
        self.setFixedWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Goal title…")
        form.addRow("Title:", self.title_edit)
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Description / steps…")
        self.desc_edit.setMaximumHeight(80)
        form.addRow("Description:", self.desc_edit)
        self.deadline_edit = QLineEdit(QDate.currentDate().addDays(30).toString("yyyy-MM-dd"))
        form.addRow("Deadline (YYYY-MM-DD):", self.deadline_edit)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["short", "long"])
        form.addRow("Type:", self.type_combo)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {
            "title": self.title_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
            "deadline": self.deadline_edit.text().strip(),
            "type": self.type_combo.currentText(),
        }


class StudyGoalsTool(QWidget):
    name = "Goals & Reminders"
    description = "Set study goals, track deadlines and progress"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = GoalService(user) if user else None
        self._goals = []
        self._build_ui()
        if self._svc:
            self._refresh()
        # Check overdue every minute
        self._check_timer = QTimer(self)
        self._check_timer.timeout.connect(self._check_deadlines)
        self._check_timer.start(60000)
        QTimer.singleShot(500, self._check_deadlines)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("🎯 Goals & Reminders")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        add_btn = QPushButton("➕ New Goal")
        add_btn.clicked.connect(self._add_goal)
        hl.addWidget(add_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_goal)
        hl.addWidget(del_btn)
        root.addWidget(hdr)

        # Summary banner
        self.banner = QLabel("")
        self.banner.setStyleSheet("background:#1A2A1A; color:#4CAF50; padding:10px 24px; font-size:13px;")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)

        # Filter
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(16, 8, 16, 4)
        filter_row.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Short-term", "Long-term", "Pending", "Completed"])
        self.filter_combo.currentTextChanged.connect(self._refresh)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()
        root.addLayout(filter_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Title", "Type", "Deadline", "Days Left", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 8)
        self.complete_btn = QPushButton("✅ Mark Complete")
        self.complete_btn.clicked.connect(lambda: self._toggle_complete(True))
        footer.addWidget(self.complete_btn)
        self.reopen_btn = QPushButton("🔄 Reopen")
        self.reopen_btn.setObjectName("secondary")
        self.reopen_btn.clicked.connect(lambda: self._toggle_complete(False))
        footer.addWidget(self.reopen_btn)
        footer.addStretch()
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#555; font-size:12px;")
        footer.addWidget(self.count_lbl)
        root.addLayout(footer)

    def _refresh(self):
        if not self._svc:
            return
        all_goals = self._svc.get_goals()
        f = self.filter_combo.currentText()
        if f == "Short-term":
            goals = [g for g in all_goals if g["goal_type"] == "short"]
        elif f == "Long-term":
            goals = [g for g in all_goals if g["goal_type"] == "long"]
        elif f == "Pending":
            goals = [g for g in all_goals if not g["completed"]]
        elif f == "Completed":
            goals = [g for g in all_goals if g["completed"]]
        else:
            goals = all_goals
        self._goals = goals

        today = QDate.currentDate()
        self.table.setRowCount(0)
        for g in goals:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(g["title"]))
            type_icon = "⚡" if g["goal_type"] == "short" else "🏆"
            self.table.setItem(row, 1, QTableWidgetItem(f"{type_icon} {g['goal_type']}"))
            self.table.setItem(row, 2, QTableWidgetItem(str(g["deadline"])[:10]))

            deadline = QDate.fromString(str(g["deadline"])[:10], "yyyy-MM-dd")
            days_left = today.daysTo(deadline)
            days_item = QTableWidgetItem(f"{days_left}d" if days_left >= 0 else f"Overdue {abs(days_left)}d")
            if days_left < 0 and not g["completed"]:
                days_item.setForeground(QColor("#F44336"))
            elif days_left <= 3 and not g["completed"]:
                days_item.setForeground(QColor("#FF9800"))
            self.table.setItem(row, 3, days_item)

            if g["completed"]:
                status_item = QTableWidgetItem("✅ Done")
                status_item.setForeground(QColor("#4CAF50"))
            elif days_left < 0:
                status_item = QTableWidgetItem("🔴 Overdue")
                status_item.setForeground(QColor("#F44336"))
            elif days_left <= 3:
                status_item = QTableWidgetItem("🟡 Due Soon")
                status_item.setForeground(QColor("#FF9800"))
            else:
                status_item = QTableWidgetItem("🔵 Active")
            self.table.setItem(row, 4, status_item)

        total = len(all_goals)
        done = sum(1 for g in all_goals if g["completed"])
        self.count_lbl.setText(f"{done}/{total} completed")
        self._update_banner(all_goals)

    def _update_banner(self, goals):
        today = QDate.currentDate()
        overdue = [g for g in goals if not g["completed"] and
                   QDate.fromString(str(g["deadline"])[:10], "yyyy-MM-dd") < today]
        due_soon = [g for g in goals if not g["completed"] and
                    0 <= today.daysTo(QDate.fromString(str(g["deadline"])[:10], "yyyy-MM-dd")) <= 3]
        msgs = []
        if overdue:
            msgs.append(f"🔴 {len(overdue)} overdue goal(s)!")
        if due_soon:
            msgs.append(f"🟡 {len(due_soon)} goal(s) due within 3 days.")
        done = sum(1 for g in goals if g["completed"])
        if done:
            msgs.append(f"✅ {done} goal(s) completed — great work!")
        self.banner.setText("  |  ".join(msgs) if msgs else "🎯 All goals on track!")
        color = "#2A1A1A" if overdue else ("#2A2A1A" if due_soon else "#1A2A1A")
        text_color = "#F44336" if overdue else ("#FF9800" if due_soon else "#4CAF50")
        self.banner.setStyleSheet(f"background:{color}; color:{text_color}; padding:10px 24px; font-size:13px;")

    def _add_goal(self):
        dlg = GoalDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        if not d["title"]:
            QMessageBox.warning(self, "Error", "Title is required.")
            return
        self._svc.add_goal(d["title"], d["description"], d["deadline"], d["type"])
        self._refresh()

    def _delete_goal(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._goals):
            return
        g = self._goals[row]
        if QMessageBox.question(self, "Delete", f"Delete goal '{g['title']}'?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._svc.delete_goal(g["id"])
            self._refresh()

    def _toggle_complete(self, completed: bool):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._goals):
            return
        self._svc.set_completed(self._goals[row]["id"], completed)
        self._refresh()

    def _check_deadlines(self):
        if not self._svc:
            return
        self._refresh()
