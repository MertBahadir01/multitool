"""Minesweeper — grid-based, flagging, Easy/Medium/Hard."""
import random
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame,QComboBox,QGridLayout
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QFont,QColor
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score

GAME="minesweeper"
MODES={"Easy":(9,9,10),"Medium":(16,16,40),"Hard":(16,30,99)}

class Cell(QPushButton):
    def __init__(self,r,c,parent=None):
        super().__init__(parent); self.r=r;self.c=c
        self.mine=False;self.revealed=False;self.flagged=False;self.adj=0
        self.setFixedSize(32,32); self._set_hidden()
    def _set_hidden(self):
        self.setStyleSheet("background:#3A3A3A;border:1px solid #555;border-radius:2px;font-size:11px;color:#E0E0E0;")
    def reveal(self):
        self.revealed=True
        if self.mine:
            self.setText("💣"); self.setStyleSheet("background:#F44336;border:none;border-radius:2px;font-size:12px;")
        elif self.adj==0:
            self.setText(""); self.setStyleSheet("background:#252525;border:1px solid #333;border-radius:2px;")
        else:
            COLORS=["","#2196F3","#4CAF50","#F44336","#9C27B0","#FF5722","#00BCD4","#333","#888"]
            self.setText(str(self.adj))
            self.setStyleSheet(f"background:#1E1E1E;border:1px solid #333;border-radius:2px;font-size:13px;font-weight:bold;color:{COLORS[self.adj]};")
    def toggle_flag(self):
        if self.revealed: return
        self.flagged=not self.flagged
        if self.flagged: self.setText("🚩"); self.setStyleSheet("background:#3A3A3A;border:1px solid #F44336;border-radius:2px;font-size:12px;")
        else: self.setText(""); self._set_hidden()

class MinesweeperTool(QWidget):
    name="Minesweeper"; description="Classic minesweeper with flagging"
    def __init__(self,parent=None):
        super().__init__(parent); self._user=auth_manager.current_user
        self._cells=[]; self._rows=self._cols=self._mines=0
        self._started=False; self._over=False; self._secs=0
        self._build(); self._new_game()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("💣 Minesweeper"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        self._mode_cb=QComboBox(); self._mode_cb.addItems(list(MODES.keys())); hl.addWidget(self._mode_cb)
        nb=QPushButton("🆕 Yeni"); nb.clicked.connect(self._new_game); hl.addWidget(nb)
        root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        info=QHBoxLayout()
        self._mine_lbl=QLabel("💣 0"); self._mine_lbl.setStyleSheet("color:#F44336;font-size:14px;font-weight:bold;"); info.addWidget(self._mine_lbl)
        info.addStretch()
        self._time_lbl=QLabel("⏱ 0"); self._time_lbl.setStyleSheet("color:#888;font-size:13px;"); info.addWidget(self._time_lbl)
        left.addLayout(info)
        self._status=QLabel(""); self._status.setAlignment(Qt.AlignCenter); self._status.setStyleSheet("font-size:13px;"); left.addWidget(self._status)
        scroll=QFrame(); scroll.setStyleSheet("background:#1A1A1A;border-radius:8px;"); sv=QVBoxLayout(scroll); sv.setContentsMargins(8,8,8,8)
        self._grid_lay=QGridLayout(); self._grid_lay.setSpacing(1); sv.addLayout(self._grid_lay)
        left.addWidget(scroll)
        body.addLayout(left)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._timer=QTimer(); self._timer.timeout.connect(self._tick)
    def _new_game(self):
        self._timer.stop(); self._secs=0; self._started=False; self._over=False
        rows,cols,mines=MODES[self._mode_cb.currentText()]
        self._rows=rows; self._cols=cols; self._mines=mines
        for i in reversed(range(self._grid_lay.count())):
            w=self._grid_lay.itemAt(i).widget()
            if w: w.deleteLater()
        self._cells=[]
        for r in range(rows):
            row=[]
            for c in range(cols):
                cell=Cell(r,c)
                cell.clicked.connect(lambda _,r=r,c=c:self._reveal(r,c))
                cell.setContextMenuPolicy(Qt.CustomContextMenu)
                cell.customContextMenuRequested.connect(lambda _,r=r,c=c:self._flag(r,c))
                self._grid_lay.addWidget(cell,r,c); row.append(cell)
            self._cells.append(row)
        self._mine_lbl.setText(f"💣 {mines}"); self._time_lbl.setText("⏱ 0"); self._status.setText("")
        self._sb.refresh()
    def _place_mines(self,fr,fc):
        positions=[(r,c) for r in range(self._rows) for c in range(self._cols) if abs(r-fr)>1 or abs(c-fc)>1]
        for r,c in random.sample(positions,min(self._mines,len(positions))):
            self._cells[r][c].mine=True
        for r in range(self._rows):
            for c in range(self._cols):
                if not self._cells[r][c].mine:
                    self._cells[r][c].adj=sum(1 for dr in(-1,0,1) for dc in(-1,0,1)
                        if 0<=r+dr<self._rows and 0<=c+dc<self._cols and self._cells[r+dr][c+dc].mine)
    def _reveal(self,r,c):
        if self._over: return
        cell=self._cells[r][c]
        if cell.flagged or cell.revealed: return
        if not self._started:
            self._started=True; self._place_mines(r,c); self._timer.start(1000)
        cell.reveal()
        if cell.mine:
            self._over=True; self._timer.stop()
            for row in self._cells:
                for cl in row:
                    if cl.mine: cl.reveal()
            self._status.setText("💥 Mayına bastınız!"); self._status.setStyleSheet("color:#F44336;")
            return
        if cell.adj==0:
            for dr in(-1,0,1):
                for dc in(-1,0,1):
                    nr,nc=r+dr,c+dc
                    if 0<=nr<self._rows and 0<=nc<self._cols and not self._cells[nr][nc].revealed:
                        self._reveal(nr,nc)
        self._check_win()
    def _flag(self,r,c):
        if self._over: return
        cell=self._cells[r][c]
        if not cell.revealed: cell.toggle_flag()
        flags=sum(1 for row in self._cells for cl in row if cl.flagged)
        self._mine_lbl.setText(f"💣 {self._mines-flags}")
    def _check_win(self):
        if all(self._cells[r][c].revealed or self._cells[r][c].mine
               for r in range(self._rows) for c in range(self._cols)):
            self._over=True; self._timer.stop()
            score=max(1,10000-self._secs*10)
            self._status.setText("🎉 Kazandınız!"); self._status.setStyleSheet("color:#4CAF50;")
            if self._user:
                post_score(GAME,self._user["id"],self._user["username"],score)
                self._sb.refresh()
    def _tick(self):
        self._secs+=1; self._time_lbl.setText(f"⏱ {self._secs}")