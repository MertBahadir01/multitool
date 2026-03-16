"""Flappy Bird — tap/space to fly, random pipes, score tracking."""
import random
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QPainter,QColor,QFont,QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score

GAME="flappy_bird"; W=400; H=500; GAP=130; PIPE_W=52; PIPE_SPEED=3; GRAV=0.5; JUMP=-8

class FlappyCanvas(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(W,H)
        self.setStyleSheet("background:#87CEEB;border-radius:8px;")
        self._reset()
    def _reset(self):
        self.bird_y=H//2; self.vel=0; self.pipes=[]; self.score=0
        self.alive=True; self.started=False; self._frame=0
        self._add_pipe()
    def _add_pipe(self):
        top=random.randint(60,H-GAP-60)
        self.pipes.append({"x":W+20,"top":top})
    def tap(self):
        if not self.alive: return
        self.started=True; self.vel=JUMP
    def step(self):
        if not self.started or not self.alive: return
        self._frame+=1
        self.vel+=GRAV; self.bird_y+=self.vel
        if self.bird_y<0 or self.bird_y>H-24: self.alive=False; self.update(); return
        for p in self.pipes:
            p["x"]-=PIPE_SPEED
            if 60<p["x"]<120:
                if not(p["top"]<self.bird_y<p["top"]+GAP):
                    self.alive=False; self.update(); return
            if p["x"]==58: self.score+=1
        self.pipes=[p for p in self.pipes if p["x"]>-PIPE_W]
        if self._frame%90==0: self._add_pipe()
        self.update()
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        # sky gradient
        p.fillRect(0,0,W,H,QColor("#87CEEB"))
        # ground
        p.fillRect(0,H-40,W,40,QColor("#8B6914"))
        p.fillRect(0,H-48,W,8,QColor("#5C8A1E"))
        # pipes
        for pipe in self.pipes:
            p.setBrush(QColor("#2E7D32")); p.setPen(Qt.NoPen)
            p.drawRect(pipe["x"],0,PIPE_W,pipe["top"])
            p.drawRect(pipe["x"],pipe["top"]+GAP,PIPE_W,H)
            p.setBrush(QColor("#388E3C"))
            p.drawRect(pipe["x"]-4,pipe["top"]-16,PIPE_W+8,16)
            p.drawRect(pipe["x"]-4,pipe["top"]+GAP,PIPE_W+8,16)
        # bird
        bx,by=80,int(self.bird_y)
        p.setBrush(QColor("#FFD700")); p.drawEllipse(bx,by,28,24)
        p.setBrush(QColor("#FF6F00")); p.drawEllipse(bx+18,by+8,14,8)
        p.setBrush(QColor("#333")); p.drawEllipse(bx+20,by+4,7,7)
        p.setBrush(QColor("#FFF")); p.drawEllipse(bx+22,by+5,3,3)
        # score
        p.setPen(QColor("#FFF")); p.setFont(QFont("Segoe UI",22,QFont.Bold))
        p.drawText(0,20,W,40,Qt.AlignCenter,str(self.score))
        if not self.alive:
            p.fillRect(0,0,W,H,QColor(0,0,0,150))
            p.setPen(QColor("#F44336")); p.setFont(QFont("Segoe UI",26,QFont.Bold))
            p.drawText(0,H//2-40,W,50,Qt.AlignCenter,"GAME OVER")
            p.setPen(QColor("#FFF")); p.setFont(QFont("Segoe UI",16))
            p.drawText(0,H//2+10,W,30,Qt.AlignCenter,f"Skor: {self.score}")
        elif not self.started:
            p.fillRect(0,0,W,H,QColor(0,0,0,80))
            p.setPen(QColor("#FFF")); p.setFont(QFont("Segoe UI",16))
            p.drawText(0,H//2-10,W,30,Qt.AlignCenter,"SPACE / Tıkla ile başla")
        p.end()

class FlappyBirdTool(QWidget):
    name="Flappy Bird"; description="Tap/Space to fly through pipes"
    def __init__(self,parent=None):
        super().__init__(parent)
        self._user=auth_manager.current_user; self._score_posted=False; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("🐦 Flappy Bird"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch(); root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        self._canvas=FlappyCanvas()
        self._canvas.mousePressEvent=lambda _:self._tap()
        left.addWidget(self._canvas)
        self._restart_btn=QPushButton("🔄 Yeniden Başla"); self._restart_btn.clicked.connect(self._restart)
        left.addWidget(self._restart_btn)
        self._score_lbl=QLabel("Skor: 0"); self._score_lbl.setAlignment(Qt.AlignCenter)
        self._score_lbl.setFont(QFont("Segoe UI",16,QFont.Bold)); self._score_lbl.setStyleSheet("color:#FF9800;")
        left.addWidget(self._score_lbl)
        body.addLayout(left)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._timer=QTimer(); self._timer.timeout.connect(self._tick); self._timer.start(16)
        self.setFocusPolicy(Qt.StrongFocus)
    def _tap(self):
        self._canvas.tap(); self.setFocus()
    def _restart(self):
        self._canvas._reset(); self._score_posted=False
        self._score_lbl.setText("Skor: 0"); self.setFocus()
    def _tick(self):
        self._canvas.step()
        self._score_lbl.setText(f"Skor: {self._canvas.score}")
        if not self._canvas.alive and self._canvas.started and not self._score_posted:
            self._score_posted=True
            score=self._canvas.score
            if self._user and score>0:
                post_score(GAME,self._user["id"],self._user["username"],score)
                self._sb.refresh()
            self._canvas.started=False
    def keyPressEvent(self,e:QKeyEvent):
        if e.key() in(Qt.Key_Space,Qt.Key_Up): self._tap()