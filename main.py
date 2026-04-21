"""MultiTool Studio — Application Entry Point"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QEventLoop

from database.database import init_database
from ui.theme import STYLESHEET
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def run_login(app: QApplication, stylesheet: str) -> bool:
    """Show the login dialog. Returns True if the user authenticated."""
    login = LoginWindow()
    login.setStyleSheet(stylesheet)
    return login.exec() == LoginWindow.Accepted


def run_main_window(app: QApplication, stylesheet: str):
    """Show the main window. Returns True if user logged out, False if closed."""
    window = MainWindow()
    window.setStyleSheet(stylesheet)
    window.showMaximized()

    _logout_triggered = [False]
    loop = QEventLoop()

    def on_logout():
        _logout_triggered[0] = True
        window.hide()
        window.close()
        loop.quit()

    def on_close():
        loop.quit()

    window.set_logout_callback(on_logout)
    window.set_close_callback(on_close)

    loop.exec()

    return _logout_triggered[0]


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MultiTool Studio")
    app.setApplicationVersion("1.0.0")
    app.setStyleSheet(STYLESHEET)
    app.setQuitOnLastWindowClosed(False)

    try:
        init_database()
    except Exception as e:
        QMessageBox.critical(None, "Fatal Error", f"Could not initialize database:\n{e}")
        app.quit()
        sys.exit(1)

    while True:
        if not run_login(app, STYLESHEET):
            app.quit()
            sys.exit(0)

        logged_out = run_main_window(app, STYLESHEET)

        if not logged_out:
            app.quit()
            sys.exit(0)
        # logged out → loop back to login


if __name__ == "__main__":
    main()