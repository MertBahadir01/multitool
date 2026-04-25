"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QSizePolicy, QStatusBar, QMessageBox, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QAction, QKeySequence, QShortcut, QIcon, QKeyEvent
from ui.sidebar import Sidebar
from ui.dashboard import Dashboard, CategoryView
from core.auth_manager import auth_manager
import os
from core import config

TOOL_REGISTRY = {}


class ToolFrame(QWidget):
    """Thin chrome wrapper placed around every tool widget.

    Adds a consistent header bar containing:
      • ← Back button (top-left, before the tool name)
      • Tool name label
    The inner tool widget fills the remaining space unchanged.
    """

    back_requested = Signal()

    _BACK_CSS = """
        QPushButton {
            background: transparent;
            color: #888888;
            border: 1px solid #3E3E3E;
            border-radius: 6px;
            padding: 4px 14px;
            font-size: 13px;
        }
        QPushButton:hover {
            background: #1A3A35;
            color: #00BFA5;
            border: 1px solid #00BFA5;
        }
        QPushButton:pressed {
            background: #0D2D28;
        }
    """

    def __init__(self, tool_widget: QWidget, tool_name: str, parent=None):
        super().__init__(parent)
        self._tool_widget = tool_widget

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background: #1E1E1E; border-bottom: 1px solid #2D2D2D;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        h_lay.setSpacing(12)

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setToolTip("Go back to categories  (ESC / Backspace)")
        back_btn.setStyleSheet(self._BACK_CSS)
        back_btn.clicked.connect(self.back_requested.emit)
        h_lay.addWidget(back_btn)

        name_lbl = QLabel(tool_name)
        name_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        name_lbl.setStyleSheet("color: #CCCCCC; background: transparent;")
        h_lay.addWidget(name_lbl)
        h_lay.addStretch()

        root.addWidget(header)
        root.addWidget(tool_widget, stretch=1)


