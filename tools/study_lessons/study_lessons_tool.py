"""Study Lessons Tool — lessons with resources (text/image/file), completion tracking."""

import base64
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QFileDialog,
    QInputDialog, QMessageBox, QSplitter, QFrame, QScrollArea,
    QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import LessonsService


class StudyLessonsTool(QWidget):
    name = "Lessons"
    description = "Organize lessons with resources and completion tracking"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = LessonsService(user) if user else None
        self._current_lesson = None
        self._build_ui()
        if self._svc:
            self._refresh_lessons()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📚 Lessons")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        add_btn = QPushButton("➕ New Lesson")
        add_btn.clicked.connect(self._add_lesson)
        hl.addWidget(add_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_lesson)
        hl.addWidget(del_btn)
        root.addWidget(hdr)

        splitter = QSplitter(Qt.Horizontal)

        # Left: lesson list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(6)
        ll.addWidget(QLabel("Lessons:"))
        self.lesson_list = QListWidget()
        self.lesson_list.setMinimumWidth(220)
        self.lesson_list.currentItemChanged.connect(self._on_lesson_select)
        ll.addWidget(self.lesson_list, 1)
        splitter.addWidget(left)

        # Right: lesson detail
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(10)

        self.lesson_title_lbl = QLabel("Select a lesson")
        self.lesson_title_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.lesson_title_lbl.setStyleSheet("color:#00BFA5;")
        rl.addWidget(self.lesson_title_lbl)

        self.completed_check = QCheckBox("Mark as Completed")
        self.completed_check.stateChanged.connect(self._toggle_completed)
        rl.addWidget(self.completed_check)

        # Tabs: Text | Images | Files
        self.tabs = QTabWidget()

        # Text tab
        text_tab = QWidget()
        ttl = QVBoxLayout(text_tab)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Add text notes for this lesson…")
        ttl.addWidget(self.text_edit, 1)
        save_text_btn = QPushButton("💾 Save Text Resource")
        save_text_btn.clicked.connect(self._save_text_resource)
        ttl.addWidget(save_text_btn)

        self.text_resources = QListWidget()
        self.text_resources.setMaximumHeight(160)
        self.text_resources.itemDoubleClicked.connect(self._view_text_resource)
        ttl.addWidget(QLabel("Saved notes:"))
        ttl.addWidget(self.text_resources)
        del_res_btn = QPushButton("🗑️ Delete Selected Note")
        del_res_btn.setObjectName("secondary")
        del_res_btn.clicked.connect(lambda: self._delete_resource(self.text_resources))
        ttl.addWidget(del_res_btn)
        self.tabs.addTab(text_tab, "📝 Text Notes")

        # Images tab
        img_tab = QWidget()
        itl = QVBoxLayout(img_tab)
        upload_img_btn = QPushButton("📁 Upload Image")
        upload_img_btn.clicked.connect(self._upload_image)
        itl.addWidget(upload_img_btn)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.addStretch()
        self.image_scroll.setWidget(self.image_container)
        itl.addWidget(self.image_scroll, 1)
        self.tabs.addTab(img_tab, "🖼️ Images")

        # Files tab
        file_tab = QWidget()
        ftl = QVBoxLayout(file_tab)
        upload_file_btn = QPushButton("📎 Attach File")
        upload_file_btn.clicked.connect(self._upload_file)
        ftl.addWidget(upload_file_btn)
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self._export_file)
        ftl.addWidget(self.file_list, 1)
        del_file_btn = QPushButton("🗑️ Delete Selected File")
        del_file_btn.setObjectName("secondary")
        del_file_btn.clicked.connect(lambda: self._delete_resource(self.file_list))
        ftl.addWidget(del_file_btn)
        self.tabs.addTab(file_tab, "📎 Files")

        rl.addWidget(self.tabs, 1)
        splitter.addWidget(right)
        splitter.setSizes([240, 760])
        root.addWidget(splitter, 1)

    # ── lessons ────────────────────────────────────────────────────────────────
    def _refresh_lessons(self):
        self.lesson_list.clear()
        for les in self._svc.get_lessons():
            icon = "✅" if les["completed"] else "📖"
            item = QListWidgetItem(f"{icon}  {les['name']}")
            item.setData(Qt.UserRole, les)
            self.lesson_list.addItem(item)

    def _on_lesson_select(self, current, _):
        if not current:
            return
        d = current.data(Qt.UserRole)
        self._current_lesson = d
        self.lesson_title_lbl.setText(d["name"])
        self.completed_check.blockSignals(True)
        self.completed_check.setChecked(bool(d["completed"]))
        self.completed_check.blockSignals(False)
        self._refresh_resources()

    def _add_lesson(self):
        name, ok = QInputDialog.getText(self, "New Lesson", "Lesson name:")
        if ok and name.strip():
            self._svc.add_lesson(name.strip())
            self._refresh_lessons()

    def _delete_lesson(self):
        if not self._current_lesson:
            return
        if QMessageBox.question(self, "Delete", f"Delete lesson '{self._current_lesson['name']}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_lesson(self._current_lesson["id"])
        self._current_lesson = None
        self.lesson_title_lbl.setText("Select a lesson")
        self._refresh_lessons()

    def _toggle_completed(self, state):
        if not self._current_lesson:
            return
        self._svc.set_completed(self._current_lesson["id"], state == Qt.Checked)
        self._refresh_lessons()

    # ── resources ──────────────────────────────────────────────────────────────
    def _refresh_resources(self):
        if not self._current_lesson:
            return
        resources = self._svc.get_resources(self._current_lesson["id"])

        # text
        self.text_resources.clear()
        for r in resources:
            if r["resource_type"] == "text":
                preview = r["content"][:60].replace("\n", " ")
                item = QListWidgetItem(f"📝 {preview}")
                item.setData(Qt.UserRole, r)
                self.text_resources.addItem(item)

        # images
        while self.image_layout.count() > 1:
            w = self.image_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        for r in resources:
            if r["resource_type"] == "image" and r["content"]:
                self._add_image_widget(r)

        # files
        self.file_list.clear()
        for r in resources:
            if r["resource_type"] == "file":
                item = QListWidgetItem(f"📎 {r['content'][:80]}")
                item.setData(Qt.UserRole, r)
                self.file_list.addItem(item)

    def _save_text_resource(self):
        if not self._current_lesson:
            QMessageBox.information(self, "No Lesson", "Select a lesson first.")
            return
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        self._svc.add_resource(self._current_lesson["id"], "text", text)
        self.text_edit.clear()
        self._refresh_resources()

    def _view_text_resource(self, item):
        d = item.data(Qt.UserRole)
        QMessageBox.information(self, "Note", d["content"])

    def _upload_image(self):
        if not self._current_lesson:
            QMessageBox.information(self, "No Lesson", "Select a lesson first.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = path.rsplit(".", 1)[-1].lower()
        data_uri = f"data:image/{ext};base64,{b64}"
        self._svc.add_resource(self._current_lesson["id"], "image", data_uri)
        self._refresh_resources()

    def _add_image_widget(self, r):
        frame = QFrame()
        frame.setStyleSheet("background:#252525; border-radius:8px; padding:4px;")
        fl = QVBoxLayout(frame)
        lbl = QLabel()
        try:
            data = r["content"].split(",", 1)[1] if "," in r["content"] else r["content"]
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(data))
            lbl.setPixmap(pix.scaledToWidth(400, Qt.SmoothTransformation))
        except Exception:
            lbl.setText("[Image could not be loaded]")
        fl.addWidget(lbl)
        del_btn = QPushButton("🗑️ Remove")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(lambda: self._del_resource_direct(r["id"], frame))
        fl.addWidget(del_btn)
        idx = self.image_layout.count() - 1
        self.image_layout.insertWidget(idx, frame)

    def _del_resource_direct(self, res_id, widget):
        self._svc.delete_resource(res_id)
        widget.deleteLater()

    def _upload_file(self):
        if not self._current_lesson:
            QMessageBox.information(self, "No Lesson", "Select a lesson first.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Attach File")
        if not path:
            return
        import os
        filename = os.path.basename(path)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content = f"FILENAME:{filename}||DATA:{b64}"
        self._svc.add_resource(self._current_lesson["id"], "file", content)
        self._refresh_resources()

    def _export_file(self, item):
        d = item.data(Qt.UserRole)
        content = d["content"]
        if not content.startswith("FILENAME:"):
            return
        parts = content.split("||DATA:", 1)
        filename = parts[0].replace("FILENAME:", "")
        b64data = parts[1] if len(parts) > 1 else ""
        save_path, _ = QFileDialog.getSaveFileName(self, "Export File", filename)
        if save_path:
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64data))
            QMessageBox.information(self, "Saved", f"File saved to {save_path}")

    def _delete_resource(self, list_widget):
        item = list_widget.currentItem()
        if not item:
            return
        d = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", "Delete this resource?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._svc.delete_resource(d["id"])
            self._refresh_resources()
