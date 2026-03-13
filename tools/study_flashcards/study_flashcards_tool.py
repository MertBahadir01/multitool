"""Flashcards Tool — decks, cards, spaced repetition review."""

import base64
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit,
    QDialog, QDialogButtonBox, QFormLayout, QFileDialog,
    QInputDialog, QMessageBox, QSplitter, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import FlashcardService


class CardDialog(QDialog):
    def __init__(self, parent=None, card=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Card" if card else "New Card")
        self.setFixedWidth(460)
        self._img_b64 = card.get("image_b64", "") if card else ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        form = QFormLayout()
        self.front_edit = QTextEdit()
        self.front_edit.setMaximumHeight(80)
        self.front_edit.setPlaceholderText("Question / term…")
        if card:
            self.front_edit.setPlainText(card.get("front", ""))
        form.addRow("Front:", self.front_edit)
        self.back_edit = QTextEdit()
        self.back_edit.setMaximumHeight(80)
        self.back_edit.setPlaceholderText("Answer / definition…")
        if card:
            self.back_edit.setPlainText(card.get("back", ""))
        form.addRow("Back:", self.back_edit)
        layout.addLayout(form)
        img_row = QHBoxLayout()
        self.img_status = QLabel("No image" if not self._img_b64 else "✅ Image loaded")
        self.img_status.setStyleSheet("color:#888;")
        img_row.addWidget(self.img_status, 1)
        up_btn = QPushButton("📁 Image")
        up_btn.clicked.connect(self._upload_image)
        img_row.addWidget(up_btn)
        clr_btn = QPushButton("✖")
        clr_btn.setFixedWidth(30)
        clr_btn.clicked.connect(self._clear_image)
        img_row.addWidget(clr_btn)
        layout.addLayout(img_row)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _upload_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        ext = path.rsplit(".", 1)[-1].lower()
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        self._img_b64 = f"data:image/{ext};base64,{b64}"
        self.img_status.setText("✅ Image loaded")
        self.img_status.setStyleSheet("color:#00BFA5;")

    def _clear_image(self):
        self._img_b64 = ""
        self.img_status.setText("No image")
        self.img_status.setStyleSheet("color:#888;")

    def get_data(self):
        return {
            "front": self.front_edit.toPlainText().strip(),
            "back": self.back_edit.toPlainText().strip(),
            "image_b64": self._img_b64,
        }


class StudyFlashcardsTool(QWidget):
    name = "Flashcards"
    description = "Digital flashcards with spaced repetition"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = FlashcardService(user) if user else None
        self._current_deck = None
        self._review_cards = []
        self._review_idx = 0
        self._showing_front = True
        self._build_ui()
        if self._svc:
            self._refresh_decks()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("🃏 Flashcards")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        new_deck_btn = QPushButton("➕ New Deck")
        new_deck_btn.clicked.connect(self._add_deck)
        hl.addWidget(new_deck_btn)
        del_deck_btn = QPushButton("🗑️ Delete Deck")
        del_deck_btn.setObjectName("secondary")
        del_deck_btn.clicked.connect(self._delete_deck)
        hl.addWidget(del_deck_btn)
        root.addWidget(hdr)

        self.stack = QStackedWidget()

        # ── Page 0: Deck + card management ────────────────────────────────────
        manage_page = QWidget()
        ml = QVBoxLayout(manage_page)
        ml.setContentsMargins(16, 16, 16, 16)
        ml.setSpacing(10)
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Decks:"))
        self.deck_list = QListWidget()
        self.deck_list.setMinimumWidth(200)
        self.deck_list.currentItemChanged.connect(self._on_deck_select)
        ll.addWidget(self.deck_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 0, 0, 0)
        card_hdr = QHBoxLayout()
        self.deck_title = QLabel("Select a deck")
        self.deck_title.setStyleSheet("color:#00BFA5; font-weight:bold; font-size:14px;")
        card_hdr.addWidget(self.deck_title)
        card_hdr.addStretch()
        add_card_btn = QPushButton("➕ Add Card")
        add_card_btn.clicked.connect(self._add_card)
        card_hdr.addWidget(add_card_btn)
        review_btn = QPushButton("▶ Start Review")
        review_btn.clicked.connect(self._start_review)
        card_hdr.addWidget(review_btn)
        rl.addLayout(card_hdr)
        self.card_list = QListWidget()
        self.card_list.itemDoubleClicked.connect(self._edit_card)
        rl.addWidget(self.card_list, 1)
        card_btns = QHBoxLayout()
        del_card_btn = QPushButton("🗑️ Delete Card")
        del_card_btn.setObjectName("secondary")
        del_card_btn.clicked.connect(self._delete_card)
        card_btns.addWidget(del_card_btn)
        card_btns.addStretch()
        rl.addLayout(card_btns)
        splitter.addWidget(right)
        splitter.setSizes([220, 780])
        ml.addWidget(splitter, 1)
        self.stack.addWidget(manage_page)

        # ── Page 1: Review mode ────────────────────────────────────────────────
        review_page = QWidget()
        rv = QVBoxLayout(review_page)
        rv.setContentsMargins(40, 30, 40, 30)
        rv.setSpacing(16)

        rv_hdr = QHBoxLayout()
        self.review_progress = QLabel("")
        self.review_progress.setStyleSheet("color:#888; font-size:13px;")
        rv_hdr.addWidget(self.review_progress)
        rv_hdr.addStretch()
        exit_btn = QPushButton("✖ Exit Review")
        exit_btn.setObjectName("secondary")
        exit_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        rv_hdr.addWidget(exit_btn)
        rv.addLayout(rv_hdr)

        # card face
        self.card_face = QFrame()
        self.card_face.setStyleSheet("""
            QFrame {
                background:#252525; border:2px solid #3E3E3E;
                border-radius:16px; min-height:200px;
            }
        """)
        self.card_face.setCursor(Qt.PointingHandCursor)
        self.card_face.mousePressEvent = lambda e: self._flip_card()
        cfl = QVBoxLayout(self.card_face)
        cfl.setAlignment(Qt.AlignCenter)
        self.card_side_lbl = QLabel("FRONT")
        self.card_side_lbl.setStyleSheet("color:#555; font-size:11px;")
        self.card_side_lbl.setAlignment(Qt.AlignCenter)
        cfl.addWidget(self.card_side_lbl)
        self.card_text_lbl = QLabel("")
        self.card_text_lbl.setAlignment(Qt.AlignCenter)
        self.card_text_lbl.setWordWrap(True)
        self.card_text_lbl.setFont(QFont("Segoe UI", 16))
        self.card_text_lbl.setStyleSheet("color:#E0E0E0;")
        cfl.addWidget(self.card_text_lbl)
        self.card_img_lbl = QLabel()
        self.card_img_lbl.setAlignment(Qt.AlignCenter)
        cfl.addWidget(self.card_img_lbl)
        tap_hint = QLabel("(tap to flip)")
        tap_hint.setAlignment(Qt.AlignCenter)
        tap_hint.setStyleSheet("color:#444; font-size:11px;")
        cfl.addWidget(tap_hint)
        rv.addWidget(self.card_face, 1)

        # ease buttons (shown after flip)
        self.ease_frame = QFrame()
        self.ease_frame.setStyleSheet("background:transparent;")
        el = QHBoxLayout(self.ease_frame)
        el.setSpacing(12)
        for label, ease, color in [
            ("😓 Again", 1, "#F44336"),
            ("😕 Hard",  2, "#FF9800"),
            ("🙂 Good",  3, "#2196F3"),
            ("😄 Easy",  4, "#4CAF50"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(44)
            b.setStyleSheet(f"QPushButton{{background:{color};color:#fff;border-radius:8px;font-size:14px;border:none;}}"
                            f"QPushButton:hover{{opacity:0.8;}}")
            b.clicked.connect(lambda _, e=ease: self._rate_card(e))
            el.addWidget(b)
        self.ease_frame.hide()
        rv.addWidget(self.ease_frame)
        self.stack.addWidget(review_page)

        root.addWidget(self.stack, 1)

    # ── decks ──────────────────────────────────────────────────────────────────
    def _refresh_decks(self):
        self.deck_list.clear()
        for d in self._svc.get_decks():
            item = QListWidgetItem(f"🗂️ {d['name']} ({d['subject'] or 'General'})")
            item.setData(Qt.UserRole, d)
            self.deck_list.addItem(item)

    def _on_deck_select(self, current, _):
        if not current:
            return
        self._current_deck = current.data(Qt.UserRole)
        self.deck_title.setText(self._current_deck["name"])
        self._refresh_cards()

    def _add_deck(self):
        name, ok = QInputDialog.getText(self, "New Deck", "Deck name:")
        if not ok or not name.strip():
            return
        subj, ok2 = QInputDialog.getText(self, "Subject", "Subject (optional):")
        self._svc.add_deck(name.strip(), subj.strip() if ok2 else "")
        self._refresh_decks()

    def _delete_deck(self):
        if not self._current_deck:
            return
        if QMessageBox.question(self, "Delete", f"Delete deck '{self._current_deck['name']}'?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.delete_deck(self._current_deck["id"])
        self._current_deck = None
        self.card_list.clear()
        self._refresh_decks()

    # ── cards ──────────────────────────────────────────────────────────────────
    def _refresh_cards(self):
        self.card_list.clear()
        if not self._current_deck:
            return
        for card in self._svc.get_cards(self._current_deck["id"]):
            preview = card["front"][:50]
            item = QListWidgetItem(f"🃏 {preview}")
            item.setData(Qt.UserRole, card)
            self.card_list.addItem(item)

    def _add_card(self):
        if not self._current_deck:
            QMessageBox.information(self, "No Deck", "Select a deck first.")
            return
        dlg = CardDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        if not d["front"] and not d["back"]:
            return
        self._svc.add_card(self._current_deck["id"], d["front"], d["back"], d["image_b64"])
        self._refresh_cards()

    def _edit_card(self, item):
        card = item.data(Qt.UserRole)
        dlg = CardDialog(self, card)
        if dlg.exec() != QDialog.Accepted:
            return
        # delete and re-add (simplest update)
        d = dlg.get_data()
        self._svc.delete_card(card["id"])
        self._svc.add_card(self._current_deck["id"], d["front"], d["back"], d["image_b64"])
        self._refresh_cards()

    def _delete_card(self):
        item = self.card_list.currentItem()
        if not item:
            return
        card = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", "Delete this card?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._svc.delete_card(card["id"])
            self._refresh_cards()

    # ── review ─────────────────────────────────────────────────────────────────
    def _start_review(self):
        if not self._current_deck:
            return
        self._review_cards = self._svc.get_cards(self._current_deck["id"])
        if not self._review_cards:
            QMessageBox.information(self, "Empty Deck", "Add cards before reviewing.")
            return
        self._review_idx = 0
        self._showing_front = True
        self.stack.setCurrentIndex(1)
        self._show_current_card()

    def _show_current_card(self):
        if self._review_idx >= len(self._review_cards):
            QMessageBox.information(self, "Done!", "Review session complete! 🎉")
            self.stack.setCurrentIndex(0)
            return
        card = self._review_cards[self._review_idx]
        self._showing_front = True
        self.ease_frame.hide()
        self.card_side_lbl.setText("FRONT")
        self.card_side_lbl.setStyleSheet("color:#00BFA5; font-size:11px;")
        self.card_text_lbl.setText(card["front"])
        self.card_img_lbl.clear()
        if card.get("image_b64") and self._showing_front:
            self._set_card_image(card["image_b64"])
        self.review_progress.setText(f"Card {self._review_idx + 1} / {len(self._review_cards)}")

    def _flip_card(self):
        if self._review_idx >= len(self._review_cards):
            return
        card = self._review_cards[self._review_idx]
        if self._showing_front:
            self._showing_front = False
            self.card_side_lbl.setText("BACK")
            self.card_side_lbl.setStyleSheet("color:#FF9800; font-size:11px;")
            self.card_text_lbl.setText(card["back"])
            self.card_img_lbl.clear()
            self.ease_frame.show()
        else:
            self._showing_front = True
            self.card_side_lbl.setText("FRONT")
            self.card_side_lbl.setStyleSheet("color:#00BFA5; font-size:11px;")
            self.card_text_lbl.setText(card["front"])
            self.card_img_lbl.clear()
            self.ease_frame.hide()

    def _rate_card(self, ease: int):
        if self._review_idx >= len(self._review_cards):
            return
        card = self._review_cards[self._review_idx]
        self._svc.update_review(card["id"], ease)
        self._review_idx += 1
        self._show_current_card()

    def _set_card_image(self, b64: str):
        try:
            raw = b64.split(",", 1)[1] if "," in b64 else b64
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(raw))
            self.card_img_lbl.setPixmap(pix.scaledToWidth(280, Qt.SmoothTransformation))
        except Exception:
            pass