def _register_tools():
    """Import all tool widget classes."""
    global TOOL_REGISTRY
    tool_modules = [
        ("qr_generator", "tools.qr_generator", "QRGeneratorTool"),
        ("qr_scanner", "tools.qr_scanner", "QRScannerTool"),
        ("password_generator", "tools.password_generator", "PasswordGeneratorTool"),
        ("random_number", "tools.random_number", "RandomNumberTool"),
        ("uuid_generator", "tools.uuid_generator", "UUIDGeneratorTool"),
        ("file_hash", "tools.file_hash", "FileHashTool"),
        ("batch_renamer", "tools.batch_renamer", "BatchRenamerTool"),
        ("file_size_analyzer", "tools.file_size_analyzer", "FileSizeAnalyzerTool"),
        ("text_merger", "tools.text_merger", "TextMergerTool"),
        ("mp4_to_mp3", "tools.mp4_to_mp3", "MP4ToMP3Tool"),
        ("image_converter", "tools.image_converter", "ImageConverterTool"),
        ("image_resizer", "tools.image_resizer", "ImageResizerTool"),
        ("ip_info", "tools.ip_info", "IPInfoTool"),
        ("website_checker", "tools.website_checker", "WebsiteCheckerTool"),
        ("http_tester", "tools.http_tester", "HTTPTesterTool"),
        ("json_formatter", "tools.json_formatter", "JSONFormatterTool"),
        ("base64_tool", "tools.base64_tool", "Base64Tool"),
        ("timestamp_converter", "tools.timestamp_converter", "TimestampConverterTool"),
#        ("face_reader", "tools.face_reader", "FaceReaderTool"),
#        ("face_age", "tools.face_age", "FaceAgeTool"),
#        ("face_detector", "tools.face_detector", "FaceDetectorTool"),
#        ("object_detector", "tools.object_detector", "ObjectDetectorTool"),
        ("password_vault", "tools.password_vault", "PasswordVaultTool"),
        ("notebook",           "tools.notebook",          "NotebookTool"),
        ("calculator",         "tools.calculator",        "CalculatorTool"),
        ("study_lessons",      "tools.study_lessons",     "StudyLessonsTool"),
        ("study_exams",        "tools.study_exams",       "StudyExamsTool"),
        ("study_tests",        "tools.study_tests",       "StudyTestsTool"),
        ("study_progress",     "tools.study_progress",    "StudyProgressTool"),
        ("study_flashcards",   "tools.study_flashcards",  "StudyFlashcardsTool"),
        ("study_timer",        "tools.study_timer",       "StudyTimerTool"),
        ("study_resources",    "tools.study_resources",   "StudyResourcesTool"),
        ("study_goals",        "tools.study_goals",       "StudyGoalsTool"),
        ("clock_app",       "tools.clock_app",       "ClockTool"),
        ("notes_app",       "tools.notes_app",       "NotesApp"),
        ("unit_converter",  "tools.unit_converter",  "UnitConverterTool"),
        ("file_manager",    "tools.file_manager",    "FileManagerTool"),
        ("screen_recorder", "tools.screen_recorder", "ScreenRecorderTool"),
        ("exam_detail",    "tools.exam_detail",    "ExamDetailTool"),
        ("exam_progress",  "tools.exam_progress",  "ExamProgressTool"),
        ("task_manager", "tools.task_manager", "TaskManagerTool"),
        ("image_base64", "tools.image_base64", "ImageBase64Tool"),
        ("sudoku",        "tools.sudoku",         "SudokuTool"),
        ("snake",         "tools.snake",           "SnakeTool"),
        ("flappy_bird",   "tools.flappy_bird",     "FlappyBirdTool"),
        ("tic_tac_toe",   "tools.tic_tac_toe",     "TicTacToeTool"),
        ("minesweeper",   "tools.minesweeper",     "MinesweeperTool"),
        ("tetris",        "tools.tetris",           "TetrisTool"),
        ("reaction_time", "tools.reaction_time",   "ReactionTimeTool"),
        ("memory_match", "tools.memory_match", "MemoryMatchTool"),
        ("pong",           "tools.pong",           "PongTool"),
        ("game_2048",      "tools.game_2048",       "Game2048Tool"),
        ("block_blast",    "tools.block_blast",     "BlockBlastTool"),
        ("wordle",         "tools.wordle",           "WordleTool"),
        ("breakout",       "tools.breakout",         "BreakoutTool"),
        ("space_invaders", "tools.space_invaders",   "SpaceInvadersTool"),
        ("connect_four",   "tools.connect_four",     "ConnectFourTool"),
        ("pac_man",        "tools.pac_man",           "PacManTool"),
        ("finance_dashboard",    "tools.finance_dashboard",    "FinanceDashboardTool"),
        ("expense_tracker",      "tools.expense_tracker",      "ExpenseTrackerTool"),
        ("budget_app",           "tools.budget_app",           "BudgetAppTool"),
        ("spending_analyzer",    "tools.spending_analyzer",    "SpendingAnalyzerTool"),
        ("cash_flow_tool",       "tools.cash_flow_tool",       "CashFlowTool"),
        ("net_worth_tracker",    "tools.net_worth_tracker",    "NetWorthTrackerTool"),
        ("portfolio_tracker",    "tools.portfolio_tracker",    "PortfolioTrackerTool"),
        ("crypto_tracker",       "tools.crypto_tracker",       "CryptoTrackerTool"),
        ("subscription_tracker", "tools.subscription_tracker", "SubscriptionTrackerTool"),
        ("bill_reminder",        "tools.bill_reminder",        "BillReminderTool"),
        ("debt_tracker",         "tools.debt_tracker",         "DebtTrackerTool"),
        ("loan_calculator",      "tools.loan_calculator",      "LoanCalculatorTool"),
        ("savings_tracker",      "tools.savings_tracker",      "SavingsTrackerTool"),
        ("goal_planner",         "tools.goal_planner",         "GoalPlannerTool"),
        ("investment_simulator", "tools.investment_simulator", "InvestmentSimulatorTool"),
        ("tax_calculator",       "tools.tax_calculator",       "TaxCalculatorTool"),
        ("invoice_tool",         "tools.invoice_tool",         "InvoiceTool"),
        ("currency_converter",   "tools.currency_converter",   "CurrencyConverterTool"),
        ("receipt_scanner",      "tools.receipt_scanner",      "ReceiptScannerTool"),
        ("media_modernizer", "tools.media_modernizer", "MediaModernizerTool"),
        ("number_prefix", "tools.number_prefix", "NumberPrefixTool"),
        ("url_shortener",      "tools.url_shortener",      "URLShortenerTool"),
        ("website_screenshot", "tools.website_screenshot", "WebsiteScreenshotTool"),
        ("port_scanner",       "tools.port_scanner",       "PortScannerTool"),
        ("sql_studio",         "tools.sql_studio",         "SQLStudioTool"),
        ("color_picker",       "tools.color_picker",       "ColorPickerTool"),
        ("smart_file_organizer",     "tools.smart_file_organizer",     "SmartFileOrganizerTool"),
        ("duplicate_file_finder",    "tools.duplicate_file_finder",    "DuplicateFileFinderTool"),
        ("clipboard_manager",        "tools.clipboard_manager",        "ClipboardManagerTool"),
        ("text_expander",            "tools.text_expander",            "TextExpanderTool"),
        ("password_strength_analyzer","tools.password_strength_analyzer","PasswordStrengthAnalyzerTool"),
        ("file_encryptor",           "tools.file_encryptor",           "FileEncryptorTool"),
        ("port_monitor_live",        "tools.port_monitor_live",        "PortMonitorLiveTool"),
        ("regex_tester",             "tools.regex_tester",             "RegexTesterTool"),
        ("diff_checker",             "tools.diff_checker",             "DiffCheckerTool"),
        ("habit_tracker",            "tools.habit_tracker",            "HabitTrackerTool"),
        ("focus_mode",               "tools.focus_mode",               "FocusModeTool"),
        ("typing_speed_test",        "tools.typing_speed_test",        "TypingSpeedTestTool"),
        ("data_chart_builder",       "tools.data_chart_builder",       "DataChartBuilderTool"),
        ("website_change_tracker",   "tools.website_change_tracker",   "WebsiteChangeTrackerTool"),
        ("tcp_udp_tool",      "tools.tcp_udp_tool",      "TCPUDPTool"),
        ("lan_file_transfer", "tools.lan_file_transfer",  "LANFileTransferTool"),
        ("db_file_storage",   "tools.db_file_storage",    "DBFileStorageTool"),
        ("youtube_downloader", "tools.youtube_downloader", "YouTubeDownloaderTool")
    ]
    import importlib
    for tool_id, module_path, class_name in tool_modules:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            TOOL_REGISTRY[tool_id] = cls
        except Exception as e:
            print(f"[MainWindow] Could not load {tool_id}: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        icon_path = os.path.join(os.path.dirname(__file__), "..", "icom.ico")
        self.setWindowIcon(QIcon(icon_path))

        _register_tools()
        self.setWindowTitle("MultiTool Studio")
        self.setMinimumSize(1200, 750)
        self._current_tool_widget = None
        self._tool_cache = {}
        self._logout_callback = None
        self._close_callback = None
        self._current_category = None   # tracks which category is active
        self._build_ui()
        self._setup_statusbar()
        self._setup_fullscreen_shortcut()
        self._setup_navigation_shortcuts()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.category_changed.connect(self._on_category)
        self.sidebar.logout_requested.connect(self._on_logout_requested)
        layout.addWidget(self.sidebar)

        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)

        # Dashboard
        self.dashboard = Dashboard()
        self.dashboard.tool_selected.connect(self._open_tool)
        self.content_stack.addWidget(self.dashboard)

        # Tool container (index 1)
        self.tool_container = QStackedWidget()
        self.content_stack.addWidget(self.tool_container)

        self.content_stack.setCurrentIndex(0)

    def _setup_statusbar(self):
        sb = self.statusBar()
        user = auth_manager.current_user
        username = user["username"] if user else "Guest"
        self._status_lbl = QLabel(f"  👤 Logged in as: {username}   |   ⚙ {config.APP_NAME} v{config.APP_VERSION}")
        self._status_lbl.setStyleSheet("color: #888888;")
        sb.addWidget(self._status_lbl)

    def _setup_fullscreen_shortcut(self):
        """Bind F11 to toggle maximized / normal window state."""
        shortcut = QShortcut(QKeySequence("F11"), self)
        shortcut.activated.connect(self._toggle_fullscreen)

    def _setup_navigation_shortcuts(self):
        """Bind ESC to always go back; Backspace goes back only when no input is focused."""
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.activated.connect(self._go_back)

    # ------------------------------------------------------------------
    # Full-screen helpers
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _go_back(self):
        """Return from an open tool to its parent category view, or from a
        category view back to the dashboard.  All three back-navigation
        methods (ESC, Backspace, Back button) call this single method."""
        if self.content_stack.currentIndex() == 0:
            return  # already on dashboard — nothing to do

        current_widget = self.tool_container.currentWidget()

        # If the current widget is a CategoryView, return to dashboard
        if isinstance(current_widget, CategoryView):
            self.content_stack.setCurrentIndex(0)
            self._current_category = None
            return

        # Otherwise it's a ToolFrame — return to the category view if one is cached
        if self._current_category:
            cat_key = f"cat_{self._current_category}"
            if cat_key in self._tool_cache:
                self.tool_container.setCurrentWidget(self._tool_cache[cat_key])
                self.content_stack.setCurrentIndex(1)
                return

        # Fallback: no category context — go all the way to dashboard
        self.content_stack.setCurrentIndex(0)
        self._current_category = None

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_category(self, cat_id):
        if cat_id == "dashboard":
            self.content_stack.setCurrentIndex(0)
            self._current_category = None
        else:
            self._current_category = cat_id
            cat_key = f"cat_{cat_id}"
            if cat_key not in self._tool_cache:
                cv = CategoryView(cat_id)
                cv.tool_selected.connect(self._open_tool)
                cv.back_requested.connect(self._go_back)
                self._tool_cache[cat_key] = cv
                self.tool_container.addWidget(cv)
            self.tool_container.setCurrentWidget(self._tool_cache[cat_key])
            self.content_stack.setCurrentIndex(1)

    def _open_tool(self, tool_id: str):
        if tool_id not in TOOL_REGISTRY:
            QMessageBox.information(self, "Tool", f"Tool '{tool_id}' is not yet available.")
            return
        if tool_id not in self._tool_cache:
            try:
                cls = TOOL_REGISTRY[tool_id]
                widget = cls()
                tool_name = getattr(cls, "name", tool_id)
                frame = ToolFrame(widget, tool_name)
                frame.back_requested.connect(self._go_back)
                self._tool_cache[tool_id] = frame
                self.tool_container.addWidget(frame)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not load tool: {e}")
                return
        self._current_tool_widget = self._tool_cache[tool_id]
        self.tool_container.setCurrentWidget(self._tool_cache[tool_id])
        self.content_stack.setCurrentIndex(1)
        tool_name = getattr(TOOL_REGISTRY[tool_id], "name", tool_id)
        self.statusBar().showMessage(f"  📂 {tool_name}", 3000)

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def set_logout_callback(self, callback):
        """Register the function main.py should call to show login again."""
        self._logout_callback = callback

    def set_close_callback(self, callback):
        """Register the function main.py should call when window is closed normally."""
        self._close_callback = callback

    def _on_logout_requested(self):
        """Ask for confirmation, then perform logout."""
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._do_logout()

    def _do_logout(self):
        """Clear all tool state, wipe session, and hand control back to main."""
        # Reset content to dashboard so no protected tool remains visible
        self.content_stack.setCurrentIndex(0)

        # Destroy every cached widget (ToolFrame wrappers + CategoryViews)
        for widget in self._tool_cache.values():
            try:
                self.tool_container.removeWidget(widget)
                widget.hide()
                widget.deleteLater()
            except Exception:
                pass
        self._tool_cache.clear()
        self._current_tool_widget = None
        self._current_category = None

        # Clear auth session (also fires any registered callbacks)
        auth_manager.logout()

        # Delegate back to main.py to show login window
        if self._logout_callback:
            self._logout_callback()

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        super().closeEvent(event)
        if self._close_callback:
            self._close_callback()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle Backspace for back-navigation when no text input is focused."""
        if event.key() == Qt.Key_Backspace:
            focused = self.focusWidget()
            # Only navigate back if focus is NOT on a typing widget
            if focused is None or not self._is_input_widget(focused):
                self._go_back()
                return
        super().keyPressEvent(event)

    @staticmethod
    def _is_input_widget(widget) -> bool:
        """Return True if the widget is a text-entry field where Backspace should type."""
        from PySide6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox
        return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox))