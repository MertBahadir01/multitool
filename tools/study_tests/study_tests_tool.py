"""Test Tool — custom tests with questions, photo uploads (Base64), solutions."""

import base64
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QFileDialog,
    QInputDialog, QMessageBox, QSplitter, QFrame, QScrollArea,
    QLineEdit, QDialog, QDialogButtonBox, QFormLayout, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import TestService


class StudyTestsTool(QWidget):
    name = "Test Capture"
    description = "Capture difficult questions with photos and solution notes"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = TestService(user) if user else None
        self._current_test = None
        self._current_q = None
        self._q_img_b64 = ""
        self._s_img_b64 = ""
        self._build_ui()
        if self._svc:
            self._refresh_tests()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📝 Test Capture")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        new_test_btn = QPushButton("➕ New Test")
        new_test_btn.clicked.connect(self._add_test)
        hl.addWidget(new_test_btn)
        del_test_btn = QPushButton("🗑️ Delete Test")
        del_test_btn.setObjectName("secondary")
        del_test_btn.clicked.connect(self._delete_test)
        hl.addWidget(del_test_btn)
        root.addWidget(hdr)

        splitter = QSplitter(Qt.Horizontal)

        # Left: test list + question list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(6)
        ll.addWidget(QLabel("Tests:"))
        self.test_list = QListWidget()
        self.test_list.setMaximumHeight(160)
        self.test_list.currentItemChanged.connect(self._on_test_select)
        ll.addWidget(self.test_list)

        q_hdr = QHBoxLayout()
        q_hdr.addWidget(QLabel("Questions:"))
        q_hdr.addStretch()
        add_q_btn = QPushButton("➕")
        add_q_btn.setFixedWidth(30)
        add_q_btn.clicked.connect(self._add_question)
        q_hdr.addWidget(add_q_btn)
        ll.addLayout(q_hdr)

        self.q_list = QListWidget()
        self.q_list.currentItemChanged.connect(self._on_q_select)
        ll.addWidget(self.q_list, 1)

        del_q_btn = QPushButton("🗑️ Delete Question")
        del_q_btn.setObjectName("secondary")
        del_q_btn.clicked.connect(self._delete_question)
        ll.addWidget(del_q_btn)
        splitter.addWidget(left)

        # Right: question editor
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(10)

        self.q_title_lbl = QLabel("Select a question")
        self.q_title_lbl.setStyleSheet("color:#00BFA5; font-size:14px; font-weight:bold;")
        rl.addWidget(self.q_title_lbl)

        tabs = QTabWidget()

        # Question tab
        q_tab = QWidget()
        qtl = QVBoxLayout(q_tab)
        qtl.addWidget(QLabel("Question text:"))
        self.q_text = QTextEdit()
        self.q_text.setPlaceholderText("Describe the question…")
        self.q_text.setMaximumHeight(120)
        qtl.addWidget(self.q_text)

        qtl.addWidget(QLabel("Question image:"))
        q_img_row = QHBoxLayout()
        self.q_img_lbl = QLabel("No image")
        self.q_img_lbl.setStyleSheet("color:#888;")
        q_img_row.addWidget(self.q_img_lbl, 1)
        q_upload_btn = QPushButton("📁 Upload")
        q_upload_btn.clicked.connect(self._upload_q_image)
        q_img_row.addWidget(q_upload_btn)
        q_clear_btn = QPushButton("✖")
        q_clear_btn.setFixedWidth(30)
        q_clear_btn.clicked.connect(self._clear_q_image)
        q_img_row.addWidget(q_clear_btn)
        qtl.addLayout(q_img_row)
        self.q_img_preview = QLabel()
        self.q_img_preview.setAlignment(Qt.AlignLeft)
        qtl.addWidget(self.q_img_preview)
        qtl.addStretch()
        tabs.addTab(q_tab, "❓ Question")

        # Solution tab
        s_tab = QWidget()
        stl = QVBoxLayout(s_tab)
        stl.addWidget(QLabel("Solution notes:"))
        self.s_text = QTextEdit()
        self.s_text.setPlaceholderText("Write the solution explanation…")
        self.s_text.setMaximumHeight(120)
        stl.addWidget(self.s_text)

        stl.addWidget(QLabel("Solution image:"))
        s_img_row = QHBoxLayout()
        self.s_img_lbl = QLabel("No image")
        self.s_img_lbl.setStyleSheet("color:#888;")
        s_img_row.addWidget(self.s_img_lbl, 1)
        s_upload_btn = QPushButton("📁 Upload")
        s_upload_btn.clicked.connect(self._upload_s_image)
        s_img_row.addWidget(s_upload_btn)
        s_clear_btn = QPushButton("✖")
        s_clear_btn.setFixedWidth(30)
        s_clear_btn.clicked.connect(self._clear_s_image)
        s_img_row.addWidget(s_clear_btn)
        stl.addLayout(s_img_row)
        self.s_img_preview = QLabel()
        self.s_img_preview.setAlignment(Qt.AlignLeft)
        stl.addWidget(self.s_img_preview)
        stl.addStretch()
        tabs.addTab(s_tab, "✅ Solution")

        rl.addWidget(tabs, 1)

        save_btn = QPushButton("💾 Save Question")
        save_btn.clicked.connect(self._save_question)
        rl.addWidget(save_btn)

        splitter.addWidget(right)
        splitter.setSizes([260, 740])
        root.addWidget(splitter, 1)

    # ── tests ──────────────────────────────────────────────────────────────────
    def _refresh_tests(self):
        self.test_list.clear()
        for t in self._svc.get_tests():
            item = QListWidgetItem(f"📝 {t['title']} ({t['subject'] or 'General'})")
            item.setData(Qt.UserRole, t)
            self.test_list.addItem(item)

    def _on_test_select(self, current, _):
        if not current:
            return
        self._current_test = current.data(Qt.UserRole)
        self._refresh_questions()

    def _add_test(self):
        title, ok = QInputDialog.getText(self, "New Test", "Test title:")
        if not ok or not title.strip():
            return
        subj, ok2 = QInputDialog.getText(self, "Subject", "Subject (optional):")
        self._svc.add_test(title.strip(), subj.strip() if ok2 else "")
        self._refresh_tests()

    def _delete_test(self):
        if not self._current_test:
            return
        if QMessageBox.question(self, "Delete", f"Delete test '{self._current_test['title']}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_test(self._current_test["id"])
        self._current_test = None
        self.q_list.clear()
        self._refresh_tests()

    # ── questions ──────────────────────────────────────────────────────────────
    def _refresh_questions(self):
        self.q_list.clear()
        if not self._current_test:
            return
        for i, q in enumerate(self._svc.get_questions(self._current_test["id"])):
            preview = q["question_text"][:40] or "(no text)"
            item = QListWidgetItem(f"Q{i+1}: {preview}")
            item.setData(Qt.UserRole, q)
            self.q_list.addItem(item)

    def _on_q_select(self, current, _):
        if not current:
            return
        q = current.data(Qt.UserRole)
        self._current_q = q
        self._q_img_b64 = q.get("question_image", "")
        self._s_img_b64 = q.get("solution_image", "")
        self.q_text.setPlainText(q.get("question_text", ""))
        self.s_text.setPlainText(q.get("solution_text", ""))
        self._show_image_preview(self.q_img_preview, self.q_img_lbl, self._q_img_b64)
        self._show_image_preview(self.s_img_preview, self.s_img_lbl, self._s_img_b64)
        self.q_title_lbl.setText(f"Question {self.q_list.currentRow() + 1}")

    def _add_question(self):
        if not self._current_test:
            QMessageBox.information(self, "No Test", "Select a test first.")
            return
        existing = self._svc.get_questions(self._current_test["id"])
        pos = len(existing) + 1
        q_id = self._svc.add_question(self._current_test["id"], pos)
        self._refresh_questions()
        # select last
        self.q_list.setCurrentRow(self.q_list.count() - 1)

    def _save_question(self):
        if not self._current_q:
            QMessageBox.information(self, "No Question", "Select a question first.")
            return
        self._svc.update_question(
            self._current_q["id"],
            self.q_text.toPlainText().strip(),
            self.s_text.toPlainText().strip(),
            self._q_img_b64,
            self._s_img_b64,
        )
        q_id = self._current_q["id"]
        self._refresh_questions()
        # re-select
        for i in range(self.q_list.count()):
            item = self.q_list.item(i)
            if item.data(Qt.UserRole)["id"] == q_id:
                self.q_list.setCurrentItem(item)
                break

    def _delete_question(self):
        item = self.q_list.currentItem()
        if not item:
            return
        q = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", "Delete this question?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_question(q["id"])
        self._current_q = None
        self._refresh_questions()

    # ── image helpers ──────────────────────────────────────────────────────────
    def _upload_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return ""
        ext = path.rsplit(".", 1)[-1].lower()
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/{ext};base64,{b64}"

    def _upload_q_image(self):
        data = self._upload_image()
        if data:
            self._q_img_b64 = data
            self._show_image_preview(self.q_img_preview, self.q_img_lbl, data)

    def _upload_s_image(self):
        data = self._upload_image()
        if data:
            self._s_img_b64 = data
            self._show_image_preview(self.s_img_preview, self.s_img_lbl, data)

    def _clear_q_image(self):
        self._q_img_b64 = ""
        self.q_img_preview.clear()
        self.q_img_lbl.setText("No image")

    def _clear_s_image(self):
        self._s_img_b64 = ""
        self.s_img_preview.clear()
        self.s_img_lbl.setText("No image")

    def _show_image_preview(self, lbl: QLabel, status_lbl: QLabel, data: str):
        if not data:
            lbl.clear()
            status_lbl.setText("No image")
            return
        try:
            raw = data.split(",", 1)[1] if "," in data else data
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(raw))
            lbl.setPixmap(pix.scaledToWidth(300, Qt.SmoothTransformation))
            status_lbl.setText("✅ Image loaded")
            status_lbl.setStyleSheet("color:#00BFA5;")
        except Exception:
            status_lbl.setText("❌ Image error")
