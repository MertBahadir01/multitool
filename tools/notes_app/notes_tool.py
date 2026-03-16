"""
Quick Notes — DB-backed, per-user note-taking.
• All data stored in SQLite via NotesService (no QSettings)
• Images stored as BLOBs in note_images table
• Double-click any thumbnail to open full-size in a viewer dialog
• Image strip height = 210px (was 140px, +50%)
• Tags, pinning, search all work as before
"""

import base64
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QFrame, QSplitter, QFileDialog, QInputDialog,
    QMessageBox, QScrollArea, QDialog, QVBoxLayout as QVL
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap, QColor

from core.auth_manager import auth_manager
from tools.notes_app.notes_service import NotesService


# ── Full-size image viewer dialog ─────────────────────────────────────────────
class ImageViewerDialog(QDialog):
    def __init__(self, pixmap: QPixmap, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"🖼️  {filename}")
        self.setMinimumSize(400, 300)
        lay = QVL(self)
        lay.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)

        lbl = QLabel()
        # Scale down only if larger than screen, otherwise show original size
        screen = self.screen().availableGeometry() if self.screen() else None
        max_w = (screen.width()  - 80) if screen else 1200
        max_h = (screen.height() - 120) if screen else 900
        if pixmap.width() > max_w or pixmap.height() > max_h:
            pixmap = pixmap.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignCenter)
        scroll.setWidget(lbl)
        lay.addWidget(scroll, 1)

        close_btn = QPushButton("✕  Kapat")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignRight)

        self.resize(min(pixmap.width() + 40, max_w),
                    min(pixmap.height() + 80, max_h))


