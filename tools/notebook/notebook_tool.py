"""
Notebook Tool — DB-backed, encrypted notes
  categories → people → notes (tree)
  notes: encrypted with user's master password
  visible metadata: category/person names, dates, user_id only
"""

import base64
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QFrame, QSplitter,
    QInputDialog, QMessageBox, QMenu, QDialog, QLineEdit,
    QFormLayout, QDialogButtonBox, QScrollArea, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

from core.auth_manager import auth_manager
from tools.notebook.notebook_service import NotebookService


class NotebookTool(QWidget):
    name        = "Notebook"
    description = "Encrypted hierarchical notebook: categories → people → notes"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._widget = NotebookWidget()
        layout.addWidget(self._widget)


class ImageViewerDialog(QDialog):
    """Full-size image viewer — double-click a thumbnail to open."""
    def __init__(self, pixmap: QPixmap, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"🖼️  {filename}")
        self.setMinimumSize(400, 300)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        lbl = QLabel()
        screen = self.screen().availableGeometry() if self.screen() else None
        max_w = (screen.width()  - 80)  if screen else 1200
        max_h = (screen.height() - 120) if screen else 900
        if pixmap.width() > max_w or pixmap.height() > max_h:
            pixmap = pixmap.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignCenter)
        scroll.setWidget(lbl)
        lay.addWidget(scroll, 1)
        close_btn = QPushButton("✕  Close")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignRight)
        self.resize(min(pixmap.width() + 40, max_w),
                    min(pixmap.height() + 80, max_h))


