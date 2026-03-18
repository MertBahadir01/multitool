"""Block Blast — place Tetris-like pieces on a 9×9 grid, clear full rows/cols.
Canvas is fully responsive: fills available space on any screen size."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME    = "block_blast"
SZ      = 9
PALETTE = ["#F44336","#E91E63","#9C27B0","#3F51B5","#2196F3",
           "#00BCD4","#4CAF50","#FF9800","#FF5722"]

SHAPES = [
    [[1]],
    [[1,1]],[[1],[1]],
    [[1,1,1]],[[1],[1],[1]],
    [[1,1,1],[0,1,0]],
    [[1,1],[1,0]],[[1,1],[0,1]],
    [[0,1],[1,1]],[[1,0],[1,1]],
    [[1,1,1,1]],[[1],[1],[1],[1]],
    [[1,1],[1,1]],
    [[1,1,1],[1,0,0]],[[1,1,1],[0,0,1]],
    [[1,0,0],[1,1,1]],[[0,0,1],[1,1,1]],
]


class Piece:
    def __init__(self):
        self.shape = random.choice(SHAPES)
        self.color = random.choice(PALETTE)

    @property
    def rows(self): return len(self.shape)
    @property
    def cols(self): return len(self.shape[0])


# ── Canvas ────────────────────────────────────────────────────────────────────
class BlockBlastCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(280, 280)
        self._hover_piece = None
        self._hover_gr = None
        self._hover_gc = None
        self._reset()

    def _reset(self):
        self.grid  = [[None] * SZ for _ in range(SZ)]
        self.score = 0
        self.alive = True

    # ── helpers: cell size & offset computed from current widget size ─────────
    def _cs(self):
        return min((self.width() - 20) // SZ, (self.height() - 20) // SZ)

    def _off_x(self):
        return (self.width()  - SZ * self._cs()) // 2

    def _off_y(self):
        return (self.height() - SZ * self._cs()) // 2

    # ── game logic ────────────────────────────────────────────────────────────
    def can_place(self, piece, gr, gc):
        for r, row in enumerate(piece.shape):
            for c, v in enumerate(row):
                if v:
                    nr, nc = gr + r, gc + c
                    if nr < 0 or nr >= SZ or nc < 0 or nc >= SZ:
                        return False
                    if self.grid[nr][nc]:
                        return False
        return True

    def place(self, piece, gr, gc):
        for r, row in enumerate(piece.shape):
            for c, v in enumerate(row):
                if v:
                    self.grid[gr + r][gc + c] = piece.color
        pts = 0
        rows_clear = [r for r in range(SZ) if all(self.grid[r][c] for c in range(SZ))]
        cols_clear = [c for c in range(SZ) if all(self.grid[r][c] for r in range(SZ))]
        for r in rows_clear:
            self.grid[r] = [None] * SZ
            pts += SZ
        for c in cols_clear:
            for r in range(SZ):
                self.grid[r][c] = None
            pts += SZ
        if rows_clear and cols_clear:
            pts *= 2
        self.score += pts + piece.rows * piece.cols

    # ── painting ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        W, H  = self.width(), self.height()
        cs    = self._cs()
        ox    = self._off_x()
        oy    = self._off_y()

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, W, H, QColor("#0D0D0D"))

        # Grid cells
        for r in range(SZ):
            for c in range(SZ):
                x = ox + c * cs
                y = oy + r * cs
                color = QColor(self.grid[r][c]) if self.grid[r][c] else QColor("#1A1A1A")
                p.setBrush(color)
                p.setPen(QColor("#222"))
                p.drawRoundedRect(x + 1, y + 1, cs - 2, cs - 2, 4, 4)

        # Hover preview
        if (self._hover_piece is not None and
                self._hover_gr is not None and
                self._hover_gc is not None):
            ok  = self.can_place(self._hover_piece, self._hover_gr, self._hover_gc)
            for r, row in enumerate(self._hover_piece.shape):
                for c, v in enumerate(row):
                    if v:
                        x = ox + (self._hover_gc + c) * cs
                        y = oy + (self._hover_gr + r) * cs
                        col = QColor(self._hover_piece.color)
                        col.setAlpha(150 if ok else 50)
                        p.setBrush(col)
                        p.setPen(Qt.NoPen)
                        p.drawRoundedRect(x + 1, y + 1, cs - 2, cs - 2, 4, 4)

        # Game over overlay
        if not self.alive:
            p.fillRect(0, 0, W, H, QColor(0, 0, 0, 170))
            p.setPen(QColor("#F44336"))
            p.setFont(QFont("Segoe UI", 22, QFont.Bold))
            p.drawText(0, 0, W, H, Qt.AlignCenter, "GAME OVER")

        p.end()


# ── Piece preview thumbnail (draggable) ───────────────────────────────────────
class PiecePreview(QWidget):
    CELL = 36

    def __init__(self, piece, on_start, on_move, on_drop, parent=None):
        super().__init__(parent)
        self.piece    = piece
        self._on_start = on_start
        self._on_move  = on_move
        self._on_drop  = on_drop
        cs = self.CELL
        self.setFixedSize(piece.cols * cs + 6, piece.rows * cs + 6)

    def paintEvent(self, _):
        cs = self.CELL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, self.width(), self.height(), QColor("#141414"))
        for r, row in enumerate(self.piece.shape):
            for c, v in enumerate(row):
                if v:
                    p.setBrush(QColor(self.piece.color))
                    p.setPen(QColor("#222"))
                    p.drawRoundedRect(c * cs + 2, r * cs + 2, cs - 3, cs - 3, 4, 4)
        p.end()

    def mousePressEvent(self, e):
        self._on_start(self.piece, e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        self._on_move(self.piece, e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        self._on_drop(self.piece, e.globalPosition().toPoint())


# ── Main tool ─────────────────────────────────────────────────────────────────
class BlockBlastTool(QWidget):
    name        = "Block Blast"
    description = "Place blocks, clear rows and columns"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user   = auth_manager.current_user
        self._pieces = []
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
        t = QLabel("💥 Block Blast")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        self._score_lbl = QLabel("Skor: 0")
        self._score_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self._score_lbl.setStyleSheet("color:#FF9800;")
        hl.addWidget(self._score_lbl)
        new_btn = QPushButton("🆕 Yeni Oyun")
        new_btn.clicked.connect(self._new_game)
        hl.addWidget(new_btn)
        root.addWidget(hdr)

        # Body
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(16, 16, 16, 16)
        body_lay.setSpacing(16)

        # Left: canvas + pieces
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(10)

        self._canvas = BlockBlastCanvas()
        left_lay.addWidget(self._canvas, 1)   # stretch=1 → fills all available height

        # Piece tray
        tray_lbl = QLabel("Parçaları sürükle ve bırak:")
        tray_lbl.setStyleSheet("color:#888; font-size:12px;")
        left_lay.addWidget(tray_lbl)

        self._tray = QWidget()
        self._tray.setStyleSheet("background:#1A1A1A; border-radius:8px;")
        self._tray_lay = QHBoxLayout(self._tray)
        self._tray_lay.setContentsMargins(12, 10, 12, 10)
        self._tray_lay.setSpacing(20)
        self._tray_lay.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self._tray)

        body_lay.addWidget(left, 3)

        # Right: scoreboard
        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb, 1)

        root.addWidget(body, 1)

    def _new_game(self):
        self._canvas._reset()
        self._score_lbl.setText("Skor: 0")
        self._gen_pieces()

    def _gen_pieces(self):
        while self._tray_lay.count():
            item = self._tray_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pieces = [Piece() for _ in range(3)]
        for piece in self._pieces:
            pw = PiecePreview(piece, self._start_drag, self._drag_move, self._drop)
            self._tray_lay.addWidget(pw)

    # ── drag helpers ──────────────────────────────────────────────────────────
    def _canvas_grid_pos(self, global_pos):
        local = self._canvas.mapFromGlobal(global_pos)
        cs = self._canvas._cs()
        ox = self._canvas._off_x()
        oy = self._canvas._off_y()
        gr = (local.y() - oy) // cs
        gc = (local.x() - ox) // cs
        return int(gr), int(gc)

    def _start_drag(self, piece, gpos):
        gr, gc = self._canvas_grid_pos(gpos)
        self._canvas._hover_piece = piece
        self._canvas._hover_gr    = gr
        self._canvas._hover_gc    = gc
        self._canvas.update()

    def _drag_move(self, piece, gpos):
        gr, gc = self._canvas_grid_pos(gpos)
        self._canvas._hover_piece = piece
        self._canvas._hover_gr    = gr
        self._canvas._hover_gc    = gc
        self._canvas.update()

    def _drop(self, piece, gpos):
        gr, gc = self._canvas_grid_pos(gpos)
        self._canvas._hover_piece = None
        self._canvas._hover_gr    = None
        self._canvas._hover_gc    = None

        if self._canvas.can_place(piece, gr, gc):
            self._canvas.place(piece, gr, gc)
            self._score_lbl.setText(f"Skor: {self._canvas.score}")
            self._pieces.remove(piece)

            # Remove the dragged piece's preview widget from tray
            for i in range(self._tray_lay.count()):
                w = self._tray_lay.itemAt(i).widget()
                if w and isinstance(w, PiecePreview) and w.piece is piece:
                    self._tray_lay.takeAt(i)
                    w.deleteLater()
                    break

            if not self._pieces:
                self._gen_pieces()
            else:
                # Check game over
                if not any(
                    self._canvas.can_place(p, r, c)
                    for p in self._pieces
                    for r in range(SZ)
                    for c in range(SZ)
                ):
                    self._canvas.alive = False
                    self._canvas.update()
                    if self._user:
                        post_score(GAME, self._user["id"],
                                   self._user["username"], self._canvas.score)
                        self._sb.refresh()

        self._canvas.update()