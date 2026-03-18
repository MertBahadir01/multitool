"""Breakout — paddle, ball, brick grid, levels, scoreboard."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "breakout"
W, H = 480, 480
PAD_W, PAD_H = 72, 12
BALL_R = 8
BRICK_ROWS, BRICK_COLS = 6, 10
BRICK_W = W // BRICK_COLS
BRICK_H = 20
BRICK_TOP = 40

BRICK_COLORS = [
    "#F44336", "#FF9800", "#FFEB3B",
    "#4CAF50", "#2196F3", "#9C27B0",
]


class BreakoutCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(W, H)
        self._reset()

    def _reset(self):
        self.score = 0
        self.lives = 3
        self.level = 1
        self.alive = True
        self.started = False
        self._pad_x = W // 2 - PAD_W // 2
        self._bx = float(W // 2)
        self._by = float(H - 60)
        speed = 3 + self.level
        self._dx = random.choice([-1, 1]) * speed
        self._dy = -speed
        self._bricks = self._make_bricks()

    def _make_bricks(self):
        bricks = []
        for r in range(BRICK_ROWS):
            for c in range(BRICK_COLS):
                bricks.append({
                    "x": c * BRICK_W + 2,
                    "y": BRICK_TOP + r * (BRICK_H + 4),
                    "w": BRICK_W - 4,
                    "h": BRICK_H,
                    "color": BRICK_COLORS[r % len(BRICK_COLORS)],
                    "alive": True,
                    "pts": (BRICK_ROWS - r) * 10,
                })
        return bricks

    def move_pad(self, dx):
        self._pad_x = max(0, min(W - PAD_W, self._pad_x + dx))

    def step(self):
        if not self.started or not self.alive:
            return
        self._bx += self._dx
        self._by += self._dy
        # Wall bounce
        if self._bx - BALL_R < 0:
            self._bx = BALL_R; self._dx = abs(self._dx)
        if self._bx + BALL_R > W:
            self._bx = W - BALL_R; self._dx = -abs(self._dx)
        if self._by - BALL_R < 0:
            self._by = BALL_R; self._dy = abs(self._dy)
        # Bottom — lose life
        if self._by + BALL_R > H:
            self.lives -= 1
            if self.lives <= 0:
                self.alive = False
            else:
                self.started = False
                self._bx = float(self._pad_x + PAD_W // 2)
                self._by = float(H - 60)
                speed = 3 + self.level
                self._dx = random.choice([-1, 1]) * speed
                self._dy = -speed
            self.update()
            return
        # Paddle bounce
        if (self._pad_x <= self._bx <= self._pad_x + PAD_W and
                H - PAD_H - 20 <= self._by + BALL_R <= H - 20):
            # Angle based on hit position
            offset = (self._bx - (self._pad_x + PAD_W / 2)) / (PAD_W / 2)
            speed = (self._dx ** 2 + self._dy ** 2) ** 0.5
            self._dx = offset * speed
            self._dy = -abs(self._dy)
        # Brick collision
        for b in self._bricks:
            if not b["alive"]:
                continue
            if (b["x"] < self._bx + BALL_R and self._bx - BALL_R < b["x"] + b["w"] and
                    b["y"] < self._by + BALL_R and self._by - BALL_R < b["y"] + b["h"]):
                b["alive"] = False
                self.score += b["pts"]
                self._dy *= -1
                break
        # Level up
        if all(not b["alive"] for b in self._bricks):
            self.level += 1
            self.score += 500
            speed = 3 + self.level
            self._bricks = self._make_bricks()
            self._bx = float(self._pad_x + PAD_W // 2)
            self._by = float(H - 60)
            self._dx = random.choice([-1, 1]) * speed
            self._dy = -speed
            self.started = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, W, H, QColor("#0D0D0D"))
        # Bricks
        for b in self._bricks:
            if b["alive"]:
                p.setBrush(QColor(b["color"]))
                p.setPen(QColor("#0D0D0D"))
                p.drawRoundedRect(b["x"], b["y"], b["w"], b["h"], 3, 3)
        # Paddle
        p.setBrush(QColor("#00BFA5"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self._pad_x, H - PAD_H - 20, PAD_W, PAD_H, 6, 6)
        # Ball
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(int(self._bx - BALL_R), int(self._by - BALL_R), BALL_R * 2, BALL_R * 2)
        # HUD
        p.setPen(QColor("#888"))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(8, 20, f"Skor: {self.score}  Seviye: {self.level}  ❤ {self.lives}")
        if not self.alive:
            p.fillRect(0, 0, W, H, QColor(0, 0, 0, 160))
            p.setPen(QColor("#F44336"))
            p.setFont(QFont("Segoe UI", 24, QFont.Bold))
            p.drawText(0, H // 2 - 30, W, 40, Qt.AlignCenter, "GAME OVER")
            p.setPen(QColor("#FFF"))
            p.setFont(QFont("Segoe UI", 14))
            p.drawText(0, H // 2 + 16, W, 30, Qt.AlignCenter, f"Skor: {self.score}")
        elif not self.started:
            p.setPen(QColor("#AAA"))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(0, H - 10, W, 20, Qt.AlignCenter, "SPACE / Tıkla ile başlat")
        p.end()


class BreakoutTool(QWidget):
    name = "Breakout"
    description = "Break bricks with the ball and paddle"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._score_posted = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 10, 20, 10)
        t = QLabel("🧱 Breakout")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("← → veya A D hareket  |  SPACE başlat",
                            styleSheet="color:#555; font-size:11px;"))
        root.addWidget(hdr)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(20)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._canvas = BreakoutCanvas()
        self._canvas.mousePressEvent = lambda _: self._tap()
        ll.addWidget(self._canvas)
        restart_btn = QPushButton("🔄 Yeniden Başla")
        restart_btn.clicked.connect(self._restart)
        ll.addWidget(restart_btn)
        body_lay.addWidget(left)

        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb)

        root.addWidget(body, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self._left = False
        self._right = False
        self.setFocusPolicy(Qt.StrongFocus)

    def _tap(self):
        self._canvas.started = True
        self.setFocus()

    def _restart(self):
        self._canvas._reset()
        self._score_posted = False
        self.setFocus()

    def _tick(self):
        if self._left:
            self._canvas.move_pad(-6)
        if self._right:
            self._canvas.move_pad(6)
        self._canvas.step()
        if not self._canvas.alive and not self._score_posted:
            self._score_posted = True
            if self._user and self._canvas.score > 0:
                post_score(GAME, self._user["id"], self._user["username"], self._canvas.score)
                self._sb.refresh()

    def keyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k in (Qt.Key_Left, Qt.Key_A):   self._left = True
        if k in (Qt.Key_Right, Qt.Key_D):  self._right = True
        if k == Qt.Key_Space:
            self._canvas.started = True

    def keyReleaseEvent(self, e: QKeyEvent):
        k = e.key()
        if k in (Qt.Key_Left, Qt.Key_A):   self._left = False
        if k in (Qt.Key_Right, Qt.Key_D):  self._right = False
