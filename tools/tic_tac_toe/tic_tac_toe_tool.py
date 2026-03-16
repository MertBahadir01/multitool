"""Tic Tac Toe — PvP or PvAI with minimax algorithm."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame,QComboBox
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QFont,QPainter,QColor,QPen
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score

GAME="tic_tac_toe"

def _winner(b):
    lines=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,c,d in lines:
        if b[a] and b[a]==b[c]==b[d]: return b[a]
    return None

def minimax(b,is_max,depth=0):
    w=_winner(b)
    if w=="O": return 10-depth
    if w=="X": return depth-10
    if all(x for x in b): return 0
    scores=[minimax(b[:i]+[("O" if is_max else "X")]+b[i+1:],not is_max,depth+1)
            for i in range(9) if not b[i]]
    return max(scores) if is_max else min(scores)

def best_move(b):
    best,bi=-999,-1
    for i in range(9):
        if not b[i]:
            s=minimax(b[:i]+["O"]+b[i+1:],False)
            if s>best: best=s;bi=i
    return bi

class BoardWidget(QWidget):
    def __init__(self,on_click,parent=None):
        super().__init__(parent); self.setFixedSize(300,300)
        self.board=[None]*9; self.winner_line=None; self._on_click=on_click
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0,0,300,300,QColor("#1A1A1A"))
        p.setPen(QPen(QColor("#3A3A3A"),3))
        for i in(1,2): p.drawLine(i*100,0,i*100,300); p.drawLine(0,i*100,300,i*100)
        for i,v in enumerate(self.board):
            r,c=i//3,i%3; cx,cy=c*100+50,r*100+50
            if v=="X":
                p.setPen(QPen(QColor("#F44336"),6)); d=30
                p.drawLine(cx-d,cy-d,cx+d,cy+d); p.drawLine(cx+d,cy-d,cx-d,cy+d)
            elif v=="O":
                p.setPen(QPen(QColor("#00BFA5"),6)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(cx-30,cy-30,60,60)
        if self.winner_line:
            a,b2=self.winner_line
            ax,ay=(a%3)*100+50,(a//3)*100+50
            bx,by=(b2%3)*100+50,(b2//3)*100+50
            p.setPen(QPen(QColor("#FFD700"),5)); p.drawLine(ax,ay,bx,by)
        p.end()
    def mousePressEvent(self,e):
        c,r=e.position().x()//100,e.position().y()//100
        self._on_click(int(r)*3+int(c))

class TicTacToeTool(QWidget):
    name="Tic Tac Toe"; description="PvP / PvAI with minimax"
    def __init__(self,parent=None):
        super().__init__(parent); self._user=auth_manager.current_user
        self._current="X"; self._scores={"X":0,"O":0}; self._build(); self._new_game()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("⭕ Tic Tac Toe"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        hl.addWidget(QLabel("Mod:")); self._mode=QComboBox()
        self._mode.addItems(["Oyuncu vs Oyuncu","Oyuncu vs AI"]); hl.addWidget(self._mode)
        new_btn=QPushButton("🆕 Yeni"); new_btn.clicked.connect(self._new_game); hl.addWidget(new_btn)
        root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        self._status=QLabel("X'in sırası"); self._status.setFont(QFont("Segoe UI",14,QFont.Bold))
        self._status.setAlignment(Qt.AlignCenter); self._status.setStyleSheet("color:#FF9800;"); left.addWidget(self._status)
        self._score_lbl=QLabel("X: 0  |  O: 0"); self._score_lbl.setAlignment(Qt.AlignCenter)
        self._score_lbl.setStyleSheet("color:#888;font-size:12px;"); left.addWidget(self._score_lbl)
        self._board_w=BoardWidget(self._on_click); left.addWidget(self._board_w,0,Qt.AlignCenter)
        body.addLayout(left)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
    def _new_game(self):
        self._board=[None]*9; self._current="X"; self._game_over=False
        self._board_w.board=self._board; self._board_w.winner_line=None
        self._board_w.update(); self._status.setText("X'in sırası")
        self._status.setStyleSheet("color:#FF9800;")
    def _on_click(self,idx):
        if self._game_over or self._board[idx]: return
        self._board[idx]=self._current; self._check_end()
        if not self._game_over and self._mode.currentIndex()==1 and self._current=="O":
            QTimer.singleShot(200,self._ai_move)
    def _ai_move(self):
        if self._game_over: return
        m=best_move(self._board)
        if m is not None: self._board[m]="O"; self._check_end()
    def _check_end(self):
        w=_winner(self._board)
        self._board_w.board=self._board
        if w:
            lines=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
            for a,_,c in lines:
                if self._board[a]==w and self._board[(a+c)//2]==w and self._board[c]==w:
                    self._board_w.winner_line=(a,c); break
            self._game_over=True; self._scores[w]+=1
            self._status.setText(f"🎉 {w} kazandı!"); self._status.setStyleSheet("color:#4CAF50;")
            self._score_lbl.setText(f"X: {self._scores['X']}  |  O: {self._scores['O']}")
            if self._user:
                post_score(GAME,self._user["id"],self._user["username"],
                           self._scores[self._user.get("symbol","X")] if hasattr(self._user,"get") else self._scores["X"])
                self._sb.refresh()
        elif all(self._board):
            self._game_over=True; self._status.setText("🤝 Beraberlik!")
            self._status.setStyleSheet("color:#888;")
        else:
            self._current="O" if self._current=="X" else "X"
            self._status.setText(f"{'O' if self._current=='O' else 'X'}'nin sırası")
        self._board_w.update()