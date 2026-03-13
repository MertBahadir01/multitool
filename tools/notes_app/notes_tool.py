"""
Notes & Quick Memo — fast note-taking with text, image attachments,
tagging, search, and pinning. Stored via QSettings (no separate DB needed).
"""

import json
import base64
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QFrame, QSplitter, QFileDialog, QInputDialog,
    QMessageBox, QScrollArea, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QFont, QPixmap, QColor


SETTINGS_KEY = "quick_notes_data"


class NotesApp(QWidget):
    name = "Quick Notes"
    description = "Fast note-taking with tags, images and search"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("MultiToolStudio", "QuickNotes")
        self._notes = []       # list of dicts
        self._filtered = []    # current displayed subset
        self._current_idx = None   # index in self._filtered
        self._dirty = False
        self._build_ui()
        self._load_notes()
        self._refresh_list()

        # auto-save every 30s
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._auto_save)
        self._save_timer.start(30000)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📒 Quick Notes")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        new_btn = QPushButton("➕ New Note")
        new_btn.clicked.connect(self._new_note)
        hl.addWidget(new_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_note)
        hl.addWidget(del_btn)
        root.addWidget(hdr)

        # Search + filter bar
        bar = QFrame()
        bar.setStyleSheet("background:#252526; border-bottom:1px solid #2A2A2A;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        bl.addWidget(QLabel("🔍"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search notes or #tags…")
        self._search.textChanged.connect(self._refresh_list)
        bl.addWidget(self._search, 1)
        pin_btn = QPushButton("📌 Pin")
        pin_btn.setObjectName("secondary")
        pin_btn.clicked.connect(self._toggle_pin)
        bl.addWidget(pin_btn)
        tag_btn = QPushButton("🏷️ Tag")
        tag_btn.setObjectName("secondary")
        tag_btn.clicked.connect(self._edit_tags)
        bl.addWidget(tag_btn)
        img_btn = QPushButton("🖼️ Image")
        img_btn.setObjectName("secondary")
        img_btn.clicked.connect(self._attach_image)
        bl.addWidget(img_btn)
        root.addWidget(bar)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: note list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._note_list = QListWidget()
        self._note_list.setMinimumWidth(220)
        self._note_list.setStyleSheet("""
            QListWidget { background:#1E1E1E; border:none; }
            QListWidget::item { padding:10px 12px; border-bottom:1px solid #2A2A2A; }
            QListWidget::item:selected { background:#1A3A35; color:#00BFA5; }
            QListWidget::item:hover:!selected { background:#2A2A2A; }
        """)
        self._note_list.currentRowChanged.connect(self._on_select)
        ll.addWidget(self._note_list, 1)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#555; font-size:11px; padding:4px 12px;")
        ll.addWidget(self._count_lbl)
        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(8)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Title…")
        self._title_edit.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._title_edit.setStyleSheet("background:#252525; border:none; border-bottom:1px solid #3E3E3E; padding:6px; color:#E0E0E0;")
        self._title_edit.textChanged.connect(self._mark_dirty)
        rl.addWidget(self._title_edit)

        self._tags_lbl = QLabel("")
        self._tags_lbl.setStyleSheet("color:#00BFA5; font-size:11px;")
        rl.addWidget(self._tags_lbl)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Start typing… (supports markdown preview)")
        self._editor.setStyleSheet("""
            QTextEdit {
                background:#1A1A1A; border:none; padding:12px;
                font-size:14px; color:#E0E0E0; line-height:1.6;
            }
        """)
        self._editor.textChanged.connect(self._mark_dirty)
        rl.addWidget(self._editor, 1)

        # Image preview area
        self._img_scroll = QScrollArea()
        self._img_scroll.setWidgetResizable(True)
        self._img_scroll.setMaximumHeight(140)
        self._img_scroll.hide()
        self._img_container = QWidget()
        self._img_row = QHBoxLayout(self._img_container)
        self._img_row.setAlignment(Qt.AlignLeft)
        self._img_scroll.setWidget(self._img_container)
        rl.addWidget(self._img_scroll)

        bottom = QHBoxLayout()
        self._meta_lbl = QLabel("")
        self._meta_lbl.setStyleSheet("color:#555; font-size:11px;")
        bottom.addWidget(self._meta_lbl)
        bottom.addStretch()
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._save_current)
        bottom.addWidget(save_btn)
        rl.addLayout(bottom)

        splitter.addWidget(right)
        splitter.setSizes([240, 760])
        root.addWidget(splitter, 1)

    # ── data ───────────────────────────────────────────────────────────────────
    def _load_notes(self):
        raw = self._settings.value(SETTINGS_KEY, "[]")
        try:
            self._notes = json.loads(raw)
        except Exception:
            self._notes = []

    def _save_notes(self):
        self._settings.setValue(SETTINGS_KEY, json.dumps(self._notes))
        self._dirty = False

    def _auto_save(self):
        if self._dirty:
            self._save_current()

    # ── list ───────────────────────────────────────────────────────────────────
    def _refresh_list(self):
        query = self._search.text().strip().lower()
        if query:
            self._filtered = [n for n in self._notes
                              if query in n.get("title", "").lower()
                              or query in n.get("body", "").lower()
                              or any(query.lstrip("#") in t.lower() for t in n.get("tags", []))]
        else:
            self._filtered = list(self._notes)

        # pinned first
        self._filtered.sort(key=lambda n: (0 if n.get("pinned") else 1, n.get("updated", "")), reverse=False)
        self._filtered.sort(key=lambda n: 0 if n.get("pinned") else 1)

        self._note_list.clear()
        for n in self._filtered:
            pin = "📌 " if n.get("pinned") else ""
            imgs = " 🖼️" if n.get("images") else ""
            title = n.get("title") or "(untitled)"
            tags  = " ".join(f"#{t}" for t in n.get("tags", []))
            preview = n.get("body", "").replace("\n", " ")[:50]
            date = n.get("updated", "")[:10]
            item = QListWidgetItem()
            item.setText(f"{pin}{title}{imgs}\n{preview}\n{date}  {tags}")
            self._note_list.addItem(item)

        self._count_lbl.setText(f"{len(self._filtered)} note(s)")

    def _on_select(self, row):
        if row < 0 or row >= len(self._filtered):
            return
        if self._dirty:
            self._save_current()
        n = self._filtered[row]
        self._current_idx = self._notes.index(n)
        self._title_edit.blockSignals(True)
        self._editor.blockSignals(True)
        self._title_edit.setText(n.get("title", ""))
        self._editor.setPlainText(n.get("body", ""))
        self._title_edit.blockSignals(False)
        self._editor.blockSignals(False)
        tags = " ".join(f"#{t}" for t in n.get("tags", []))
        self._tags_lbl.setText(tags)
        self._meta_lbl.setText(f"Created: {n.get('created','')[:10]}   Updated: {n.get('updated','')[:10]}")
        self._render_images(n.get("images", []))
        self._dirty = False

    def _render_images(self, images):
        while self._img_row.count():
            w = self._img_row.takeAt(0).widget()
            if w: w.deleteLater()
        if not images:
            self._img_scroll.hide()
            return
        self._img_scroll.show()
        for img_data in images:
            lbl = QLabel()
            try:
                raw = img_data.split(",", 1)[1] if "," in img_data else img_data
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(raw))
                lbl.setPixmap(pix.scaledToHeight(120, Qt.SmoothTransformation))
            except Exception:
                lbl.setText("⚠️ Image")
            lbl.setStyleSheet("border:1px solid #3E3E3E; border-radius:4px; margin:4px;")
            self._img_row.addWidget(lbl)

    # ── CRUD ───────────────────────────────────────────────────────────────────
    def _new_note(self):
        if self._dirty:
            self._save_current()
        now = datetime.datetime.now().isoformat()
        note = {"title": "", "body": "", "tags": [], "images": [],
                "pinned": False, "created": now, "updated": now}
        self._notes.insert(0, note)
        self._save_notes()
        self._refresh_list()
        self._note_list.setCurrentRow(0)
        self._title_edit.setFocus()

    def _save_current(self):
        if self._current_idx is None or self._current_idx >= len(self._notes):
            return
        n = self._notes[self._current_idx]
        n["title"] = self._title_edit.text().strip()
        n["body"]  = self._editor.toPlainText()
        n["updated"] = datetime.datetime.now().isoformat()
        self._save_notes()
        self._refresh_list()

    def _delete_note(self):
        row = self._note_list.currentRow()
        if row < 0 or row >= len(self._filtered):
            return
        n = self._filtered[row]
        if QMessageBox.question(self, "Delete", f"Delete '{n.get('title') or 'this note'}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._notes.remove(n)
        self._current_idx = None
        self._dirty = False
        self._save_notes()
        self._refresh_list()
        self._title_edit.clear()
        self._editor.clear()
        self._tags_lbl.setText("")

    def _toggle_pin(self):
        if self._current_idx is None:
            return
        n = self._notes[self._current_idx]
        n["pinned"] = not n.get("pinned", False)
        self._save_notes()
        self._refresh_list()

    def _edit_tags(self):
        if self._current_idx is None:
            QMessageBox.information(self, "No Note", "Select a note first.")
            return
        n = self._notes[self._current_idx]
        current = ", ".join(n.get("tags", []))
        new_tags, ok = QInputDialog.getText(self, "Edit Tags",
                                            "Tags (comma-separated):", text=current)
        if ok:
            n["tags"] = [t.strip().lstrip("#") for t in new_tags.split(",") if t.strip()]
            self._tags_lbl.setText(" ".join(f"#{t}" for t in n["tags"]))
            self._save_notes()
            self._refresh_list()

    def _attach_image(self):
        if self._current_idx is None:
            QMessageBox.information(self, "No Note", "Select a note first.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Attach Image", "",
                                              "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        ext = path.rsplit(".", 1)[-1].lower()
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        data_uri = f"data:image/{ext};base64,{b64}"
        n = self._notes[self._current_idx]
        n.setdefault("images", []).append(data_uri)
        self._save_notes()
        self._render_images(n["images"])

    def _mark_dirty(self):
        self._dirty = True
