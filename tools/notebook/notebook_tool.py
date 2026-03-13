"""Notebook Tool — encrypted, per-user, DB-backed. Mirrors PasswordVaultTool pattern."""

import bcrypt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QDialog, QDialogButtonBox,
    QMessageBox, QSplitter, QFrame, QMenu, QInputDialog, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from core.auth_manager import auth_manager
from tools.notebook.notebook_service import NotebookService


class MasterPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unlock Notebook")
        self.setFixedSize(380, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel("🔐 Enter your account password to decrypt notes")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("Your login password")
        self.pw_input.returnPressed.connect(self.accept)
        layout.addWidget(self.pw_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_password(self):
        return self.pw_input.text()


class NotebookTool(QWidget):
    name = "Notebook"
    description = "Encrypted hierarchical notebook: categories → people → notes"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._svc = None
        self._current_note_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Locked screen ──────────────────────────────────────────────────────
        self.locked_widget = QWidget()
        lw = QVBoxLayout(self.locked_widget)
        lw.setAlignment(Qt.AlignCenter)

        lock_icon = QLabel("📓")
        lock_icon.setFont(QFont("Segoe UI Emoji", 48))
        lock_icon.setAlignment(Qt.AlignCenter)
        lw.addWidget(lock_icon)

        lock_title = QLabel("Notebook Locked")
        lock_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        lock_title.setAlignment(Qt.AlignCenter)
        lock_title.setStyleSheet("color: #00BFA5;")
        lw.addWidget(lock_title)

        lock_sub = QLabel("Notes are encrypted.\nEnter your account password to unlock.")
        lock_sub.setAlignment(Qt.AlignCenter)
        lock_sub.setStyleSheet("color: #888888;")
        lw.addWidget(lock_sub)

        unlock_btn = QPushButton("🔓 Unlock Notebook")
        unlock_btn.setFixedWidth(200)
        unlock_btn.clicked.connect(self._unlock)
        lw.addWidget(unlock_btn, alignment=Qt.AlignCenter)

        layout.addWidget(self.locked_widget)

        # ── Unlocked screen ────────────────────────────────────────────────────
        self.main_widget = QWidget()
        mw = QVBoxLayout(self.main_widget)
        mw.setContentsMargins(24, 24, 24, 24)
        mw.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📓 Notebook")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        hdr.addWidget(title)

        enc_badge = QLabel("🔐 AES-256 Encrypted")
        enc_badge.setStyleSheet(
            "background:#00BFA520; color:#00BFA5; border:1px solid #00BFA540;"
            "border-radius:10px; padding:2px 10px; font-size:11px;"
        )
        hdr.addWidget(enc_badge)
        hdr.addStretch()

        add_cat_btn = QPushButton("➕ Category")
        add_cat_btn.clicked.connect(self._add_category)
        hdr.addWidget(add_cat_btn)

        add_person_btn = QPushButton("➕ Person")
        add_person_btn.clicked.connect(self._add_person)
        hdr.addWidget(add_person_btn)

        add_note_btn = QPushButton("➕ Note")
        add_note_btn.clicked.connect(self._add_note)
        hdr.addWidget(add_note_btn)

        lock_btn = QPushButton("🔒 Lock")
        lock_btn.setObjectName("secondary")
        lock_btn.clicked.connect(self._lock)
        hdr.addWidget(lock_btn)

        mw.addLayout(hdr)

        # Splitter: tree | editor
        splitter = QSplitter(Qt.Horizontal)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setMinimumWidth(240)
        self.tree.currentItemChanged.connect(self._on_select)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        splitter.addWidget(self.tree)

        # Editor panel
        editor_panel = QWidget()
        ep = QVBoxLayout(editor_panel)
        ep.setContentsMargins(12, 0, 0, 0)
        ep.setSpacing(8)

        self.editor_label = QLabel("Select or create a note")
        self.editor_label.setStyleSheet("color: #888888; font-size: 14px;")
        ep.addWidget(self.editor_label)

        self.editor_date = QLabel("")
        self.editor_date.setStyleSheet("color: #555555; font-size: 11px;")
        ep.addWidget(self.editor_date)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Note content…")
        self.editor.setEnabled(False)
        self.editor.textChanged.connect(self._on_text_changed)
        ep.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Note")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_note)
        btn_row.addWidget(self.save_btn)

        del_note_btn = QPushButton("🗑️ Delete")
        del_note_btn.setObjectName("danger")
        del_note_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_note_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00BFA5; font-size: 12px;")
        btn_row.addWidget(self.status_lbl)
        btn_row.addStretch()
        ep.addLayout(btn_row)

        splitter.addWidget(editor_panel)
        splitter.setSizes([260, 740])
        mw.addWidget(splitter)

        layout.addWidget(self.main_widget)
        self.main_widget.hide()

    # ── Lock / Unlock ──────────────────────────────────────────────────────────
    def _unlock(self):
        if not auth_manager.current_user:
            QMessageBox.warning(self, "Error", "Not logged in.")
            return
        dlg = MasterPasswordDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        master_pw = dlg.get_password()
        stored_hash = auth_manager.current_user["password_hash"].encode()
        if not bcrypt.checkpw(master_pw.encode(), stored_hash):
            QMessageBox.critical(self, "Error", "Invalid password.")
            return
        self._svc = NotebookService(auth_manager.get_user_id(), master_pw)
        self.locked_widget.hide()
        self.main_widget.show()
        self._refresh_tree()

    def _lock(self):
        self._svc = None
        self._current_note_id = None
        self.editor.blockSignals(True)
        self.editor.clear()
        self.editor.blockSignals(False)
        self.editor.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.main_widget.hide()
        self.locked_widget.show()

    # ── Tree ───────────────────────────────────────────────────────────────────
    def _refresh_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        if not self._svc:
            self.tree.blockSignals(False)
            return
        for cat in self._svc.get_categories():
            cat_item = QTreeWidgetItem([f"📁  {cat['name']}"])
            cat_item.setData(0, Qt.UserRole, {"kind": "cat", "id": cat["id"], "name": cat["name"]})
            cat_item.setFont(0, QFont("Segoe UI", 11, QFont.Bold))
            for person in self._svc.get_people(cat["id"]):
                p_item = QTreeWidgetItem([f"👤  {person['name']}"])
                p_item.setData(0, Qt.UserRole, {
                    "kind": "person", "id": person["id"],
                    "name": person["name"], "cat_id": cat["id"]
                })
                for note in self._svc.get_notes(person["id"]):
                    preview = note["content"][:40].replace("\n", " ")
                    if not preview.strip():
                        preview = "(empty note)"
                    n_item = QTreeWidgetItem([f"📝  {preview}"])
                    n_item.setData(0, Qt.UserRole, {
                        "kind": "note",
                        "id": note["id"],
                        "person_id": person["id"],
                        "cat_id": cat["id"],
                        "content": note["content"],
                        "created_at": str(note.get("created_at", ""))[:16],
                        "updated_at": str(note.get("updated_at", ""))[:16],
                    })
                    p_item.addChild(n_item)
                cat_item.addChild(p_item)
            self.tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)
            for j in range(cat_item.childCount()):
                cat_item.child(j).setExpanded(True)
        self.tree.blockSignals(False)

    def _on_select(self, current, _prev):
        if not current:
            return
        data = current.data(0, Qt.UserRole)
        if not data:
            return
        if data["kind"] == "note":
            self._current_note_id = data["id"]
            self.editor.blockSignals(True)
            self.editor.setPlainText(data["content"])
            self.editor.blockSignals(False)
            self.editor.setEnabled(True)
            self.save_btn.setEnabled(False)
            self.editor_label.setText("📝  Note")
            self.editor_label.setStyleSheet("color: #00BFA5; font-size: 14px;")
            self.editor_date.setText(
                f"Created: {data['created_at']}   Updated: {data['updated_at']}"
            )
        else:
            self._current_note_id = None
            self.editor.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.editor.blockSignals(True)
            self.editor.clear()
            self.editor.blockSignals(False)
            self.editor_label.setText(
                f"📁  {data['name']}" if data["kind"] == "cat" else f"👤  {data['name']}"
            )
            self.editor_label.setStyleSheet("color: #888888; font-size: 14px;")
            self.editor_date.setText("")

    def _on_text_changed(self):
        if self._current_note_id is not None:
            self.save_btn.setEnabled(True)

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def _add_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if ok and name.strip():
            try:
                self._svc.add_category(name.strip())
                self._refresh_tree()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _add_person(self):
        cats = self._svc.get_categories()
        if not cats:
            QMessageBox.information(self, "No Category", "Create a category first.")
            return
        # Use currently selected category if possible
        data = self._selected_data()
        cat_id = None
        if data:
            if data["kind"] == "cat":
                cat_id = data["id"]
            elif data["kind"] in ("person", "note"):
                cat_id = data["cat_id"]
        if cat_id is None:
            cat_names = [c["name"] for c in cats]
            choice, ok = QInputDialog.getItem(
                self, "Select Category", "Add person to:", cat_names, 0, False
            )
            if not ok:
                return
            cat_id = next(c["id"] for c in cats if c["name"] == choice)
        name, ok = QInputDialog.getText(self, "New Person", "Person name:")
        if ok and name.strip():
            try:
                self._svc.add_person(cat_id, name.strip())
                self._refresh_tree()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _add_note(self):
        data = self._selected_data()
        person_id = None
        if data:
            if data["kind"] == "person":
                person_id = data["id"]
            elif data["kind"] == "note":
                person_id = data["person_id"]
        if person_id is None:
            QMessageBox.information(self, "Select Person", "Select a person first.")
            return
        note_id = self._svc.add_note(person_id, "")
        self._refresh_tree()
        self._select_note_by_id(note_id)

    def _save_note(self):
        if self._current_note_id is None:
            return
        self._svc.update_note(self._current_note_id, self.editor.toPlainText())
        self.save_btn.setEnabled(False)
        self._show_status("✓ Saved")
        saved_id = self._current_note_id
        self._refresh_tree()
        self._select_note_by_id(saved_id)

    def _delete_selected(self):
        data = self._selected_data()
        if not data:
            return
        msgs = {
            "cat":    f"Delete category '{data['name']}' and ALL its data?",
            "person": f"Delete person '{data['name']}' and all their notes?",
            "note":   "Delete this note?",
        }
        if QMessageBox.question(self, "Delete", msgs[data["kind"]],
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if data["kind"] == "cat":
            self._svc.delete_category(data["id"])
        elif data["kind"] == "person":
            self._svc.delete_person(data["id"])
        elif data["kind"] == "note":
            self._svc.delete_note(data["id"])
            self._current_note_id = None
            self.editor.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.editor.blockSignals(True)
            self.editor.clear()
            self.editor.blockSignals(False)
        self._refresh_tree()

    # ── Context menu ───────────────────────────────────────────────────────────
    def _context_menu(self, pos):
        data = self._selected_data()
        if not data:
            return
        menu = QMenu(self)
        if data["kind"] == "cat":
            menu.addAction("➕ Add Person", self._add_person)
        elif data["kind"] == "person":
            menu.addAction("➕ Add Note", self._add_note)
        menu.addSeparator()
        menu.addAction("🗑 Delete", self._delete_selected)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _selected_data(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _select_note_by_id(self, note_id: int):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            for j in range(cat_item.childCount()):
                p_item = cat_item.child(j)
                for k in range(p_item.childCount()):
                    n_item = p_item.child(k)
                    d = n_item.data(0, Qt.UserRole)
                    if d and d.get("id") == note_id:
                        self.tree.setCurrentItem(n_item)
                        return

    def _show_status(self, msg: str):
        self.status_lbl.setText(msg)
        QTimer.singleShot(3000, lambda: self.status_lbl.setText(""))