"""Pong — Player vs AI, increasing ball speed, scoreboard."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QPainter,QColor,QFont,QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score

GAME="pong"; W=600; H=400; PAD_W=12; PAD_H=70; BALL=12

class PongCanvas(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(W,H)
        self._reset()
    def _reset(self):
        self.py=(H-PAD_H)//2; self.ay=(H-PAD_H)//2
        self.bx,self.by=W//2,H//2; self.bdx,self.bdy=4,3
        self.ps=self.as_=0; self.alive=True; self.started=False
        self.speed_mult=1.0
    def step(self,up,down):
        if not self.started or not self.alive: return
        spd=6
        if up and self.py>0: self.py-=spd
        if down and self.py<H-PAD_H: self.py+=spd
        # AI
        cy=self.ay+PAD_H//2
        if cy<self.by-4: self.ay=min(self.ay+4,H-PAD_H)
        elif cy>self.by+4: self.ay=max(self.ay-4,0)
        # ball
        self.bx+=self.bdx; self.by+=self.bdy
        if self.by<=0 or self.by>=H-BALL: self.bdy*=-1
        # player paddle
        px=20
        if px<self.bx<px+PAD_W and self.py<self.by<self.py+PAD_H:
            self.bdx=abs(self.bdx)*self.speed_mult; offset=(self.by-(self.py+PAD_H//2))/(PAD_H//2); self.bdy=offset*6
            self.speed_mult=min(2.0,self.speed_mult+0.05)
        # ai paddle
        ax=W-20-PAD_W
        if ax<self.bx+BALL<ax+PAD_W and self.ay<self.by<self.ay+PAD_H:
            self.bdx=-abs(self.bdx)*self.speed_mult
        # score
        if self.bx<0: self.as_+=1; self._serve(-1)
        elif self.bx>W: self.ps+=1; self._serve(1)
        if self.ps>=7 or self.as_>=7: self.alive=False
        self.update()
    def _serve(self,dir_):
        import random
        self.bx,self.by=W//2,H//2; self.bdx=4*dir_; self.bdy=random.choice([-3,3])
        self.speed_mult=1.0
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0,0,W,H,QColor("#0D0D0D"))
        p.setPen(QColor("#222")); 
        for y in range(0,H,20):
            if (y//20)%2==0: p.fillRect(W//2-2,y,4,10,QColor("#222"))
        # paddles
        p.setBrush(QColor("#00BFA5")); p.setPen(Qt.NoPen)
        p.drawRoundedRect(20,self.py,PAD_W,PAD_H,6,6)
        p.setBrush(QColor("#F44336"))
        p.drawRoundedRect(W-20-PAD_W,self.ay,PAD_W,PAD_H,6,6)
        # ball
        p.setBrush(QColor("#FFF"))
        p.drawEllipse(int(self.bx),int(self.by),BALL,BALL)
        # scores
        p.setPen(QColor("#555")); p.setFont(QFont("Segoe UI",28,QFont.Bold))
        p.drawText(W//2-80,10,80,50,Qt.AlignRight,str(self.ps))
        p.drawText(W//2+10,10,80,50,Qt.AlignLeft,str(self.as_))
        # labels
        p.setPen(QColor("#00BFA5")); p.setFont(QFont("Segoe UI",10))
        p.drawText(10,H-20,60,20,Qt.AlignLeft,"SEN")
        p.setPen(QColor("#F44336")); p.drawText(W-70,H-20,60,20,Qt.AlignRight,"AI")
        if not self.alive:
            p.fillRect(0,0,W,H,QColor(0,0,0,160))
            winner="SEN" if self.ps>self.as_ else "AI"
            col=QColor("#00BFA5") if winner=="SEN" else QColor("#F44336")
            p.setPen(col); p.setFont(QFont("Segoe UI",28,QFont.Bold))
            p.drawText(0,H//2-30,W,50,Qt.AlignCenter,f"{winner} KAZANDI!")
        elif not self.started:
            p.fillRect(0,0,W,H,QColor(0,0,0,100))
            p.setPen(QColor("#FFF")); p.setFont(QFont("Segoe UI",14))
            p.drawText(0,H//2-10,W,30,Qt.AlignCenter,"SPACE / Tıkla ile başla")
        p.end()

class PongTool(QWidget):
    name="Pong"; description="Classic Pong vs AI"
    def __init__(self,parent=None):
        super().__init__(parent); self._user=auth_manager.current_user
        self._up=self._down=False; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("🏓 Pong"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        hl.addWidget(QLabel("W/S veya ↑↓ ile hareket",styleSheet="color:#555;font-size:12px;"))
        root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        self._canvas=PongCanvas()
        self._canvas.mousePressEvent=lambda _:self._start()
        left.addWidget(self._canvas)
        rb=QPushButton("🔄 Yeniden Başla"); rb.clicked.connect(self._restart); left.addWidget(rb)
        body.addLayout(left)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._timer=QTimer(); self._timer.timeout.connect(self._tick); self._timer.start(16)
        self.setFocusPolicy(Qt.StrongFocus)
    def _start(self):
        self._canvas.started=True; self.setFocus()
    def _restart(self):
        self._canvas._reset(); self.setFocus()
    def _tick(self):
        self._canvas.step(self._up,self._down)
        if not self._canvas.alive and self._canvas.started:
            if self._user:
                post_score(GAME,self._user["id"],self._user["username"],self._canvas.ps)
                self._sb.refresh()
            self._canvas.started=False
    def keyPressEvent(self,e:QKeyEvent):
        if e.key() in(Qt.Key_Up,Qt.Key_W): self._up=True
        if e.key() in(Qt.Key_Down,Qt.Key_S): self._down=True
        if e.key()==Qt.Key_Space: self._start()
    def keyReleaseEvent(self,e:QKeyEvent):
        if e.key() in(Qt.Key_Up,Qt.Key_W): self._up=False
        if e.key() in(Qt.Key_Down,Qt.Key_S): self._down=False
