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
MAZE_TEMPLATE = [
    "#####################",
    "#o..........#........o#",
    "#.##.#####.#.#####.##.#",
    "#.##.#####.#.#####.##.#",
    "#...................#",
    "#.##.#.#######.#.##.#",
    "#....#....#....#....#",
    "######.###.###.######",
    "     #.#       #.#   ",
    "######.# ## ## #.######",
    "      .  #   #  .      ",
    "######.# ##### #.######",
    "     #.#       #.#   ",
    "######.#.#######.#.######",
    "#............#............#",
    "#.##.#####.#.#####.##.#",
    "#o##.......#.......##o#",
    "###.#.#######.#.###",
    "#......#....#......#",
    "#.##########.##########.#",
    "#####################",
]

# Simpler clean maze
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
        d = {Qt.Key_Left: (-1,0), Qt.Key_Right: (1,0),
             Qt.Key_Up: (0,-1), Qt.Key_Down: (0,1)}
        if e.key() in d:
            self._canvas.next_dir = d[e.key()]


class _Ghost:
    def __init__(self, x, y, color):
        self.x = float(x)
        self.y = float(y)
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
        self.px = 10.0
        self.py = 15.0
        self.dx = 0
        self.dy = 0
        self.next_dir = (0, 0)
        self.mouth_open = True
        self.mouth_tick = 0
        self._ghosts = [
            _Ghost(9, 9, GHOST_COLORS[0]),
            _Ghost(10, 9, GHOST_COLORS[1]),
            _Ghost(11, 9, GHOST_COLORS[2]),
            _Ghost(10, 10, GHOST_COLORS[3]),
        ]
        self._total_dots = sum(
            1 for r in range(ROWS) for c in range(COLS) if MAZE[r][c] in (2, 3)
        )

    def _can_move(self, x, y):
        c, r = int(round(x)), int(round(y))
        if 0 <= r < ROWS and 0 <= c < COLS:
            return self.maze[r][c] != 1
        return False

    def step(self):
        if not self.alive:
            return

        # Try next direction first
        nx, ny = self.next_dir
        if nx != 0 or ny != 0:
            if self._can_move(self.px + nx, self.py + ny):
                self.dx, self.dy = nx, ny

        # Move pac
        if self._can_move(self.px + self.dx, self.py + self.dy):
            self.px += self.dx * 0.5
            self.py += self.dy * 0.5
        # Wrap tunnel
        if self.px < 0: self.px = COLS - 1
        if self.px >= COLS: self.px = 0

        # Eat dot
        cr, cc = int(round(self.py)), int(round(self.px))
        if 0 <= cr < ROWS and 0 <= cc < COLS:
            cell = self.maze[cr][cc]
            if cell == 2:
                self.maze[cr][cc] = 0
                self.score += 10
            elif cell == 3:
                self.maze[cr][cc] = 0
                self.score += 50
                for g in self._ghosts:
                    g.frightened = True
                    g.frighten_ticks = 30

        # Mouth animation
        self.mouth_tick += 1
        if self.mouth_tick >= 4:
            self.mouth_tick = 0
            self.mouth_open = not self.mouth_open

        # Ghosts
        for g in self._ghosts:
            if g.frightened:
                g.frighten_ticks -= 1
                if g.frighten_ticks <= 0:
                    g.frightened = False
            # Simple ghost movement
            gc, gr = int(round(g.x)), int(round(g.y))
            options = []
            for ddx, ddy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nc, nr = gc + ddx, gr + ddy
                if 0 <= nr < ROWS and 0 <= nc < COLS and self.maze[nr][nc] != 1:
                    if (ddx, ddy) != (-g.dx, -g.dy):
                        options.append((ddx, ddy))
            if options:
                if not g.frightened:
                    # Chase pac
                    best = min(options, key=lambda o:
                               (gc + o[0] - self.px)**2 + (gr + o[1] - self.py)**2)
                    if random.random() < 0.7:
                        g.dx, g.dy = best
                    else:
                        g.dx, g.dy = random.choice(options)
                else:
                    g.dx, g.dy = random.choice(options)
            g.x += g.dx * 0.5
            g.y += g.dy * 0.5
            if g.x < 0: g.x = COLS - 1
            if g.x >= COLS: g.x = 0

            # Collision with pac
            if abs(g.x - self.px) < 0.9 and abs(g.y - self.py) < 0.9:
                if g.frightened:
                    g.x, g.y = 10.0, 9.0
                    g.frightened = False
                    self.score += 200
                else:
                    self.lives -= 1
                    if self.lives <= 0:
                        self.alive = False
                    else:
                        self.px, self.py = 10.0, 15.0
                        self.dx = self.dy = 0

        # Win
        remaining = sum(1 for r in range(ROWS) for c in range(COLS) if self.maze[r][c] in (2,3))
        if remaining == 0:
            self.score += 500
            self.alive = False  # trigger score post (win)

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
                    p.drawEllipse(x + CELL//2 - 3, y + CELL//2 - 3, 6, 6)
                elif v == 3:
                    p.setBrush(QColor("#FFFFFF"))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(x + CELL//2 - 6, y + CELL//2 - 6, 12, 12)

        # Pac-Man
        px = int(self.px * CELL)
        py = int(self.py * CELL)
        p.setBrush(QColor("#FFD700"))
        p.setPen(Qt.NoPen)
        if self.mouth_open:
            from PySide6.QtCore import QRectF
            # Determine mouth angle based on direction
            angles = {(1,0):30, (-1,0):210, (0,-1):120, (0,1):300}
            start_angle = angles.get((int(self.dx), int(self.dy)), 30)
            span = 300
            p.drawPie(px - CELL//2 + 2, py - CELL//2 + 2, CELL - 4, CELL - 4,
                      start_angle * 16, span * 16)
        else:
            p.drawEllipse(px - CELL//2 + 2, py - CELL//2 + 2, CELL - 4, CELL - 4)

        # Ghosts
        for g in self._ghosts:
            gx = int(g.x * CELL)
            gy = int(g.y * CELL)
            color = QColor("#2196F3") if g.frightened else QColor(g.color)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            # Body
            p.drawEllipse(gx - 8, gy - 10, 16, 16)
            p.drawRect(gx - 8, gy - 2, 16, 10)
            # Eyes
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
            p.drawText(0, H//2 - 20, W, 40, Qt.AlignCenter, "GAME OVER")
            p.setPen(QColor("#FFF"))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(0, H//2 + 24, W, 28, Qt.AlignCenter, f"Skor: {self.score}")
        p.end()
