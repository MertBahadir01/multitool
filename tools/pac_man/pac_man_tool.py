"""Pac-Man — maze, dots, ghosts, power pellets, lives, scoreboard."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "pac_man"
CELL = 20
COLS, ROWS = 21, 21

# 0=path, 1=wall, 2=dot, 3=power pellet
MAZE = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,2,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,2,1],
    [1,3,1,1,2,1,1,1,2,1,1,1,2,1,1,1,2,1,1,3,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,2,1,2,1,1,1,1,1,1,1,2,1,2,1,1,2,1],
    [1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1],
    [1,1,1,1,2,1,1,1,0,0,0,0,0,1,1,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,0,0,1,1,1,0,0,0,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,1,1,0,0,0,1,1,0,1,2,1,1,1,1],
    [0,0,0,0,2,0,0,1,0,0,0,0,0,1,0,0,2,0,0,0,0],
    [1,1,1,1,2,1,0,1,1,1,1,1,1,1,0,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,0,0,0,0,0,0,0,0,1,2,1,1,1,1],
    [1,1,1,1,2,1,0,1,1,1,1,1,1,1,0,1,2,1,1,1,1],
    [1,2,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,2,1],
    [1,2,1,1,2,1,1,1,2,1,1,1,2,1,1,1,2,1,1,2,1],
    [1,3,2,1,2,2,2,2,2,2,0,2,2,2,2,2,2,1,2,3,1],
    [1,1,2,1,2,1,2,1,1,1,1,1,1,1,2,1,2,1,2,1,1],
    [1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1,2,2,2,2,1],
    [1,2,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,1,1,2,1],
    [1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]

W = COLS * CELL
H = ROWS * CELL
GHOST_COLORS = ["#F44336", "#FF69B4", "#00BCD4", "#FF9800"]

# Ghost spawn positions — must be on open (non-wall) cells
GHOST_SPAWNS = [(9, 9), (10, 9), (11, 9), (10, 10)]


class PacManTool(QWidget):
    name = "Pac-Man"
    description = "Eat dots, avoid ghosts, clear the maze"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._score_posted = False
        self._build_ui()
        self._new_game()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 10, 20, 10)
        t = QLabel("👻 Pac-Man")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#FFD700;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("← → ↑ ↓ hareket", styleSheet="color:#555;font-size:11px;"))
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
        self._canvas = _PacCanvas(self)
        ll.addWidget(self._canvas)
        body_lay.addWidget(left)

        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb)

        root.addWidget(body, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFocusPolicy(Qt.StrongFocus)

    def _new_game(self):
        self._canvas._reset()
        self._score_posted = False
        self._timer.start(150)
        self.setFocus()

    def _tick(self):
        c = self._canvas
        c.step()
        if not c.alive and not self._score_posted:
            self._score_posted = True
            if self._user and c.score > 0:
                post_score(GAME, self._user["id"], self._user["username"], c.score)
                self._sb.refresh()

    def keyPressEvent(self, e: QKeyEvent):
        d = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
             Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if e.key() in d:
            self._canvas.next_dir = d[e.key()]


class _Ghost:
    def __init__(self, x, y, color):
        # x/y are integer cell coords — ghosts always snap to grid
        self.x = x
        self.y = y
        self.color = color
        self.dx = random.choice([-1, 1])
        self.dy = 0
        self.frightened = False
        self.frighten_ticks = 0


class _PacCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(W, H)
        self._reset()

    def _reset(self):
        import copy
        self.maze = copy.deepcopy(MAZE)
        self.score = 0
        self.lives = 3
        self.alive = True
        # pac position in cell units (integers)
        self.px = 10
        self.py = 15
        self.dx = 0
        self.dy = 0
        self.next_dir = (0, 0)
        self.mouth_open = True
        self.mouth_tick = 0
        self._ghosts = [
            _Ghost(sx, sy, GHOST_COLORS[i])
            for i, (sx, sy) in enumerate(GHOST_SPAWNS)
        ]
        self._total_dots = sum(
            1 for r in range(ROWS) for c in range(COLS) if MAZE[r][c] in (2, 3)
        )

    def _can_move(self, x, y):
        """Check if cell (x, y) is walkable. x=col, y=row."""
        c, r = int(x), int(y)
        if 0 <= r < ROWS and 0 <= c < COLS:
            return self.maze[r][c] != 1
        # Out of bounds = tunnel (only for x axis)
        return True

    def step(self):
        if not self.alive:
            return

        # --- Pac-Man movement (one full cell per tick) ---
        nx, ny = self.next_dir
        # Try to switch to buffered direction
        if (nx != 0 or ny != 0) and self._can_move(self.px + nx, self.py + ny):
            self.dx, self.dy = nx, ny

        new_px = self.px + self.dx
        new_py = self.py + self.dy
        if self._can_move(new_px, new_py):
            self.px = new_px
            self.py = new_py

        # Tunnel wrap
        if self.px < 0:
            self.px = COLS - 1
        elif self.px >= COLS:
            self.px = 0

        # Eat dot — pac is always at integer cell
        r, c = self.py, self.px
        if 0 <= r < ROWS and 0 <= c < COLS:
            cell = self.maze[r][c]
            if cell == 2:
                self.maze[r][c] = 0
                self.score += 10
            elif cell == 3:
                self.maze[r][c] = 0
                self.score += 50
                for g in self._ghosts:
                    g.frightened = True
                    g.frighten_ticks = 40

        # Mouth animation
        self.mouth_tick += 1
        if self.mouth_tick >= 3:
            self.mouth_tick = 0
            self.mouth_open = not self.mouth_open

        # --- Ghost movement (one full cell per tick, decide at each cell) ---
        for g in self._ghosts:
            if g.frightened:
                g.frighten_ticks -= 1
                if g.frighten_ticks <= 0:
                    g.frightened = False

            # Build list of valid moves (no reversing unless forced)
            options = []
            for ddx, ddy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nc, nr = g.x + ddx, g.y + ddy
                if 0 <= nr < ROWS and 0 <= nc < COLS and self.maze[nr][nc] != 1:
                    # Don't allow 180-degree reversal unless it's the only option
                    if not (ddx == -g.dx and ddy == -g.dy):
                        options.append((ddx, ddy))

            if not options:
                # Forced reversal
                options = [(-g.dx, -g.dy)]

            if g.frightened:
                g.dx, g.dy = random.choice(options)
            else:
                # 70% chance chase pac, 30% random — choose from valid options
                best = min(options, key=lambda o:
                           (g.x + o[0] - self.px) ** 2 + (g.y + o[1] - self.py) ** 2)
                g.dx, g.dy = best if random.random() < 0.7 else random.choice(options)

            g.x += g.dx
            g.y += g.dy

            # Tunnel wrap for ghosts
            if g.x < 0:
                g.x = COLS - 1
            elif g.x >= COLS:
                g.x = 0

            # Collision
            if g.x == self.px and g.y == self.py:
                if g.frightened:
                    g.x, g.y = GHOST_SPAWNS[self._ghosts.index(g)]
                    g.frightened = False
                    self.score += 200
                else:
                    self.lives -= 1
                    if self.lives <= 0:
                        self.alive = False
                    else:
                        self.px, self.py = 10, 15
                        self.dx = self.dy = 0
                        # Reset ghosts to spawn
                        for i, gh in enumerate(self._ghosts):
                            gh.x, gh.y = GHOST_SPAWNS[i]
                            gh.frightened = False

        # Win condition
        remaining = sum(
            1 for r in range(ROWS) for c in range(COLS) if self.maze[r][c] in (2, 3)
        )
        if remaining == 0:
            self.score += 500
            self.alive = False

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, W, H, QColor("#000010"))

        for r in range(ROWS):
            for c in range(COLS):
                x, y = c * CELL, r * CELL
                v = self.maze[r][c]
                if v == 1:
                    p.setBrush(QColor("#1A1AFF"))
                    p.setPen(QColor("#0000AA"))
                    p.drawRect(x, y, CELL, CELL)
                elif v == 2:
                    p.setBrush(QColor("#FFEB3B"))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(x + CELL // 2 - 3, y + CELL // 2 - 3, 6, 6)
                elif v == 3:
                    p.setBrush(QColor("#FFFFFF"))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(x + CELL // 2 - 6, y + CELL // 2 - 6, 12, 12)

        # Pac-Man — draw centered on his cell
        px = self.px * CELL + CELL // 2
        py = self.py * CELL + CELL // 2
        p.setBrush(QColor("#FFD700"))
        p.setPen(Qt.NoPen)
        if self.mouth_open:
            angles = {(1, 0): 30, (-1, 0): 210, (0, -1): 120, (0, 1): 300}
            start_angle = angles.get((self.dx, self.dy), 30)
            span = 300
            p.drawPie(px - CELL // 2 + 2, py - CELL // 2 + 2, CELL - 4, CELL - 4,
                      start_angle * 16, span * 16)
        else:
            p.drawEllipse(px - CELL // 2 + 2, py - CELL // 2 + 2, CELL - 4, CELL - 4)

        # Ghosts — draw centered on their cell
        for g in self._ghosts:
            gx = g.x * CELL + CELL // 2
            gy = g.y * CELL + CELL // 2
            color = QColor("#2196F3") if g.frightened else QColor(g.color)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(gx - 8, gy - 10, 16, 16)
            p.drawRect(gx - 8, gy - 2, 16, 10)
            p.setBrush(QColor("#FFF"))
            p.drawEllipse(gx - 5, gy - 8, 5, 6)
            p.drawEllipse(gx + 1, gy - 8, 5, 6)
            p.setBrush(QColor("#00F"))
            p.drawEllipse(gx - 4, gy - 7, 3, 4)
            p.drawEllipse(gx + 2, gy - 7, 3, 4)

        # HUD
        p.setPen(QColor("#FFD700"))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(8, H - 6, f"Skor: {self.score}   ❤ {self.lives}")

        if not self.alive:
            p.fillRect(0, 0, W, H, QColor(0, 0, 0, 160))
            p.setPen(QColor("#FFD700"))
            p.setFont(QFont("Segoe UI", 22, QFont.Bold))
            p.drawText(0, H // 2 - 20, W, 40, Qt.AlignCenter, "GAME OVER")
            p.setPen(QColor("#FFF"))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(0, H // 2 + 24, W, 28, Qt.AlignCenter, f"Skor: {self.score}")
        p.end()