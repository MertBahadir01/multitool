"""MultiTool Studio — Application Entry Point"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor

from database.database import init_database
from ui.theme import STYLESHEET
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MultiTool Studio")
    app.setApplicationVersion("1.0.0")
    app.setStyleSheet(STYLESHEET)

    # Initialize database
    try:
        init_database()
    except Exception as e:
        QMessageBox.critical(None, "Fatal Error", f"Could not initialize database:\n{e}")
        sys.exit(1)

    # Show login
    login = LoginWindow()
    login.setStyleSheet(STYLESHEET)

    if login.exec() != LoginWindow.Accepted:
        sys.exit(0)

    # Show main window
    window = MainWindow()
    window.setStyleSheet(STYLESHEET)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
