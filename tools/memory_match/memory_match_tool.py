"""Memory Match — card-flipping memory game with move counter, timer, leaderboard."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QComboBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "memory_match"

EMOJIS = [
    "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼",
    "🐨","🐯","🦁","🐸","🐵","🦄","🐔","🐧",
    "🐦","🦆","🦅","🦉","🦇","🐺","🐗","🐴",
    "🦋","🐛","🐝","🐞","🦗","🦂",
]

SIZES = {"4×4": (4, 4), "4×5": (4, 5), "6×6": (6, 6)}


class CardBtn(QPushButton):
    def __init__(self, emoji, parent=None):
        super().__init__(parent)
        self._emoji = emoji
        self.matched = False
        self.setFixedSize(64, 64)
        self._hide()

    def _hide(self):
        self.setText("❓")
        self.setStyleSheet("background:#252525;border:2px solid #3A3A3A;border-radius:8px;font-size:22px;")

    def show_face(self):
        self.setText(self._emoji)
        self.setStyleSheet("background:#1A3A35;border:2px solid #00BFA5;border-radius:8px;font-size:22px;")

    def mark_matched(self):
        self.matched = True
        self.setStyleSheet("background:#0D2E2A;border:2px solid #4CAF50;border-radius:8px;font-size:22px;")
        self.setEnabled(False)

    def reset(self):
        if not self.matched:
            self._hide()


class MemoryMatchTool(QWidget):
    name = "Memory Match"
    description = "Card flip memory game"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._first = None
        self._second = None
        self._moves = 0
        self._secs = 0
        self._pairs = 0
        self._total_pairs = 0
        self._locked = False
        self._running = False
        self._build_ui()
        self._new_game()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 10, 20, 10)
        t = QLabel("🃏 Memory Match")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("Boyut:"))
        self._size_cb = QComboBox()
        self._size_cb.addItems(list(SIZES.keys()))
        hl.addWidget(self._size_cb)
        new_btn = QPushButton("🆕 Yeni Oyun")
        new_btn.clicked.connect(self._new_game)
        hl.addWidget(new_btn)
        root.addWidget(hdr)

        # Body
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(20)

        # Left: stats + grid
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        info = QWidget()
        info_lay = QHBoxLayout(info)
        info_lay.setContentsMargins(0, 0, 0, 0)
        self._move_lbl = QLabel("Hamle: 0")
        self._move_lbl.setStyleSheet("color:#FF9800;font-size:13px;font-weight:bold;")
        info_lay.addWidget(self._move_lbl)
        info_lay.addStretch()
        self._time_lbl = QLabel("⏱ 00:00")
        self._time_lbl.setStyleSheet("color:#888;font-size:13px;")
        info_lay.addWidget(self._time_lbl)
        left_lay.addWidget(info)

        self._status = QLabel("Kart seçin ve eşleştirin!")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color:#888;font-size:13px;")
        left_lay.addWidget(self._status)

        grid_frame = QFrame()
        grid_frame.setStyleSheet("background:#1A1A1A;border-radius:8px;")
        gfl = QVBoxLayout(grid_frame)
        gfl.setContentsMargins(12, 12, 12, 12)
        self._grid = QGridLayout()
        self._grid.setSpacing(6)
        gfl.addLayout(self._grid)
        left_lay.addWidget(grid_frame)
        left_lay.addStretch()
        body_lay.addWidget(left, 3)

        # Right: scoreboard
        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb, 1)

        root.addWidget(body, 1)

        # Timers
        self._flip_timer = QTimer(self)
        self._flip_timer.setSingleShot(True)
        self._flip_timer.timeout.connect(self._hide_flipped)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)

    def _new_game(self):
        self._tick_timer.stop()
        self._moves = 0
        self._secs = 0
        self._pairs = 0
        self._first = None
        self._second = None
        self._locked = False
        self._running = True

        rows, cols = SIZES[self._size_cb.currentText()]
        total = rows * cols
        emojis = EMOJIS[:total // 2] * 2
        random.shuffle(emojis)

        # Clear old cards
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._cards = []
        for i, e in enumerate(emojis):
            btn = CardBtn(e)
            btn.clicked.connect(lambda checked, b=btn: self._flip(b))
            self._grid.addWidget(btn, i // cols, i % cols)
            self._cards.append(btn)

        self._total_pairs = total // 2
        self._move_lbl.setText("Hamle: 0")
        self._time_lbl.setText("⏱ 00:00")
        self._status.setText("Kart seçin ve eşleştirin!")
        self._status.setStyleSheet("color:#888;font-size:13px;")
        self._sb.refresh()
        self._tick_timer.start(1000)

    def _flip(self, btn):
        if self._locked or btn.matched or btn is self._first:
            return
        btn.show_face()
        if self._first is None:
            self._first = btn
        else:
            self._second = btn
            self._moves += 1
            self._move_lbl.setText(f"Hamle: {self._moves}")
            if self._first._emoji == self._second._emoji:
                self._first.mark_matched()
                self._second.mark_matched()
                self._first = None
                self._second = None
                self._pairs += 1
                if self._pairs == self._total_pairs:
                    self._on_win()
            else:
                self._locked = True
                self._flip_timer.start(800)

    def _hide_flipped(self):
        if self._first:
            self._first.reset()
        if self._second:
            self._second.reset()
        self._first = None
        self._second = None
        self._locked = False

    def _on_win(self):
        self._running = False
        self._tick_timer.stop()
        score = max(1, 10000 - self._moves * 100 - self._secs * 10)
        self._status.setText(
            f"🎉 Tebrikler! {self._moves} hamle, {self._secs}s — Skor: {score}")
        self._status.setStyleSheet("color:#4CAF50;font-size:13px;")
        if self._user:
            post_score(GAME, self._user["id"], self._user["username"], score)
            self._sb.refresh()

    def _tick(self):
        if not self._running:
            return
        self._secs += 1
        m, s = divmod(self._secs, 60)
        self._time_lbl.setText(f"⏱ {m:02d}:{s:02d}")