class ImageThumb(QLabel):
    """Thumbnail: double-click = full-size viewer, right-click = delete."""
    def __init__(self, pixmap: QPixmap, image_id: int,
                 filename: str, on_delete, parent=None):
        super().__init__(parent)
        self._full_pix  = pixmap
        self._image_id  = image_id
        self._filename  = filename
        self._on_delete = on_delete
        self.setPixmap(pixmap.scaledToHeight(180, Qt.SmoothTransformation))
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #3E3E3E; border-radius: 6px;
                margin: 4px; background: #1A1A1A;
            }
            QLabel:hover { border: 1px solid #00BFA5; }
        """)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Double-click to open  |  Right-click to delete\n{filename}")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            ImageViewerDialog(self._full_pix, self._filename, self).exec()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        open_act   = menu.addAction("🔍 Open full size")
        delete_act = menu.addAction("🗑️ Delete image")
        action = menu.exec(event.globalPos())
        if action == open_act:
            ImageViewerDialog(self._full_pix, self._filename, self).exec()
        elif action == delete_act:
            if QMessageBox.question(
                    self, "Delete Image", f"Delete '{self._filename}'?",
                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self._on_delete(self._image_id)


class MasterPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔐 Notebook — Enter Master Password")
        self.setFixedWidth(380)
        self.setStyleSheet("background:#1E1E1E; color:#E0E0E0;")
        lay = QVBoxLayout(self)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 24, 24, 24)

        info = QLabel(
#            "Note contents are encrypted with your master password.\n"
#            "This is typically your login password."
        )
        info.setStyleSheet("color:#888; font-size:13px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QFormLayout()
        self._pwd = QLineEdit()
        self._pwd.setEchoMode(QLineEdit.Password)
        self._pwd.setPlaceholderText("Master password…")
        self._pwd.setStyleSheet(
            "background:#252525; border:1px solid #3E3E3E; border-radius:6px;"
            "padding:8px; font-size:14px; color:#E0E0E0;"
        )
        form.addRow("Password:", self._pwd)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self._pwd.returnPressed.connect(self.accept)

    def password(self) -> str:
        return self._pwd.text()


class NotebookWidget(QWidget):

    def __init__(self):
        super().__init__()
        self._svc = None
        self._current = None
        self._build_ui()
        self._prompt_master_password()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Lock screen ───────────────────────────────────────────────────────
        self.locked_widget = QWidget()
        lw = QVBoxLayout(self.locked_widget)
        lw.setAlignment(Qt.AlignCenter)
        lw.setSpacing(16)

        lock_icon = QLabel("🔐")
        lock_icon.setFont(QFont("Segoe UI Emoji", 52))
        lock_icon.setAlignment(Qt.AlignCenter)
        lw.addWidget(lock_icon)

        lock_title = QLabel("Notebook Locked")
        lock_title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        lock_title.setAlignment(Qt.AlignCenter)
        lock_title.setStyleSheet("color:#00BFA5;")
        lw.addWidget(lock_title)

        lock_sub = QLabel("Your notes are encrypted.\nEnter your master password to unlock.")
        lock_sub.setAlignment(Qt.AlignCenter)
        lock_sub.setStyleSheet("color:#888; font-size:13px;")
        lw.addWidget(lock_sub)

        unlock_btn = QPushButton("🔓  Unlock Notebook")
        unlock_btn.setFixedWidth(220)
        unlock_btn.setFixedHeight(40)
        unlock_btn.clicked.connect(self._prompt_master_password)
        lw.addWidget(unlock_btn, alignment=Qt.AlignCenter)

        root.addWidget(self.locked_widget)

        # ── Content (shown when unlocked) ─────────────────────────────────────
        self.content_widget = QWidget()
        cw = QVBoxLayout(self.content_widget)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 14, 24, 14)

        title = QLabel("📓  Notebook")
        title.setStyleSheet("font-size:20px; font-weight:bold;")
        h.addWidget(title)
        h.addStretch()

        self._lock_btn = QPushButton("🔒 Lock")
        self._lock_btn.setFixedHeight(32)
        self._lock_btn.setObjectName("btn_secondary")
        self._lock_btn.clicked.connect(self._lock)
        h.addWidget(self._lock_btn)

        for lbl, slot in [
            ("➕ Category", self._add_category),
            ("➕ Person",   self._add_person),
            ("➕ Note",     self._add_note),
        ]:
            b = QPushButton(lbl)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            h.addWidget(b)

        del_btn = QPushButton("🗑 Delete")
        del_btn.setObjectName("btn_secondary")
        del_btn.setFixedHeight(32)
        del_btn.clicked.connect(self._delete_selected)
        h.addWidget(del_btn)

        cw.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background:#3E3E3E; }")

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setStyleSheet("""
            QTreeWidget { background:#252525; border:none; font-size:14px; padding:8px; }
            QTreeWidget::item { padding:5px 8px; border-radius:5px; }
            QTreeWidget::item:selected { background:#00BFA5; color:#000; }
            QTreeWidget::item:hover:!selected { background:#2D2D2D; }
        """)
        self.tree.currentItemChanged.connect(self._on_select)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        splitter.addWidget(self.tree)

        right = QWidget()
        right.setStyleSheet("background:#1A1A1A;")
        r = QVBoxLayout(right)
        r.setContentsMargins(20, 20, 20, 20)
        r.setSpacing(12)

        self._editor_label = QLabel("Select or create a note")
        self._editor_label.setStyleSheet("font-size:14px; color:#888;")
        r.addWidget(self._editor_label)

        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet("font-size:12px; color:#555;")
        r.addWidget(self._meta_label)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Note content (encrypted on save)…")
        self._editor.setStyleSheet("""
            QTextEdit {
                background:#252525; border:1px solid #3E3E3E; border-radius:8px;
                padding:12px; font-size:14px; color:#E0E0E0;
            }
        """)
        self._editor.setEnabled(False)
        r.addWidget(self._editor, 1)

        self._save_btn = QPushButton("💾  Save & Encrypt")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_note)
        r.addWidget(self._save_btn)

        # ── Image strip ───────────────────────────────────────────────────────
        self._img_scroll = QScrollArea()
        self._img_scroll.setWidgetResizable(True)
        self._img_scroll.setMaximumHeight(210)
        self._img_scroll.setMinimumHeight(210)
        self._img_scroll.setStyleSheet(
            "QScrollArea { background:#111; border:1px solid #2A2A2A; border-radius:6px; }")
        self._img_scroll.hide()
        self._img_container = QWidget()
        self._img_container.setStyleSheet("background:#111;")
        self._img_row = QHBoxLayout(self._img_container)
        self._img_row.setContentsMargins(6, 6, 6, 6)
        self._img_row.setSpacing(6)
        self._img_row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._img_scroll.setWidget(self._img_container)
        r.addWidget(self._img_scroll)

        self._img_btn = QPushButton("🖼️  Attach Image")
        self._img_btn.setObjectName("btn_secondary")
        self._img_btn.setEnabled(False)
        self._img_btn.clicked.connect(self._attach_image)
        r.addWidget(self._img_btn)

        splitter.addWidget(right)
        splitter.setSizes([280, 700])
        cw.addWidget(splitter, 1)

        root.addWidget(self.content_widget)
        self.content_widget.hide()   # start locked

    def _prompt_master_password(self):
        user = auth_manager.current_user
        if not user:
            return
        dlg = MasterPasswordDialog(self)
        if dlg.exec() != QDialog.Accepted or not dlg.password():
            return
        self._svc = NotebookService(user["id"], dlg.password())
        self.locked_widget.hide()
        self.content_widget.show()
        self._refresh_tree()

    def _lock(self):
        self._svc = None
        self._current = None
        self._editor.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._img_btn.setEnabled(False)
        self._editor.clear()
        self._editor_label.setText("Select or create a note")
        self._editor_label.setStyleSheet("font-size:14px; color:#888;")
        self._meta_label.setText("")
        self._img_scroll.hide()
        self.tree.clear()
        self.content_widget.hide()
        self.locked_widget.show()

    def _require_svc(self):
        if self._svc:
            return True
        self._prompt_master_password()
        return self._svc is not None

    def _refresh_tree(self):
        if not self._svc:
            return
        self.tree.blockSignals(True)
        self.tree.clear()
        for cat in self._svc.get_categories():
            c_item = QTreeWidgetItem(["📁  " + cat["name"]])
            c_item.setData(0, Qt.UserRole, {"type": "cat", "id": cat["id"], "name": cat["name"]})
            c_item.setFont(0, QFont("", 13, QFont.Bold))
            for person in self._svc.get_people(cat["id"]):
                p_item = QTreeWidgetItem(["👤  " + person["name"]])
                p_item.setData(0, Qt.UserRole, {
                    "type": "person", "id": person["id"],
                    "name": person["name"], "cat_id": cat["id"]
                })
                for note in self._svc.get_notes(person["id"]):
                    preview = note["content"][:45].replace("\n", " ")
                    if len(note["content"]) > 45:
                        preview += "…"
                    n_item = QTreeWidgetItem(["📝  " + (preview or "(empty)")])
                    n_item.setData(0, Qt.UserRole, {
                        "type": "note", "id": note["id"],
                        "content": note["content"],
                        "created_at": note["created_at"],
                        "updated_at": note["updated_at"],
                        "person_id": person["id"],
                        "person_name": person["name"],
                        "cat_name": cat["name"],
                    })
                    p_item.addChild(n_item)
                c_item.addChild(p_item)
            self.tree.addTopLevelItem(c_item)
            c_item.setExpanded(True)
            for i in range(c_item.childCount()):
                c_item.child(i).setExpanded(True)
        self.tree.blockSignals(False)

    def _on_select(self, current, _prev):
        if not current:
            return
        d = current.data(0, Qt.UserRole)
        if not d:
            return
        if d["type"] == "note":
            self._current = d
            self._editor.blockSignals(True)
            self._editor.setPlainText(d["content"])
            self._editor.blockSignals(False)
            self._editor.setEnabled(True)
            self._save_btn.setEnabled(True)
            self._img_btn.setEnabled(True)
            self._editor_label.setText("📝  " + d["cat_name"] + " / " + d["person_name"])
            self._editor_label.setStyleSheet("font-size:14px; color:#00BFA5;")
            self._meta_label.setText(
                "Created: " + str(d["created_at"]) +
                "   |   Updated: " + str(d["updated_at"]) +
                "   |   🔐 Encrypted"
            )
            self._render_images()
        else:
            self._current = None
            self._editor.setEnabled(False)
            self._save_btn.setEnabled(False)
            self._img_btn.setEnabled(False)
            self._editor.blockSignals(True)
            self._editor.clear()
            self._editor.blockSignals(False)
            self._editor_label.setText(("📁  " if d["type"] == "cat" else "👤  ") + d["name"])
            self._editor_label.setStyleSheet("font-size:14px; color:#888;")
            self._meta_label.setText("")
            self._img_scroll.hide()

    def _add_category(self):
        if not self._require_svc():
            return
        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if ok and name.strip():
            try:
                self._svc.add_category(name.strip())
                self._refresh_tree()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _add_person(self):
        if not self._require_svc():
            return
        cats = self._svc.get_categories()
        if not cats:
            QMessageBox.information(self, "No Category", "Create a category first.")
            return
        d = self._selected_data()
        cat_id = None
        if d:
            if d["type"] == "cat":
                cat_id = d["id"]
            elif d["type"] == "person":
                cat_id = d.get("cat_id")
            elif d["type"] == "note":
                item = self.tree.currentItem()
                if item and item.parent() and item.parent().parent():
                    gpd = item.parent().parent().data(0, Qt.UserRole)
                    if gpd:
                        cat_id = gpd["id"]
        if cat_id is None:
            cat_names = [c["name"] for c in cats]
            choice, ok = QInputDialog.getItem(self, "Select Category", "Add to:", cat_names, 0, False)
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
        if not self._require_svc():
            return
        d = self._selected_data()
        person_id = None
        if d:
            if d["type"] == "person":
                person_id = d["id"]
            elif d["type"] == "note":
                person_id = d["person_id"]
        if person_id is None:
            QMessageBox.information(self, "Select Person", "Select a person to attach the note to.")
            return
        note_id = self._svc.add_note(person_id, "")
        self._refresh_tree()
        self._select_note_by_id(note_id)

    def _save_note(self):
        if not self._current or not self._svc:
            return
        self._svc.update_note(self._current["id"], self._editor.toPlainText())
        self._refresh_tree()
        self._select_note_by_id(self._current["id"])

    def _delete_selected(self):
        if not self._require_svc():
            return
        d = self._selected_data()
        if not d:
            return
        if d["type"] == "cat":
            if QMessageBox.question(self, "Delete", "Delete category '" + d["name"] + "' and ALL data?") != QMessageBox.Yes:
                return
            self._svc.delete_category(d["id"])
        elif d["type"] == "person":
            if QMessageBox.question(self, "Delete", "Delete person '" + d["name"] + "' and all notes?") != QMessageBox.Yes:
                return
            self._svc.delete_person(d["id"])
        elif d["type"] == "note":
            if QMessageBox.question(self, "Delete", "Delete this note?") != QMessageBox.Yes:
                return
            self._svc.delete_note(d["id"])
        self._current = None
        self._editor.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._img_btn.setEnabled(False)
        self._editor.clear()
        self._editor_label.setText("Select or create a note")
        self._editor_label.setStyleSheet("font-size:14px; color:#888;")
        self._meta_label.setText("")
        self._img_scroll.hide()
        self._refresh_tree()

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        d = item.data(0, Qt.UserRole)
        if not d:
            return
        menu = QMenu(self)
        if d["type"] == "cat":
            menu.addAction("➕ Add Person", self._add_person)
        elif d["type"] == "person":
            menu.addAction("➕ Add Note", self._add_note)
        menu.addSeparator()
        menu.addAction("🗑 Delete", self._delete_selected)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _selected_data(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _render_images(self):
        while self._img_row.count():
            w = self._img_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not self._current or not self._svc:
            self._img_scroll.hide()
            return
        images = self._svc.get_images(self._current["id"])
        if not images:
            self._img_scroll.hide()
            return
        self._img_scroll.show()
        for img in images:
            pix = QPixmap()
            try:
                pix.loadFromData(base64.b64decode(img["data_b64"]))
            except Exception:
                pass
            if pix.isNull():
                err = QLabel("⚠️")
                err.setStyleSheet("color:#888; padding:8px;")
                self._img_row.addWidget(err)
                continue
            thumb = ImageThumb(pix, img["id"], img["filename"],
                               on_delete=self._delete_image)
            self._img_row.addWidget(thumb)

    def _attach_image(self):
        if not self._current or not self._svc:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        filename  = os.path.basename(path)
        ext       = path.rsplit(".", 1)[-1].lower()
        with open(path, "rb") as f:
            raw_bytes = f.read()
        self._svc.add_image(self._current["id"], filename, f"image/{ext}", raw_bytes)
        self._render_images()
        self._refresh_tree()

    def _delete_image(self, image_id: int):
        if self._svc:
            self._svc.delete_image(image_id)
        self._render_images()
        self._refresh_tree()

    def _select_note_by_id(self, note_id):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            c = root.child(i)
            for j in range(c.childCount()):
                p = c.child(j)
                for k in range(p.childCount()):
                    n = p.child(k)
                    d = n.data(0, Qt.UserRole)
                    if d and d["type"] == "note" and d["id"] == note_id:
                        self.tree.setCurrentItem(n)
                        return