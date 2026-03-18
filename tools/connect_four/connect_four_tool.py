"""Connect Four — PvP or PvAI (minimax). Drop discs, 4-in-a-row wins."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "connect_four"
ROWS, COLS = 6, 7
CELL = 70
W = COLS * CELL
H = ROWS * CELL + CELL  # extra row for hover indicator


def _check_win(board, piece):
    # Horizontal
    for r in range(ROWS):
        for c in range(COLS - 3):
            if all(board[r][c + i] == piece for i in range(4)):
                return True
    # Vertical
    for c in range(COLS):
        for r in range(ROWS - 3):
            if all(board[r + i][c] == piece for i in range(4)):
                return True
    # Diagonal /
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            if all(board[r - i][c + i] == piece for i in range(4)):
                return True
    # Diagonal \
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            if all(board[r + i][c + i] == piece for i in range(4)):
                return True
    return False


def _valid_cols(board):
    return [c for c in range(COLS) if board[0][c] == 0]


def _drop(board, col, piece):
    b = [row[:] for row in board]
    for r in range(ROWS - 1, -1, -1):
        if b[r][col] == 0:
            b[r][col] = piece
            return b, r
    return b, -1


def _score_window(window, piece):
    opp = 3 - piece
    s = 0
    if window.count(piece) == 4: s += 100
    elif window.count(piece) == 3 and window.count(0) == 1: s += 5
    elif window.count(piece) == 2 and window.count(0) == 2: s += 2
    if window.count(opp) == 3 and window.count(0) == 1: s -= 4
    return s


def _heuristic(board, piece):
    score = 0
    # Centre column preference
    centre = [board[r][COLS // 2] for r in range(ROWS)]
    score += centre.count(piece) * 3
    # Horizontal
    for r in range(ROWS):
        row = board[r]
        for c in range(COLS - 3):
            score += _score_window(row[c:c + 4], piece)
    # Vertical
    for c in range(COLS):
        col = [board[r][c] for r in range(ROWS)]
        for r in range(ROWS - 3):
            score += _score_window(col[r:r + 4], piece)
    return score


def _minimax(board, depth, alpha, beta, maximising):
    valid = _valid_cols(board)
    if _check_win(board, 2): return None, 100000
    if _check_win(board, 1): return None, -100000
    if not valid or depth == 0:
        return None, _heuristic(board, 2)
    if maximising:
        best_score = -10 ** 9
        best_col = random.choice(valid)
        for col in valid:
            nb, _ = _drop(board, col, 2)
            _, score = _minimax(nb, depth - 1, alpha, beta, False)
            if score > best_score:
                best_score = score
                best_col = col
            alpha = max(alpha, best_score)
            if alpha >= beta:
                break
        return best_col, best_score
    else:
        best_score = 10 ** 9
        best_col = random.choice(valid)
        for col in valid:
            nb, _ = _drop(board, col, 1)
            _, score = _minimax(nb, depth - 1, alpha, beta, True)
            if score < best_score:
                best_score = score
                best_col = col
            beta = min(beta, best_score)
            if alpha >= beta:
                break
        return best_col, best_score


class BoardCanvas(QWidget):
    def __init__(self, on_col_click, parent=None):
        super().__init__(parent)
        self.setFixedSize(W, H)
        self._on_col_click = on_col_click
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.hover_col = -1
        self.win_cells = []
        self.setMouseTracking(True)

    def mouseMoveEvent(self, e):
        col = int(e.position().x()) // CELL
        self.hover_col = min(max(col, 0), COLS - 1)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            col = int(e.position().x()) // CELL
            self._on_col_click(col)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, W, H, QColor("#0A1628"))

        # Hover indicator
        if 0 <= self.hover_col < COLS:
            p.setBrush(QColor(255, 80, 80, 120))
            p.setPen(Qt.NoPen)
            cx = self.hover_col * CELL + CELL // 2
            p.drawEllipse(cx - 24, CELL // 2 - 24, 48, 48)

        # Board
        p.setBrush(QColor("#1A3A6B"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, CELL, W, ROWS * CELL, 8, 8)

        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL + CELL // 2
                cy = (r + 1) * CELL + CELL // 2
                v = self.board[r][c]
                if (r, c) in self.win_cells:
                    p.setBrush(QColor("#FFD700"))
                elif v == 1:
                    p.setBrush(QColor("#F44336"))
                elif v == 2:
                    p.setBrush(QColor("#FFEB3B"))
                else:
                    p.setBrush(QColor("#050C1C"))
                p.drawEllipse(cx - 26, cy - 26, 52, 52)

        p.end()


class ConnectFourTool(QWidget):
    name = "Connect Four"
    description = "Drop discs — connect 4 in a row to win"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._build_ui()
        self._new_game()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 10, 20, 10)
        t = QLabel("🔴 Connect Four")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("Mod:"))
        self._mode = QComboBox()
        self._mode.addItems(["Oyuncu vs Oyuncu", "Oyuncu vs AI"])
        hl.addWidget(self._mode)
        new_btn = QPushButton("🆕 Yeni Oyun")
        new_btn.clicked.connect(self._new_game)
        hl.addWidget(new_btn)
        root.addWidget(hdr)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(20)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        self._status = QLabel("🔴 Kırmızı'nın sırası")
        self._status.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("color:#FF9800;")
        ll.addWidget(self._status)
        self._canvas = BoardCanvas(self._on_col_click)
        ll.addWidget(self._canvas)
        body_lay.addWidget(left)

        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb)

        root.addWidget(body, 1)

    def _new_game(self):
        self._board = [[0] * COLS for _ in range(ROWS)]
        self._turn = 1     # 1=red(human), 2=yellow(human or AI)
        self._over = False
        self._canvas.board = self._board
        self._canvas.win_cells = []
        self._canvas.update()
        self._status.setText("🔴 Kırmızı'nın sırası")
        self._status.setStyleSheet("color:#F44336;")

    def _on_col_click(self, col):
        if self._over:
            return
        if self._mode.currentIndex() == 1 and self._turn == 2:
            return   # AI's turn
        self._play(col, self._turn)
        if not self._over and self._mode.currentIndex() == 1 and self._turn == 2:
            QTimer.singleShot(300, self._ai_move)

    def _play(self, col, piece):
        valid = _valid_cols(self._board)
        if col not in valid:
            return
        self._board, row = _drop(self._board, col, piece)
        self._canvas.board = self._board
        self._canvas.update()
        if _check_win(self._board, piece):
            self._mark_win(piece)
        elif not _valid_cols(self._board):
            self._over = True
            self._status.setText("🤝 Beraberlik!")
            self._status.setStyleSheet("color:#888;")
        else:
            self._turn = 3 - piece
            icon = "🔴" if self._turn == 1 else "🟡"
            label = "Kırmızı" if self._turn == 1 else "Sarı"
            self._status.setText(f"{icon} {label}'nın sırası")
            self._status.setStyleSheet(f"color:{'#F44336' if self._turn==1 else '#FFEB3B'};")

    def _ai_move(self):
        if self._over:
            return
        col, _ = _minimax(self._board, 4, -10 ** 9, 10 ** 9, True)
        if col is not None:
            self._play(col, 2)

    def _mark_win(self, piece):
        self._over = True
        # Find winning cells
        cells = []
        for r in range(ROWS):
            for c in range(COLS - 3):
                if all(self._board[r][c + i] == piece for i in range(4)):
                    cells += [(r, c + i) for i in range(4)]
        for r in range(ROWS - 3):
            for c in range(COLS):
                if all(self._board[r + i][c] == piece for i in range(4)):
                    cells += [(r + i, c) for i in range(4)]
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                if all(self._board[r - i][c + i] == piece for i in range(4)):
                    cells += [(r - i, c + i) for i in range(4)]
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                if all(self._board[r + i][c + i] == piece for i in range(4)):
                    cells += [(r + i, c + i) for i in range(4)]
        self._canvas.win_cells = cells
        self._canvas.update()
        label = "🔴 Kırmızı Kazandı!" if piece == 1 else "🟡 Sarı Kazandı!"
        self._status.setText(label)
        self._status.setStyleSheet("color:#4CAF50;")
        user = self._user
        if user and piece == 1:
            post_score(GAME, user["id"], user["username"], 100)
            self._sb.refresh()
