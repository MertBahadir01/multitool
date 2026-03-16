"""
Task Manager Tool
=================
Personal task organiser with:
  • Multiple named lists with accent colours
  • Tasks: title, description, due date, priority, reminder, subtasks
  • Views: Today | Upcoming | All / by list
  • Filter by priority / status / search
  • Progress bar per list and overall
  • Inline subtask checklist
  • Reminder badge (visual) for overdue tasks
"""

import datetime

from PySide6.QtWidgets import (
    QDateEdit,QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QSplitter, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QCheckBox, QScrollArea, QMessageBox, QInputDialog, QProgressBar,
    QTabWidget, QGridLayout, QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QFont, QColor

from core.auth_manager import auth_manager
from tools.task_manager.task_service import TaskService

PRIORITY_COLORS = {"high": "#F44336", "medium": "#FF9800", "low": "#4CAF50"}
PRIORITY_ICONS  = {"high": "🔴", "medium": "🟡", "low": "🟢"}
LIST_COLOR_OPTIONS = [
    "#00BFA5", "#2196F3", "#9C27B0", "#FF9800",
    "#F44336", "#4CAF50", "#FF5722", "#607D8B",
]


# ── Task Dialog (add / edit) ───────────────────────────────────────────────────
class TaskDialog(QDialog):
    def __init__(self, parent=None, lists=None, task=None, default_list_id=None):
        super().__init__(parent)
        self._lists  = lists or []
        self._task   = task
        self.setWindowTitle("Görevi Düzenle" if task else "Yeni Görev")
        self.setFixedWidth(460)
        self._build_ui(default_list_id)
        if task:
            self._populate(task)

    def _build_ui(self, default_list_id):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        form = QFormLayout(); form.setSpacing(10)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Görev başlığı…")
        form.addRow("Başlık*:", self.title_edit)

        self.list_combo = QComboBox()
        for lst in self._lists:
            self.list_combo.addItem(f"  {lst['name']}", lst["id"])
            if lst["id"] == default_list_id:
                self.list_combo.setCurrentIndex(self.list_combo.count() - 1)
        form.addRow("Liste:", self.list_combo)

        self.priority_combo = QComboBox()
        for p in ["high", "medium", "low"]:
            self.priority_combo.addItem(f"{PRIORITY_ICONS[p]}  {p.capitalize()}", p)
        self.priority_combo.setCurrentIndex(1)
        form.addRow("Öncelik:", self.priority_combo)

        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True) # This enables the calendar dropdown
        self.due_edit.setDisplayFormat("yyyy-MM-dd")
        self.due_edit.setDate(QDate.currentDate())
        self.due_edit.setSpecialValueText(" ") # Allows "empty" look if needed
        form.addRow("Son tarih:", self.due_edit)


        self.reminder_edit = QDateEdit()
        self.reminder_edit.setCalendarPopup(True)
        self.reminder_edit.setDisplayFormat("yyyy-MM-dd")
        self.reminder_edit.setDate(QDate.currentDate())
        self.reminder_edit.setSpecialValueText(" ")
        form.addRow("Hatırlatıcı:", self.reminder_edit)


#        self.due_edit = QLineEdit()
#        self.due_edit.setPlaceholderText("YYYY-AA-GG  (boş bırakılabilir)")
#        form.addRow("Son tarih:", self.due_edit)
#
#        self.reminder_edit = QLineEdit()
#        self.reminder_edit.setPlaceholderText("YYYY-AA-GG  hatırlatıcı")
#        form.addRow("Hatırlatıcı:", self.reminder_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Açıklama / notlar…")
        self.desc_edit.setFixedHeight(80)
        form.addRow("Açıklama:", self.desc_edit)

        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _populate(self, t):
        self.title_edit.setText(t.get("title", ""))
        self.desc_edit.setPlainText(t.get("description", "") or "")
        
        # Parse due_date string to QDate
        due_str = t.get("due_date", "")
        if due_str:
            self.due_edit.setDate(QDate.fromString(due_str, Qt.ISODate))
            
        # Parse reminder string to QDate
        rem_str = t.get("reminder", "")
        if rem_str:
            self.reminder_edit.setDate(QDate.fromString(rem_str, Qt.ISODate))

