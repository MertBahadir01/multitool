"""Habit Tracker — daily habit tracking with streaks."""
import os, json
from datetime import date, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

DATA_FILE = os.path.join(os.path.expanduser("~"), ".multitool_habits.json")


def _load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"habits": [], "log": {}}


def _save(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _streak(habit, log):
    today = date.today()
    streak = 0
    d = today
    while True:
        ds = d.isoformat()
        if log.get(ds, {}).get(habit):
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak


class HabitTrackerTool(QWidget):
    name        = "Habit Tracker"
    description = "Track daily habits and streaks"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = _load()
        self._today = date.today().isoformat()
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        date_lbl = QLabel(f"Today: {self._today}")
        date_lbl.setStyleSheet("color: #00BFA5; font-weight: bold;")
        lay.addWidget(date_lbl)

        # Add habit
        add_box = QGroupBox("Add Habit")
        al = QHBoxLayout(add_box)
        self.habit_in = QLineEdit()
        self.habit_in.setPlaceholderText("e.g. Exercise, Read, Meditate...")
        self.habit_in.returnPressed.connect(self._add_habit)
        al.addWidget(self.habit_in)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_habit)
        al.addWidget(add_btn)
        lay.addWidget(add_box)

        # Today's habits
        today_box = QGroupBox("Today's Habits")
        tl = QVBoxLayout(today_box)
        self.today_list = QListWidget()
        self.today_list.itemDoubleClicked.connect(self._toggle)
        tl.addWidget(self.today_list)
        hint = QLabel("Double-click to mark complete / incomplete")
        hint.setStyleSheet("color: #555555; font-size: 11px;")
        tl.addWidget(hint)
        del_btn = QPushButton("Delete Selected Habit")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete)
        tl.addWidget(del_btn)
        lay.addWidget(today_box)

        # Streaks
        streak_box = QGroupBox("Streaks (last 14 days)")
        sl = QVBoxLayout(streak_box)
        self.streak_table = QTableWidget(0, 3)
        self.streak_table.setHorizontalHeaderLabels(["Habit", "Current Streak", "Last 14 Days"])
        self.streak_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.streak_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sl.addWidget(self.streak_table)
        lay.addWidget(streak_box)

    def _add_habit(self):
        name = self.habit_in.text().strip()
        if not name or name in self._data["habits"]:
            return
        self._data["habits"].append(name)
        _save(self._data)
        self.habit_in.clear()
        self._refresh()

    def _toggle(self, item):
        habit = item.data(Qt.UserRole)
        log   = self._data["log"]
        if self._today not in log:
            log[self._today] = {}
        log[self._today][habit] = not log[self._today].get(habit, False)
        _save(self._data)
        self._refresh()

    def _delete(self):
        sel = self.today_list.currentItem()
        if not sel: return
        habit = sel.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete '{habit}' and all its history?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._data["habits"].remove(habit)
        for v in self._data["log"].values():
            v.pop(habit, None)
        _save(self._data)
        self._refresh()

    def _refresh(self):
        self.today_list.clear()
        today_log = self._data["log"].get(self._today, {})
        for habit in self._data["habits"]:
            done = today_log.get(habit, False)
            item = QListWidgetItem(f"{'[DONE]' if done else '[    ]'}  {habit}")
            item.setData(Qt.UserRole, habit)
            item.setForeground(QColor("#00BFA5") if done else QColor("#CCCCCC"))
            self.today_list.addItem(item)

        self.streak_table.setRowCount(0)
        today = date.today()
        for habit in self._data["habits"]:
            st = _streak(habit, self._data["log"])
            days14 = ""
            for i in range(13, -1, -1):
                d = (today - timedelta(days=i)).isoformat()
                done = self._data["log"].get(d, {}).get(habit, False)
                days14 += "X" if done else "."
            r = self.streak_table.rowCount()
            self.streak_table.insertRow(r)
            self.streak_table.setItem(r, 0, QTableWidgetItem(habit))
            streak_item = QTableWidgetItem(f"{st} day{'s' if st != 1 else ''}")
            streak_item.setForeground(QColor("#00BFA5") if st > 0 else QColor("#888888"))
            self.streak_table.setItem(r, 1, streak_item)
            self.streak_table.setItem(r, 2, QTableWidgetItem(days14))
