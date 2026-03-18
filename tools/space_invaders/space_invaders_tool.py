"""Space Invaders — alien grid, player laser, shields, levels, scoreboard."""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "space_invaders"
W, H = 480, 500
PLAYER_W, PLAYER_H = 36, 20
ALIEN_ROWS, ALIEN_COLS = 4, 10
ALIEN_W, ALIEN_H = 36, 24
ALIEN_H_GAP = 12
BULLET_W, BULLET_H = 3, 12
ALIEN_ICONS = ["👾", "👽", "🛸", "🤖"]
ALIEN_PTS   = [10, 20, 30, 40]


class SpaceInvadersTool(QWidget):
    name = "Space Invaders"
    description = "Shoot down the alien invasion"

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
        t = QLabel("👾 Space Invaders")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("← → hareket  |  SPACE ateş",
                            styleSheet="color:#555; font-size:11px;"))
        root.addWidget(hdr)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(20)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self._canvas = _Canvas(self)
        ll.addWidget(self._canvas)
        restart_btn = QPushButton("🔄 Yeniden Başla")
        restart_btn.clicked.connect(self._new_game)
        ll.addWidget(restart_btn)
        body_lay.addWidget(left)

        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb)

        root.addWidget(body, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._left = self._right = self._fire = False
        self.setFocusPolicy(Qt.StrongFocus)

    def _new_game(self):
        self._canvas._reset()
        self._score_posted = False
        self._timer.start(40)
        self.setFocus()

    def _tick(self):
        c = self._canvas
        if not c.alive:
            if not self._score_posted:
                self._score_posted = True
                if self._user and c.score > 0:
                    post_score(GAME, self._user["id"], self._user["username"], c.score)
                    self._sb.refresh()
            return
        if self._left:  c.px = max(0, c.px - 5)
        if self._right: c.px = min(W - PLAYER_W, c.px + 5)
        if self._fire:  c.shoot(); self._fire = False
        c.step()

    def keyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k in (Qt.Key_Left, Qt.Key_A):   self._left = True
        if k in (Qt.Key_Right, Qt.Key_D):  self._right = True
        if k == Qt.Key_Space: self._fire = True

    def keyReleaseEvent(self, e: QKeyEvent):
        k = e.key()
        if k in (Qt.Key_Left, Qt.Key_A):   self._left = False
        if k in (Qt.Key_Right, Qt.Key_D):  self._right = False


class _Canvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(W, H)
        self._reset()

    def _reset(self):
        self.score = 0
        self.lives = 3
        self.level = 1
        self.alive = True
        self.px = W // 2 - PLAYER_W // 2
        self._bullets = []
        self._alien_bullets = []
        self._alien_dir = 1
        self._alien_speed = 0.6
        self._alien_tick = 0
        self._fire_cooldown = 0
        self._make_aliens()

    def _make_aliens(self):
        self._aliens = []
        ox = (W - ALIEN_COLS * ALIEN_W) // 2
        for r in range(ALIEN_ROWS):
            for c in range(ALIEN_COLS):
                self._aliens.append({
                    "x": float(ox + c * ALIEN_W),
                    "y": float(60 + r * (ALIEN_H + ALIEN_H_GAP)),
                    "row": r, "alive": True,
                })

    def shoot(self):
        if self._fire_cooldown > 0:
            return
        self._bullets.append({"x": self.px + PLAYER_W // 2, "y": H - PLAYER_H - 20})
        self._fire_cooldown = 15

    def step(self):
        if not self.alive:
            return
        if self._fire_cooldown > 0:
            self._fire_cooldown -= 1

        # Move bullets
        self._bullets = [b for b in self._bullets if b["y"] > 0]
        for b in self._bullets:
            b["y"] -= 8

        # Alien bullets
        self._alien_bullets = [b for b in self._alien_bullets if b["y"] < H]
        for b in self._alien_bullets:
            b["y"] += 4

        # Alien movement
        self._alien_tick += self._alien_speed
        alive = [a for a in self._aliens if a["alive"]]
        if not alive:
            self.level += 1
            self.score += 200
            self._alien_speed = 0.6 + self.level * 0.3
            self._make_aliens()
            return

        if self._alien_tick >= 1:
            self._alien_tick = 0
            xs = [a["x"] for a in alive]
            if max(xs) + ALIEN_W > W - 4:
                self._alien_dir = -1
                for a in self._aliens:
                    a["y"] += 16
            elif min(xs) < 4:
                self._alien_dir = 1
                for a in self._aliens:
                    a["y"] += 16
            for a in self._aliens:
                if a["alive"]:
                    a["x"] += self._alien_dir * 8

            # Alien fire
            cols = {}
            for a in alive:
                c = round(a["x"])
                cols.setdefault(c, []).append(a)
            if random.random() < 0.3 and cols:
                shooter = random.choice(list(cols.values()))[-1]
                self._alien_bullets.append({
                    "x": shooter["x"] + ALIEN_W // 2,
                    "y": shooter["y"] + ALIEN_H,
                })

        # Collision: player bullets vs aliens
        for b in list(self._bullets):
            for a in self._aliens:
                if not a["alive"]:
                    continue
                if a["x"] < b["x"] < a["x"] + ALIEN_W and a["y"] < b["y"] < a["y"] + ALIEN_H:
                    a["alive"] = False
                    self.score += ALIEN_PTS[a["row"]]
                    if b in self._bullets:
                        self._bullets.remove(b)
                    break

        # Alien bullets hit player
        py = H - PLAYER_H - 10
        for b in list(self._alien_bullets):
            if self.px < b["x"] < self.px + PLAYER_W and py < b["y"] < py + PLAYER_H:
                self.lives -= 1
                self._alien_bullets.remove(b)
                if self.lives <= 0:
                    self.alive = False

        # Aliens reach bottom
        if any(a["y"] + ALIEN_H >= H - 40 for a in self._aliens if a["alive"]):
            self.alive = False

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, W, H, QColor("#050510"))

        # Stars
        p.setPen(QColor("#FFFFFF"))
        for sx, sy in [(50, 30), (120, 80), (200, 20), (300, 60), (400, 40),
                       (70, 150), (350, 120), (430, 200), (160, 300), (260, 180)]:
            p.drawPoint(sx, sy)

        # Aliens
        p.setFont(QFont("Segoe UI Emoji", 14))
        for a in self._aliens:
            if a["alive"]:
                p.drawText(int(a["x"]), int(a["y"]), ALIEN_W, ALIEN_H,
                           Qt.AlignCenter, ALIEN_ICONS[a["row"]])

        # Player
        p.setBrush(QColor("#00BFA5"))
        p.setPen(Qt.NoPen)
        py = H - PLAYER_H - 10
        # Body
        p.drawRect(self.px + 6, py + 6, PLAYER_W - 12, PLAYER_H - 6)
        # Cockpit
        p.drawRect(self.px + 14, py, 8, 10)
        # Wings
        p.drawRect(self.px, py + 10, PLAYER_W, 8)

        # Player bullets
        p.setBrush(QColor("#FFEB3B"))
        for b in self._bullets:
            p.drawRect(int(b["x"]) - 1, int(b["y"]), BULLET_W, BULLET_H)

        # Alien bullets
        p.setBrush(QColor("#F44336"))
        for b in self._alien_bullets:
            p.drawRect(int(b["x"]) - 1, int(b["y"]), BULLET_W, BULLET_H)

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
        p.end()
