"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QLabel, QSizePolicy, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QAction
from ui.sidebar import Sidebar
from ui.dashboard import Dashboard, CategoryView
from core.auth_manager import auth_manager


TOOL_REGISTRY = {}


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
        _register_tools()
        self.setWindowTitle("MultiTool Studio")
        self.setMinimumSize(1200, 750)
        self._current_tool_widget = None
        self._tool_cache = {}
        self._build_ui()
        self._setup_statusbar()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.category_changed.connect(self._on_category)
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
        self._status_lbl = QLabel(f"  👤 Logged in as: {username}   |   ⚙ MultiTool Studio v1.0.0")
        self._status_lbl.setStyleSheet("color: #888888;")
        sb.addWidget(self._status_lbl)

    def _on_category(self, cat_id):
        if cat_id == "dashboard":
            self.content_stack.setCurrentIndex(0)
        else:
            # Show category view
            cat_key = f"cat_{cat_id}"
            if cat_key not in self._tool_cache:
                cv = CategoryView(cat_id)
                cv.tool_selected.connect(self._open_tool)
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
                self._tool_cache[tool_id] = widget
                self.tool_container.addWidget(widget)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not load tool: {e}")
                return
        self.tool_container.setCurrentWidget(self._tool_cache[tool_id])
        self.content_stack.setCurrentIndex(1)
        tool_name = getattr(TOOL_REGISTRY[tool_id], "name", tool_id)
        self.statusBar().showMessage(f"  📂 {tool_name}", 3000)

    def closeEvent(self, event):
        super().closeEvent(event)
