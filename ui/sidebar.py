"""Left sidebar navigation."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QScrollArea
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from core import config 

CATEGORIES = [
    ("🏠", "Dashboard", "dashboard"),
##    ("🤖", "AI Tools", "ai"),
    ("📚", "Study Tools", "study"),
    ("🎮", "Games", "games"),
    ("🔧", "Utility Tools", "utility"),
    ("📁", "File Tools", "file"),
    ("🎬", "Media Tools", "media"),
    ("🌐", "Networking", "network"),
    ("💻", "Developer Tools", "developer"),
    ("💰", "Finance", "finance"),
    ("🔒", "Security Tools", "security"),

]


class SidebarButton(QPushButton):
    def __init__(self, icon, label, tool_id):
        super().__init__(f"  {icon}  {label}")
        self.tool_id = tool_id
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #AAAAAA;
                border: none;
                border-radius: 6px;
                text-align: left;
                padding-left: 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #2D2D2D;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background: #1A3A35;
                color: #00BFA5;
                font-weight: bold;
                border-left: 3px solid #00BFA5;
            }
        """)


class Sidebar(QWidget):
    category_changed = Signal(str)
    logout_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet("background-color: #252526; border-right: 1px solid #3E3E3E;")
        self._buttons = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        # App name
        name_lbl = QLabel("⚙ MultiTool")
        name_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        name_lbl.setStyleSheet("color: #00BFA5; padding-left: 10px; margin-bottom: 12px;")
        layout.addWidget(name_lbl)

        for icon, label, cat_id in CATEGORIES:
            btn = SidebarButton(icon, label, cat_id)
            btn.clicked.connect(lambda checked, cid=cat_id: self._on_click(cid))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Version
        ver = QLabel(f"v{config.APP_VERSION}")
        ver.setStyleSheet("color: #555555; font-size: 11px; padding-left: 12px;")
        layout.addWidget(ver)

        # Logout button
        btn_logout = QPushButton("  🚪  Logout")
        btn_logout.setFixedHeight(40)
        btn_logout.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                border-radius: 6px;
                text-align: left;
                padding-left: 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3A1A1A;
                color: #F44336;
            }
        """)
        btn_logout.clicked.connect(self.logout_requested.emit)
        layout.addWidget(btn_logout)

        # Select dashboard by default
        self._buttons[0].setChecked(True)

    def _on_click(self, cat_id):
        for btn in self._buttons:
            btn.setChecked(btn.tool_id == cat_id)
        self.category_changed.emit(cat_id)