#        self.title_edit.setText(t.get("title", ""))
#        self.desc_edit.setPlainText(t.get("description", "") or "")
#        self.due_edit.setText(t.get("due_date", "") or "")
#        self.reminder_edit.setText(t.get("reminder", "") or "")
        for i in range(self.priority_combo.count()):
            if self.priority_combo.itemData(i) == t.get("priority", "medium"):
                self.priority_combo.setCurrentIndex(i); break
        for i in range(self.list_combo.count()):
            if self.list_combo.itemData(i) == t.get("list_id"):
                self.list_combo.setCurrentIndex(i); break

    def get_data(self) -> dict:
        return {
            "title":       self.title_edit.text().strip(),
            "list_id":     self.list_combo.currentData(),
            "priority":    self.priority_combo.currentData(),
            "due_date":    self.due_edit.date().toString(Qt.ISODate),
            "reminder":    self.reminder_edit.date().toString(Qt.ISODate),
#            "due_date":    self.due_edit.text().strip(),
#            "reminder":    self.reminder_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
        }


# ── List Edit Dialog ───────────────────────────────────────────────────────────
class ListDialog(QDialog):
    def __init__(self, parent=None, name="", color="#00BFA5"):
        super().__init__(parent)
        self.setWindowTitle("Liste")
        self.setFixedWidth(340)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        form = QFormLayout(); form.setSpacing(10)
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Liste adı…")
        form.addRow("Ad:", self.name_edit)
        lay.addLayout(form)

        lay.addWidget(QLabel("Renk:"))
        color_row = QHBoxLayout()
        self._color = color
        self._color_btns = []
        for c in LIST_COLOR_OPTIONS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.setStyleSheet(f"background:{c}; border-radius:14px; border:2px solid "
                              f"{'#fff' if c == color else 'transparent'};")
            btn.clicked.connect(lambda _, col=c: self._select_color(col))
            color_row.addWidget(btn)
            self._color_btns.append((btn, c))
        lay.addLayout(color_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _select_color(self, color):
        self._color = color
        for btn, c in self._color_btns:
            btn.setStyleSheet(f"background:{c}; border-radius:14px; border:2px solid "
                              f"{'#fff' if c == color else 'transparent'};")

    def get_data(self):
        return {"name": self.name_edit.text().strip(), "color": self._color}


# ── Task Row Widget (used in the task list on the right) ──────────────────────
class TaskRowWidget(QFrame):
    """One task card: checkbox | priority dot | title | due badge | subtask bar."""

    def __init__(self, task: dict, subtasks: list, on_toggle, on_click, parent=None):
        super().__init__(parent)
        self._task   = task
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)

        today  = datetime.date.today().isoformat()
        is_done = task["status"] == "completed"
        due     = task.get("due_date") or ""
        overdue = due and due < today and not is_done

        border_color = PRIORITY_COLORS.get(task.get("priority", "medium"), "#3E3E3E")
        if is_done:
            border_color = "#333"
        elif overdue:
            border_color = "#F44336"

        self.setStyleSheet(f"""
            QFrame {{
                background:#212121;
                border:1px solid {border_color};
                border-radius:8px;
                margin:2px 4px;
            }}
            QFrame:hover {{ background:#262626; border-color:#00BFA5; }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        # Checkbox
        chk = QCheckBox()
        chk.setChecked(is_done)
        chk.setStyleSheet("QCheckBox::indicator { width:18px; height:18px; }")
        chk.toggled.connect(lambda state: on_toggle(task["id"], state))
        lay.addWidget(chk)

        # Body
        body = QVBoxLayout()
        body.setSpacing(3)

        title_row = QHBoxLayout()
        title_lbl = QLabel(task["title"])
        title_lbl.setFont(QFont("Segoe UI", 12))
        if is_done:
            title_lbl.setStyleSheet("color:#555; text-decoration:line-through;")
        else:
            title_lbl.setStyleSheet("color:#E0E0E0;")
        title_row.addWidget(title_lbl)

        pri = task.get("priority", "medium")
        pri_lbl = QLabel(PRIORITY_ICONS.get(pri, ""))
        pri_lbl.setToolTip(pri.capitalize())
        title_row.addWidget(pri_lbl)
        title_row.addStretch()

        if due:
            due_lbl = QLabel(f"📅 {due}")
            color = "#F44336" if overdue else ("#FF9800" if due == today else "#666")
            due_lbl.setStyleSheet(f"color:{color}; font-size:11px;")
            title_row.addWidget(due_lbl)

        body.addLayout(title_row)

        # Subtask progress
        if subtasks:
            done_sub = sum(1 for s in subtasks if s["done"])
            bar = QProgressBar()
            bar.setRange(0, len(subtasks))
            bar.setValue(done_sub)
            bar.setFixedHeight(4)
            bar.setTextVisible(False)
            bar.setStyleSheet("""
                QProgressBar { background:#333; border-radius:2px; border:none; }
                QProgressBar::chunk { background:#00BFA5; border-radius:2px; }
            """)
            sub_lbl = QLabel(f"{done_sub}/{len(subtasks)} adım")
            sub_lbl.setStyleSheet("color:#555; font-size:10px;")
            sub_row = QHBoxLayout()
            sub_row.addWidget(bar)
            sub_row.addWidget(sub_lbl)
            body.addLayout(sub_row)

        if task.get("description"):
            desc = QLabel(task["description"][:80] + ("…" if len(task["description"]) > 80 else ""))
            desc.setStyleSheet("color:#666; font-size:11px;")
            body.addWidget(desc)

        lay.addLayout(body, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click(self._task)
        super().mousePressEvent(event)


# ── Task Detail Panel (right side, shows on task click) ──────────────────────
class TaskDetailPanel(QFrame):
    task_updated = None   # set externally

    def __init__(self, svc: TaskService, parent=None):
        super().__init__(parent)
        self._svc  = svc
        self._task = None
        self.setMinimumWidth(300)
        self.setStyleSheet("background:#1A1A1A; border-left:1px solid #2A2A2A;")
        self._build_ui()
        self._show_empty()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._empty_lbl = QLabel("← Bir görev seçin")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet("color:#444; font-size:14px;")
        root.addWidget(self._empty_lbl)

        self._detail = QWidget(); self._detail.hide()
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(16, 16, 16, 16)
        dl.setSpacing(12)

        self._title_lbl = QLabel()
        self._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._title_lbl.setStyleSheet("color:#00BFA5;")
        self._title_lbl.setWordWrap(True)
        dl.addWidget(self._title_lbl)

        self._meta_lbl = QLabel()
        self._meta_lbl.setStyleSheet("color:#666; font-size:11px;")
        dl.addWidget(self._meta_lbl)

        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet("color:#AAA; font-size:12px;")
        dl.addWidget(self._desc_lbl)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#2A2A2A;")
        dl.addWidget(sep)

        dl.addWidget(QLabel("✅ Adımlar:", styleSheet="color:#888; font-size:11px; font-weight:bold;"))
        self._sub_scroll = QScrollArea()
        self._sub_scroll.setWidgetResizable(True)
        self._sub_scroll.setFrameShape(QFrame.NoFrame)
        self._sub_scroll.setMaximumHeight(220)
        self._sub_container = QWidget()
        self._sub_layout = QVBoxLayout(self._sub_container)
        self._sub_layout.setContentsMargins(0, 0, 0, 0)
        self._sub_layout.setSpacing(4)
        self._sub_scroll.setWidget(self._sub_container)
        dl.addWidget(self._sub_scroll)

        add_sub_row = QHBoxLayout()
        self._sub_edit = QLineEdit()
        self._sub_edit.setPlaceholderText("Yeni adım…")
        self._sub_edit.returnPressed.connect(self._add_subtask)
        add_sub_row.addWidget(self._sub_edit, 1)
        add_sub_btn = QPushButton("➕")
        add_sub_btn.setFixedWidth(32)
        add_sub_btn.clicked.connect(self._add_subtask)
        add_sub_row.addWidget(add_sub_btn)
        dl.addLayout(add_sub_row)

        dl.addStretch()

        btn_row = QHBoxLayout()
        complete_btn = QPushButton("✅ Tamamla")
        complete_btn.clicked.connect(self._toggle_complete)
        btn_row.addWidget(complete_btn)
        del_btn = QPushButton("🗑️ Sil")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_task)
        btn_row.addWidget(del_btn)
        dl.addLayout(btn_row)

        root.addWidget(self._detail, 1)

    def load_task(self, task: dict):
        self._task = task
        self._empty_lbl.hide()
        self._detail.show()
        self._refresh_display()

    def _refresh_display(self):
        t = self._task
        self._title_lbl.setText(t["title"])
        pri = t.get("priority", "medium")
        due = t.get("due_date") or "—"
        rem = t.get("reminder") or ""
        status = "✅ Tamamlandı" if t["status"] == "completed" else "⏳ Bekliyor"
        meta = f"{PRIORITY_ICONS[pri]} {pri.capitalize()}   📅 {due}   {status}"
        if rem:
            meta += f"   🔔 {rem}"
        self._meta_lbl.setText(meta)
        self._desc_lbl.setText(t.get("description") or "")
        self._refresh_subtasks()

    def _refresh_subtasks(self):
        while self._sub_layout.count():
            w = self._sub_layout.takeAt(0).widget()
            if w: w.deleteLater()
        subtasks = self._svc.get_subtasks(self._task["id"])
        for sub in subtasks:
            row = QHBoxLayout()
            chk = QCheckBox(sub["title"])
            chk.setChecked(bool(sub["done"]))
            chk.toggled.connect(lambda state, sid=sub["id"]: self._toggle_sub(sid, state))
            row.addWidget(chk, 1)
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(20, 20)
            del_btn.setStyleSheet("QPushButton{background:transparent;color:#555;border:none;}")
            del_btn.clicked.connect(lambda _, sid=sub["id"]: self._delete_sub(sid))
            row.addWidget(del_btn)
            w = QWidget(); w.setLayout(row)
            self._sub_layout.addWidget(w)
        self._sub_layout.addStretch()

    def _add_subtask(self):
        text = self._sub_edit.text().strip()
        if not text or not self._task: return
        self._svc.add_subtask(self._task["id"], text)
        self._sub_edit.clear()
        self._refresh_subtasks()
        if self.task_updated: self.task_updated()

    def _toggle_sub(self, sid, done):
        self._svc.set_subtask_done(sid, done)
        if self.task_updated: self.task_updated()

    def _delete_sub(self, sid):
        self._svc.delete_subtask(sid)
        self._refresh_subtasks()
        if self.task_updated: self.task_updated()

    def _toggle_complete(self):
        if not self._task: return
        new_status = "pending" if self._task["status"] == "completed" else "completed"
        self._svc.set_status(self._task["id"], new_status)
        self._task["status"] = new_status
        self._refresh_display()
        if self.task_updated: self.task_updated()

    def _delete_task(self):
        if not self._task: return
        if QMessageBox.question(self, "Sil", f"'{self._task['title']}' silinsin mi?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_task(self._task["id"])
        self._show_empty()
        if self.task_updated: self.task_updated()

    def _show_empty(self):
        self._task = None
        self._detail.hide()
        self._empty_lbl.show()

    def clear(self):
        self._show_empty()


# ── Main Task Manager Tool ────────────────────────────────────────────────────
class TaskManagerTool(QWidget):
    name        = "Task Manager"
    description = "Listeler, görevler, alt adımlar ve son tarihlerle kişisel görev yöneticisi"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc    = TaskService(user["id"]) if user else None
        self._lists  : list[dict] = []
        self._tasks  : list[dict] = []
        self._active_list_id: int | None = None   # None = show all/today/upcoming
        self._active_view   = "today"             # "today" | "upcoming" | "all" | list_id
        self._search_query  = ""
        self._filter_priority = ""
        self._filter_status   = ""
        self._build_ui()
        if self._svc:
            self._load_lists()
            self._refresh_tasks()
        # reminder check every minute
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(60_000)
        self._notified_ids: set[int] = set()

    # ── UI build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("✅ Task Manager")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍 Görev ara…")
        self._search_box.setFixedWidth(220)
        self._search_box.textChanged.connect(self._on_search)
        hl.addWidget(self._search_box)

        hl.addWidget(QLabel("Öncelik:"))
        self._pri_filter = QComboBox()
        self._pri_filter.addItems(["Tümü", "🔴 High", "🟡 Medium", "🟢 Low"])
        self._pri_filter.setFixedWidth(110)
        self._pri_filter.currentIndexChanged.connect(self._on_filter_change)
        hl.addWidget(self._pri_filter)

        hl.addWidget(QLabel("Durum:"))
        self._status_filter = QComboBox()
        self._status_filter.addItems(["Tümü", "⏳ Bekleyen", "✅ Tamamlanan"])
        self._status_filter.setFixedWidth(130)
        self._status_filter.currentIndexChanged.connect(self._on_filter_change)
        hl.addWidget(self._status_filter)

        add_btn = QPushButton("➕ Görev Ekle")
        add_btn.clicked.connect(self._add_task)
        hl.addWidget(add_btn)
        root.addWidget(hdr)

        # ── Main splitter ──────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: sidebar (views + lists)
        left = QWidget()
        left.setMaximumWidth(230)
        left.setStyleSheet("background:#1A1A1A;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 12, 8, 12)
        ll.setSpacing(4)

        # Smart views
        ll.addWidget(QLabel("GÖRÜNÜMLER", styleSheet="color:#444; font-size:10px; padding:0 4px 4px 4px;"))
        for icon, label, view_id in [
            ("📅", "Bugün",    "today"),
            ("📆", "Yaklaşan", "upcoming"),
            ("📋", "Tümü",     "all"),
        ]:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setObjectName("view_btn")
            btn.setStyleSheet(self._view_btn_style())
            btn.clicked.connect(lambda _, v=view_id: self._set_view(v))
            setattr(self, f"_view_btn_{view_id}", btn)
            ll.addWidget(btn)

        ll.addSpacing(12)

        # Lists header
        list_hdr = QHBoxLayout()
        list_hdr.addWidget(QLabel("LİSTELER", styleSheet="color:#888; font-size:10px; font-weight:bold;"))
        list_hdr.addStretch()
        ll.addLayout(list_hdr)

        add_list_btn = QPushButton("＋  Yeni Liste")
        add_list_btn.setFixedHeight(32)
        add_list_btn.setAutoDefault(False)
        add_list_btn.setDefault(False)
        add_list_btn.setStyleSheet("""
            QPushButton {
                background:#1A3A35; color:#00BFA5;
                border:1px solid #00BFA5; border-radius:6px;
                font-size:12px; font-weight:bold; padding:0 8px;
            }
            QPushButton:hover { background:#1F4A40; }
            QPushButton:pressed { background:#143028; }
        """)
        add_list_btn.clicked.connect(self._add_list)
        ll.addWidget(add_list_btn)

        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet("""
            QListWidget { background:transparent; border:none; }
            QListWidget::item { padding:7px 8px; border-radius:6px; }
            QListWidget::item:selected { background:#1A3A35; color:#00BFA5; }
            QListWidget::item:hover:!selected { background:#252525; }
        """)
        self._list_widget.currentRowChanged.connect(self._on_list_select)
        self._list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_widget.customContextMenuRequested.connect(self._list_context_menu)
        ll.addWidget(self._list_widget, 1)

        # Stats strip at bottom of sidebar
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("color:#444; font-size:10px; padding:4px;")
        self._stats_lbl.setWordWrap(True)
        ll.addWidget(self._stats_lbl)
        splitter.addWidget(left)

        # Middle: task list
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self._view_title = QLabel("Bugün")
        self._view_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._view_title.setStyleSheet(
            "color:#CCCCCC; padding:12px 16px 8px 16px; background:#1C1C1C;")
        ml.addWidget(self._view_title)

        # Overall progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#00BFA5; border-radius:2px; }
        """)
        ml.addWidget(self._progress_bar)

        # Scrollable task area
        self._task_scroll = QScrollArea()
        self._task_scroll.setWidgetResizable(True)
        self._task_scroll.setFrameShape(QFrame.NoFrame)
        self._task_scroll.setStyleSheet("background:#1C1C1C;")
        self._tasks_container = QWidget()
        self._tasks_container.setStyleSheet("background:#1C1C1C;")
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(8, 8, 8, 8)
        self._tasks_layout.setSpacing(4)
        self._tasks_layout.setAlignment(Qt.AlignTop)
        self._task_scroll.setWidget(self._tasks_container)
        ml.addWidget(self._task_scroll, 1)

        self._empty_tasks_lbl = QLabel("🎉 Görev yok!")
        self._empty_tasks_lbl.setAlignment(Qt.AlignCenter)
        self._empty_tasks_lbl.setStyleSheet("color:#333; font-size:14px; padding:40px;")
        self._empty_tasks_lbl.hide()
        ml.addWidget(self._empty_tasks_lbl)
        splitter.addWidget(mid)

        # Right: task detail panel
        self._detail = TaskDetailPanel(self._svc)
        self._detail.task_updated = self._refresh_tasks
        splitter.addWidget(self._detail)

        splitter.setSizes([220, 620, 360])
        root.addWidget(splitter, 1)

        # Activate "today" view
        self._view_btn_today.setChecked(True)

    def _view_btn_style(self):
        return """
            QPushButton {
                background:transparent; color:#AAAAAA;
                border:none; border-radius:6px;
                text-align:left; padding:7px 10px; font-size:13px;
            }
            QPushButton:hover { background:#252525; color:#fff; }
            QPushButton:checked { background:#1A3A35; color:#00BFA5; font-weight:bold; }
        """

    # ── Lists ──────────────────────────────────────────────────────────────────
    def _load_lists(self):
        self._lists = self._svc.get_lists()
        self._list_widget.clear()
        for lst in self._lists:
            color = lst.get("color", "#00BFA5")
            stats = self._svc.get_stats(lst["id"])
            pct   = int(stats["completed"] / max(stats["total"], 1) * 100)
            item  = QListWidgetItem(f"  ● {lst['name']}  ({stats['completed']}/{stats['total']})")
            item.setForeground(QColor(color))
            item.setData(Qt.UserRole, lst)
            self._list_widget.addItem(item)

    def _on_list_select(self, row):
        if row < 0 or row >= len(self._lists): return
        lst = self._lists[row]
        self._active_list_id = lst["id"]
        self._active_view    = lst["id"]
        self._detail.clear()
        for v in ("today", "upcoming", "all"):
            btn = getattr(self, f"_view_btn_{v}", None)
            if btn: btn.setChecked(False)
        self._view_title.setText(lst["name"])
        self._refresh_tasks()

    def _add_list(self):
        dlg = ListDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        if not d["name"]:
            QMessageBox.warning(self, "Eksik", "Liste adi bos olamaz.")
            return
        self._svc.add_list(d["name"], d["color"])
        self._load_lists()

    def _list_context_menu(self, pos):
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._lists): return
        lst = self._lists[row]
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        rename = menu.addAction("✏️ Yeniden Adlandır / Renk")
        delete = menu.addAction("🗑️ Sil")
        action = menu.exec(self._list_widget.mapToGlobal(pos))
        if action == rename:
            dlg = ListDialog(self, name=lst["name"], color=lst.get("color", "#00BFA5"))
            if dlg.exec() == QDialog.Accepted:
                d = dlg.get_data()
                if d["name"]:
                    self._svc.rename_list(lst["id"], d["name"], d["color"])
                    self._load_lists()
        elif action == delete:
            if QMessageBox.question(self, "Sil",
                                    f"'{lst['name']}' listesi ve tüm görevleri silinsin mi?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self._svc.delete_list(lst["id"])
                self._set_view("all")
                self._load_lists()

    # ── Views ──────────────────────────────────────────────────────────────────
    def _set_view(self, view_id):
        self._active_view    = view_id
        self._active_list_id = None
        self._list_widget.clearSelection()
        self._detail.clear()
        for v in ("today", "upcoming", "all"):
            btn = getattr(self, f"_view_btn_{v}", None)
            if btn: btn.setChecked(v == view_id)
        labels = {"today": "📅 Bugün", "upcoming": "📆 Yaklaşan", "all": "📋 Tüm Görevler"}
        self._view_title.setText(labels.get(str(view_id), str(view_id)))
        self._refresh_tasks()

    # ── Tasks ──────────────────────────────────────────────────────────────────
    def _on_search(self, text):
        self._search_query = text
        self._refresh_tasks()

    def _on_filter_change(self):
        pri_map    = {"Tümü": "", "🔴 High": "high", "🟡 Medium": "medium", "🟢 Low": "low"}
        status_map = {"Tümü": "", "⏳ Bekleyen": "pending", "✅ Tamamlanan": "completed"}
        self._filter_priority = pri_map.get(self._pri_filter.currentText(), "")
        self._filter_status   = status_map.get(self._status_filter.currentText(), "")
        self._refresh_tasks()

    def _refresh_tasks(self):
        if not self._svc: return

        view = self._active_view
        if view == "today":
            tasks = self._svc.get_tasks_due_today()
        elif view == "upcoming":
            tasks = self._svc.get_tasks_upcoming()
        else:
            list_id = self._active_list_id if isinstance(view, int) else None
            tasks = self._svc.get_tasks(
                list_id=list_id,
                status=self._filter_status or None,
                priority=self._filter_priority or None,
                search=self._search_query,
            )

        self._tasks = tasks

        # progress bar
        stats = self._svc.get_stats(self._active_list_id)
        self._progress_bar.setRange(0, max(stats["total"], 1))
        self._progress_bar.setValue(stats["completed"])
        self._stats_lbl.setText(
            f"Toplam: {stats['total']}  ✅ {stats['completed']}  "
            f"⏳ {stats['pending']}  🔴 {stats['overdue']} gecikmiş"
        )

        # render task rows
        while self._tasks_layout.count():
            item = self._tasks_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not tasks:
            self._empty_tasks_lbl.show()
            return
        self._empty_tasks_lbl.hide()

        for task in tasks:
            subtasks = self._svc.get_subtasks(task["id"])
            row = TaskRowWidget(
                task, subtasks,
                on_toggle=self._on_task_toggle,
                on_click=self._on_task_click,
            )
            self._tasks_layout.addWidget(row)
        self._tasks_layout.addStretch()

        # Reload lists (counts may have changed)
        self._load_lists()

    def _on_task_toggle(self, task_id: int, checked: bool):
        self._svc.set_status(task_id, "completed" if checked else "pending")
        self._refresh_tasks()

    def _on_task_click(self, task: dict):
        # Reload fresh copy from DB
        fresh = self._svc.get_tasks(search="")
        fresh_map = {t["id"]: t for t in fresh}
        self._detail.load_task(fresh_map.get(task["id"], task))

    def _add_task(self):
        default_lid = self._active_list_id if isinstance(self._active_view, int) else None
        dlg = TaskDialog(self, lists=self._lists, default_list_id=default_lid)
        if dlg.exec() != QDialog.Accepted: return
        d = dlg.get_data()
        if not d["title"]:
            QMessageBox.warning(self, "Eksik", "Görev başlığı gerekli."); return
        if not d["list_id"] and not self._lists:
            QMessageBox.information(self, "Liste Yok",
                                    "Önce sol panelden bir liste oluşturun."); return
        list_id = d["list_id"] or (self._lists[0]["id"] if self._lists else None)
        if not list_id: return
        self._svc.add_task(
            list_id, d["title"], d["description"],
            d["due_date"], d["priority"], d["reminder"]
        )
        self._refresh_tasks()

    # ── Reminder check ─────────────────────────────────────────────────────────
    def _check_reminders(self):
        if not self._svc: return
        today = datetime.date.today().isoformat()
        tasks = self._svc.get_tasks(status="pending")
        for t in tasks:
            rem = t.get("reminder") or ""
            if rem and rem <= today and t["id"] not in self._notified_ids:
                self._notified_ids.add(t["id"])
                QMessageBox.information(
                    self, "🔔 Hatırlatıcı",
                    f"Hatırlatıcı: {t['title']}\n(Son tarih: {t.get('due_date','—')})"
                )