# ── Clickable image thumbnail ─────────────────────────────────────────────────
class ImageThumb(QLabel):
    """Thumbnail that opens full-size viewer on double-click and shows delete X on hover."""

    def __init__(self, pixmap: QPixmap, image_id: int, filename: str,
                 on_delete, parent=None):
        super().__init__(parent)
        self._full_pix  = pixmap
        self._image_id  = image_id
        self._filename  = filename
        self._on_delete = on_delete

        self.setPixmap(pixmap.scaledToHeight(180, Qt.SmoothTransformation))
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #3E3E3E;
                border-radius: 6px;
                margin: 4px;
                background: #1A1A1A;
            }
            QLabel:hover {
                border: 1px solid #00BFA5;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"🔍 Double-click to open  |  Right-click to delete\n{filename}")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            dlg = ImageViewerDialog(self._full_pix, self._filename, self)
            dlg.exec()

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        open_act   = menu.addAction("🔍 Tam ekran aç")
        delete_act = menu.addAction("🗑️ Resmi sil")
        action = menu.exec(event.globalPos())
        if action == open_act:
            dlg = ImageViewerDialog(self._full_pix, self._filename, self)
            dlg.exec()
        elif action == delete_act:
            if QMessageBox.question(self, "Sil", "Bu resim silinsin mi?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self._on_delete(self._image_id)


# ── Main Notes Tool ───────────────────────────────────────────────────────────
class NotesApp(QWidget):
    name        = "Quick Notes"
    description = "Fast note-taking with tags, images and search — DB backed"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc           = NotesService(user["id"]) if user else None
        self._notes: list[dict] = []       # rows from DB
        self._current_note_id: int | None = None
        self._dirty         = False
        self._build_ui()
        if self._svc:
            self._refresh_list()

        # auto-save every 30 s
        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._auto_save)
        self._save_timer.start(30_000)

    # ── UI ────────────────────────────────────────────────────────────────────
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

        # Toolbar
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

        # Splitter
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
        self._title_edit.setStyleSheet(
            "background:#252525; border:none; border-bottom:1px solid #3E3E3E;"
            "padding:6px; color:#E0E0E0;")
        self._title_edit.textChanged.connect(self._mark_dirty)
        rl.addWidget(self._title_edit)

        self._tags_lbl = QLabel("")
        self._tags_lbl.setStyleSheet("color:#00BFA5; font-size:11px;")
        rl.addWidget(self._tags_lbl)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Start typing…")
        self._editor.setStyleSheet("""
            QTextEdit {
                background:#1A1A1A; border:none; padding:12px;
                font-size:14px; color:#E0E0E0;
            }
        """)
        self._editor.textChanged.connect(self._mark_dirty)
        rl.addWidget(self._editor, 1)

        # Image strip — 210 px tall (+50% from original 140 px)
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

    # ── List refresh ──────────────────────────────────────────────────────────
    def _refresh_list(self):
        if not self._svc:
            return
        query = self._search.text().strip()
        self._notes = self._svc.get_notes(query)

        self._note_list.clear()
        for n in self._notes:
            pin     = "📌 " if n.get("pinned") else ""
            tags    = n.get("tags", "") or ""
            tag_str = " ".join(f"#{t}" for t in tags.split(",") if t.strip())
            preview = (n.get("body") or "").replace("\n", " ")[:50]
            date    = (n.get("updated_at") or "")[:10]
            has_img = "🖼️ " if self._svc.get_image_count(n["id"]) > 0 else ""
            item = QListWidgetItem()
            item.setText(f"{pin}{has_img}{n.get('title') or '(untitled)'}\n"
                         f"{preview}\n{date}  {tag_str}")
            item.setData(Qt.UserRole, n["id"])
            self._note_list.addItem(item)

        self._count_lbl.setText(f"{len(self._notes)} note(s)")

    # ── Select note ───────────────────────────────────────────────────────────
    def _on_select(self, row):
        if row < 0 or row >= len(self._notes):
            return
        if self._dirty:
            self._save_current()
        n = self._notes[row]
        self._current_note_id = n["id"]

        self._title_edit.blockSignals(True)
        self._editor.blockSignals(True)
        self._title_edit.setText(n.get("title") or "")
        self._editor.setPlainText(n.get("body") or "")
        self._title_edit.blockSignals(False)
        self._editor.blockSignals(False)

        tags    = n.get("tags", "") or ""
        tag_str = " ".join(f"#{t}" for t in tags.split(",") if t.strip())
        self._tags_lbl.setText(tag_str)
        created = (n.get("created_at") or "")[:10]
        updated = (n.get("updated_at") or "")[:10]
        pin_txt = "📌 Pinned  " if n.get("pinned") else ""
        self._meta_lbl.setText(f"{pin_txt}Created: {created}   Updated: {updated}")

        self._render_images()
        self._dirty = False

    # ── Image rendering ───────────────────────────────────────────────────────
    def _render_images(self):
        # Clear existing thumbnails
        while self._img_row.count():
            w = self._img_row.takeAt(0).widget()
            if w:
                w.deleteLater()

        if not self._current_note_id:
            self._img_scroll.hide()
            return

        images = self._svc.get_images(self._current_note_id)
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
                err = QLabel("⚠️ Image")
                err.setStyleSheet("color:#888; padding:8px;")
                self._img_row.addWidget(err)
                continue

            thumb = ImageThumb(
                pix,
                image_id=img["id"],
                filename=img["filename"],
                on_delete=self._delete_image,
            )
            self._img_row.addWidget(thumb)

    def _delete_image(self, image_id: int):
        self._svc.delete_image(image_id)
        self._render_images()

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def _new_note(self):
        if self._dirty:
            self._save_current()
        nid = self._svc.add_note()
        self._refresh_list()
        # Select the newly created note (first after refresh since ordered by updated_at DESC)
        for i, n in enumerate(self._notes):
            if n["id"] == nid:
                self._note_list.setCurrentRow(i)
                break
        self._title_edit.setFocus()

    def _save_current(self):
        if self._current_note_id is None:
            return
        self._svc.update_note(
            self._current_note_id,
            self._title_edit.text().strip(),
            self._editor.toPlainText(),
        )
        self._dirty = False
        self._refresh_list()
        # Re-select current row
        for i, n in enumerate(self._notes):
            if n["id"] == self._current_note_id:
                self._note_list.blockSignals(True)
                self._note_list.setCurrentRow(i)
                self._note_list.blockSignals(False)
                break

    def _auto_save(self):
        if self._dirty:
            self._save_current()

    def _delete_note(self):
        if self._current_note_id is None:
            return
        n = self._svc.get_note(self._current_note_id)
        title = (n.get("title") or "this note") if n else "this note"
        if QMessageBox.question(self, "Delete", f"Delete '{title}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_note(self._current_note_id)
        self._current_note_id = None
        self._dirty = False
        self._title_edit.clear()
        self._editor.clear()
        self._tags_lbl.setText("")
        self._img_scroll.hide()
        self._meta_lbl.setText("")
        self._refresh_list()

    def _toggle_pin(self):
        if self._current_note_id is None:
            QMessageBox.information(self, "No Note", "Select a note first.")
            return
        n = self._svc.get_note(self._current_note_id)
        if n:
            self._svc.set_pinned(self._current_note_id, not bool(n.get("pinned")))
            self._refresh_list()
            # Refresh meta label
            n2 = self._svc.get_note(self._current_note_id)
            if n2:
                pin_txt = "📌 Pinned  " if n2.get("pinned") else ""
                created = (n2.get("created_at") or "")[:10]
                updated = (n2.get("updated_at") or "")[:10]
                self._meta_lbl.setText(f"{pin_txt}Created: {created}   Updated: {updated}")

    def _edit_tags(self):
        if self._current_note_id is None:
            QMessageBox.information(self, "No Note", "Select a note first.")
            return
        n = self._svc.get_note(self._current_note_id)
        current_tags = n.get("tags", "") or "" if n else ""
        text, ok = QInputDialog.getText(
            self, "Edit Tags", "Tags (comma-separated):", text=current_tags)
        if ok:
            tags = [t.strip().lstrip("#") for t in text.split(",") if t.strip()]
            self._svc.set_tags(self._current_note_id, tags)
            self._tags_lbl.setText(" ".join(f"#{t}" for t in tags))
            self._refresh_list()

    def _attach_image(self):
        if self._current_note_id is None:
            QMessageBox.information(self, "No Note", "Select a note first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        import os
        filename  = os.path.basename(path)
        ext       = path.rsplit(".", 1)[-1].lower()
        mime_type = f"image/{ext}"
        with open(path, "rb") as f:
            raw_bytes = f.read()
        self._svc.add_image(self._current_note_id, filename, mime_type, raw_bytes)
        self._render_images()
        self._refresh_list()

    def _mark_dirty(self):
        self._dirty = True