"""Login and Registration window."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QStackedWidget, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from core.auth_manager import auth_manager
from database.database import user_exists


class LoginWindow(QDialog):
    login_success = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("MultiTool Studio – Login")

        # Larger window for breathing room
        self.setFixedSize(560, 650)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self._drag_pos = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Larger margins and spacing
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(22)

        # Header
        header = QLabel("⚙ MultiTool Studio")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)
        header.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(header)

        sub = QLabel("Your All-in-One Productivity Toolbox")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignCenter)
        sub.setFont(QFont("Segoe UI", 11))
        layout.addWidget(sub)

        layout.addSpacing(20)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # =========================
        # Login Page
        # =========================
        self.login_page = QWidget()
        lp = QVBoxLayout(self.login_page)

        lp.setSpacing(16)
        lp.setContentsMargins(0, 10, 0, 0)

        lp.addWidget(QLabel("Username"))
        lp.addSpacing(4)

        self.login_user = QLineEdit()
        self.login_user.setPlaceholderText("Enter username")
        self.login_user.setMinimumHeight(36)
        lp.addWidget(self.login_user)

        lp.addWidget(QLabel("Password"))
        lp.addSpacing(4)

        self.login_pass = QLineEdit()
        self.login_pass.setEchoMode(QLineEdit.Password)
        self.login_pass.setPlaceholderText("Enter password")
        self.login_pass.setMinimumHeight(36)
        self.login_pass.returnPressed.connect(self._do_login)
        lp.addWidget(self.login_pass)

        lp.addSpacing(10)

        btn_login = QPushButton("Login")
        btn_login.setMinimumHeight(40)
        btn_login.clicked.connect(self._do_login)
        lp.addWidget(btn_login)

        self.login_status = QLabel("")
        self.login_status.setAlignment(Qt.AlignCenter)
        lp.addWidget(self.login_status)

        lp.addSpacing(10)

        switch_reg = QPushButton("No account? Register here")
        switch_reg.setObjectName("secondary")
        switch_reg.setMinimumHeight(34)
        switch_reg.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        lp.addWidget(switch_reg)

        lp.addStretch()

        self.stack.addWidget(self.login_page)

        # =========================
        # Register Page
        # =========================
        self.reg_page = QWidget()
        rp = QVBoxLayout(self.reg_page)

        rp.setSpacing(16)
        rp.setContentsMargins(0, 10, 0, 0)

        title = QLabel("Create Account")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        rp.addWidget(title)

        rp.addWidget(QLabel("Username"))
        rp.addSpacing(4)

        self.reg_user = QLineEdit()
        self.reg_user.setPlaceholderText("Choose a username")
        self.reg_user.setMinimumHeight(36)
        rp.addWidget(self.reg_user)

        rp.addWidget(QLabel("Password"))
        rp.addSpacing(4)

        self.reg_pass = QLineEdit()
        self.reg_pass.setEchoMode(QLineEdit.Password)
        self.reg_pass.setPlaceholderText("Min 8 characters")
        self.reg_pass.setMinimumHeight(36)
        rp.addWidget(self.reg_pass)

        rp.addWidget(QLabel("Confirm Password"))
        rp.addSpacing(4)

        self.reg_pass2 = QLineEdit()
        self.reg_pass2.setEchoMode(QLineEdit.Password)
        self.reg_pass2.setPlaceholderText("Repeat password")
        self.reg_pass2.setMinimumHeight(36)
        self.reg_pass2.returnPressed.connect(self._do_register)
        rp.addWidget(self.reg_pass2)

        rp.addSpacing(10)

        btn_reg = QPushButton("Create Account")
        btn_reg.setMinimumHeight(40)
        btn_reg.clicked.connect(self._do_register)
        rp.addWidget(btn_reg)

        self.reg_status = QLabel("")
        self.reg_status.setAlignment(Qt.AlignCenter)
        rp.addWidget(self.reg_status)

        rp.addSpacing(10)

        switch_login = QPushButton("Already have an account? Login")
        switch_login.setObjectName("secondary")
        switch_login.setMinimumHeight(34)
        switch_login.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        rp.addWidget(switch_login)

        rp.addStretch()

        self.stack.addWidget(self.reg_page)

        # Auto-switch if no users exist
        if not user_exists():
            self.stack.setCurrentIndex(1)

        # Auto focus username
        self.login_user.setFocus()

    def _do_login(self):
        u = self.login_user.text().strip()
        p = self.login_pass.text()

        ok, msg = auth_manager.login(u, p)

        if ok:
            self.login_success.emit()
            self.accept()
        else:
            self.login_status.setStyleSheet("color: #F44336;")
            self.login_status.setText(msg)

    def _do_register(self):
        u = self.reg_user.text().strip()
        p = self.reg_pass.text()
        p2 = self.reg_pass2.text()

        if p != p2:
            self.reg_status.setStyleSheet("color: #F44336;")
            self.reg_status.setText("Passwords do not match.")
            return

        ok, msg = auth_manager.register(u, p)

        if ok:
            self.reg_status.setStyleSheet("color: #4CAF50;")
            self.reg_status.setText(msg)
            self.stack.setCurrentIndex(0)
            self.login_user.setText(u)
        else:
            self.reg_status.setStyleSheet("color: #F44336;")
            self.reg_status.setText(msg)

    # =========================
    # Window Dragging
    # =========================
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()