"""Wordle — guess the 5-letter word in 6 tries. Color feedback per letter."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "wordle"

WORDS = [
    "CRANE","SLATE","FLINT","STORM","BRAVE","GRIPE","SHOUT","PLUMB","TRACK","SWIFT",
    "BLAZE","CRIMP","DWARF","EPOCH","FROST","GLOOM","HIPPO","IRONY","JOUST","KNAVE",
    "LEMON","MOURN","NUDGE","OLIVE","PERCH","QUILL","RIDGE","SNOWY","THYME","ULTRA",
    "VAPOR","WHIRL","XEROX","YACHT","ZEBRA","ACUTE","BLINK","CHANT","DRIVE","EMBER",
    "FAINT","GRASP","HAVEN","INFER","JEWEL","KNEEL","LIVER","MIRTH","NERVE","OUGHT",
    "PIXEL","QUALM","REPEL","STING","TROUT","UNIFY","VICAR","WALTZ","EXPEL","YODEL",
    "ZONAL","ABBOT","BLOAT","CLEFT","DEBUT","ETHOS","FLUKE","GRUEL","HEIST","INEPT",
    "JUMBO","KUDOS","LUSTY","MACRO","NICHE","OCTET","PRANK","QUOTA","RIVET","SCONE",
    "TACIT","UNCUT","VIGOR","WOKEN","EXTOL","YEARN","ZIPPY","AGILE","BRAWN","CLOAK",
    "DELTA","ELUDE","FINCH","GLARE","HASTE","IGLOO","JOKER","KEBAB","LATCH","MOCHA",
]

VALID_LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class LetterTile(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self._set_empty()

    def _set_empty(self):
        self.setText("")
        self.setStyleSheet(
            "background:#252525; border:2px solid #3A3A3A;"
            "border-radius:4px; color:#E0E0E0;")

    def set_letter(self, ch):
        self.setText(ch)
        self.setStyleSheet(
            "background:#252525; border:2px solid #00BFA5;"
            "border-radius:4px; color:#E0E0E0;")

    def reveal(self, state):
        # state: 'correct'=green, 'present'=yellow, 'absent'=gray
        colors = {
            "correct": ("#538D4E", "#538D4E"),
            "present": ("#B59F3B", "#B59F3B"),
            "absent":  ("#3A3A3C", "#3A3A3C"),
        }
        bg, bd = colors[state]
        self.setStyleSheet(
            f"background:{bg}; border:2px solid {bd};"
            "border-radius:4px; color:#FFFFFF;")


class KeyboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._btns = {}
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
        for row in rows:
            rl = QHBoxLayout()
            rl.setSpacing(5)
            rl.setAlignment(Qt.AlignCenter)
            for ch in row:
                btn = QPushButton(ch)
                btn.setFixedSize(36, 36)
                btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
                btn.setStyleSheet(
                    "background:#818384; border:none; border-radius:4px; color:#fff;")
                rl.addWidget(btn)
                self._btns[ch] = btn
            lay.addLayout(rl)

    def update_key(self, ch, state):
        if ch not in self._btns:
            return
        colors = {"correct": "#538D4E", "present": "#B59F3B", "absent": "#3A3A3C"}
        # Don't downgrade correct → present/absent
        btn = self._btns[ch]
        cur = btn.styleSheet()
        if "#538D4E" in cur:
            return
        if "#B59F3B" in cur and state == "absent":
            return
        btn.setStyleSheet(
            f"background:{colors[state]}; border:none; border-radius:4px; color:#fff;")

    def reset(self):
        for btn in self._btns.values():
            btn.setStyleSheet(
                "background:#818384; border:none; border-radius:4px; color:#fff;")


class WordleTool(QWidget):
    name = "Wordle"
    description = "Guess the 5-letter word in 6 tries"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._word = ""
        self._row = 0
        self._col = 0
        self._current = []
        self._over = False
        self._build_ui()
        self._new_game()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 10, 20, 10)
        t = QLabel("🟩 Wordle")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet("color:#888; font-size:13px;")
        hl.addWidget(self._status)
        new_btn = QPushButton("🆕 Yeni Oyun")
        new_btn.clicked.connect(self._new_game)
        hl.addWidget(new_btn)
        root.addWidget(hdr)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(24)

        # Centre: grid + keyboard
        centre = QWidget()
        cl = QVBoxLayout(centre)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(16)
        cl.setAlignment(Qt.AlignCenter)

        # 6×5 tile grid
        grid_w = QWidget()
        self._grid = QGridLayout(grid_w)
        self._grid.setSpacing(6)
        self._tiles = []
        for r in range(6):
            row = []
            for c in range(5):
                tile = LetterTile()
                self._grid.addWidget(tile, r, c)
                row.append(tile)
            self._tiles.append(row)
        cl.addWidget(grid_w, 0, Qt.AlignCenter)

        # Keyboard
        self._kb = KeyboardWidget()
        cl.addWidget(self._kb, 0, Qt.AlignCenter)
        body_lay.addWidget(centre, 2)

        # Scoreboard
        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb, 1)

        root.addWidget(body, 1)
        self.setFocusPolicy(Qt.StrongFocus)

    def _new_game(self):
        self._word = random.choice(WORDS)
        self._row = 0
        self._col = 0
        self._current = []
        self._over = False
        for row in self._tiles:
            for tile in row:
                tile._set_empty()
        self._kb.reset()
        self._status.setText(f"Attempt 1/6")
        self.setFocus()

    def keyPressEvent(self, e: QKeyEvent):
        if self._over:
            return
        key = e.key()
        text = e.text().upper()
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            self._submit()
        elif key == Qt.Key_Backspace:
            self._backspace()
        elif text in VALID_LETTERS and len(self._current) < 5:
            self._type_letter(text)

    def _type_letter(self, ch):
        if len(self._current) < 5:
            self._tiles[self._row][self._col].set_letter(ch)
            self._current.append(ch)
            self._col += 1

    def _backspace(self):
        if self._current:
            self._current.pop()
            self._col -= 1
            self._tiles[self._row][self._col]._set_empty()

    def _submit(self):
        if len(self._current) != 5:
            self._status.setText("5 harf girin!")
            return
        guess = "".join(self._current)
        result = self._evaluate(guess, self._word)
        for c, (ch, state) in enumerate(zip(guess, result)):
            self._tiles[self._row][c].reveal(state)
            self._kb.update_key(ch, state)
        if guess == self._word:
            self._over = True
            score = max(1, (7 - self._row) * 100)
            self._status.setText(f"🎉 Doğru! Skor: {score}")
            if self._user:
                post_score(GAME, self._user["id"], self._user["username"], score)
                self._sb.refresh()
        else:
            self._row += 1
            self._col = 0
            self._current = []
            if self._row == 6:
                self._over = True
                self._status.setText(f"❌ Cevap: {self._word}")
            else:
                self._status.setText(f"Attempt {self._row + 1}/6")

    def _evaluate(self, guess, word):
        result = ["absent"] * 5
        word_count = {}
        for i, (g, w) in enumerate(zip(guess, word)):
            if g == w:
                result[i] = "correct"
            else:
                word_count[w] = word_count.get(w, 0) + 1
        for i, (g, w) in enumerate(zip(guess, word)):
            if result[i] != "correct" and g in word_count and word_count[g] > 0:
                result[i] = "present"
                word_count[g] -= 1
        return result
