"""Dashboard / home screen showing tool cards."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QGridLayout, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


TOOL_CARDS = {
#    "ai": [
#        ("🧠", "Face Reader", "Detect emotions from webcam", "face_reader"),
#        ("🎂", "Age Estimator", "Estimate age from face", "face_age"),
#        ("👤", "Face Detector", "Detect faces in images", "face_detector"),
#        ("📦", "Object Detector", "Detect objects in images", "object_detector"),
#    ],
    "study": [
        ("📚", "Lessons",          "Organize lessons & resources",      "study_lessons"),
        ("📊", "Exam Logging",     "Log TYT/AYT scores per subject",    "study_exams"),
        ("📝", "Test Capture",     "Capture questions with photos",      "study_tests"),
        ("📈", "Progress Tracker", "Charts for exam & study progress",  "study_progress"),
        ("🃏", "Flashcards",       "Spaced repetition flashcards",      "study_flashcards"),
        ("⏱️", "Study Timer",      "Pomodoro timer with logging",        "study_timer"),
        ("📖", "Resource Library", "Books, PDFs, links & videos",       "study_resources"),
        ("🎯", "Goals & Reminders","Set goals and track deadlines",      "study_goals"),
        ("📋", "Exam Detail",   "TYT/AYT detaylı sınav girişi",        "exam_detail"),
        ("📈", "Exam Progress", "Bölüm/konu bazlı ilerleme grafikleri", "exam_progress"),
    ],
    "games": [
        ("🔢", "Sudoku",        "Random puzzles — 4x4 to 16x16",    "sudoku"),
        ("🐍", "Snake",         "Classic snake with speed scaling",   "snake"),
        ("🐦", "Flappy Bird",   "Tap or Space to fly past pipes",     "flappy_bird"),
        ("✖️",  "Tic Tac Toe",  "Player vs Player or vs AI",          "tic_tac_toe"),
        ("💣", "Minesweeper",   "Easy / Medium / Hard mine grid",     "minesweeper"),
        ("🟦", "Tetris",        "Falling blocks, levels and scoring", "tetris"),
        ("⚡", "Reaction Time", "Measure your reaction in ms",        "reaction_time"),
        ("🃏", "Memory Match", "Card flip matching game", "memory_match"),
        ("🏓", "Pong",            "Classic paddle ball game",        "pong"),
        ("🔢", "2048",            "Merge tiles to reach 2048",       "game_2048"),
        ("🟦", "Block Blast",     "Clear block rows",                "block_blast"),
        ("🟩", "Wordle",          "Guess the 5-letter word",         "wordle"),
        ("🧱", "Breakout",        "Break bricks with a ball",        "breakout"),
        ("👾", "Space Invaders",  "Shoot down the alien invasion",   "space_invaders"),
        ("🔴", "Connect Four",    "Drop discs, connect 4 to win",    "connect_four"),
        ("👻", "Pac-Man",         "Eat dots, avoid ghosts",          "pac_man"),
    ],
    "utility": [
        ("📒", "Quick Notes",     "Fast notes with tags and images",    "notes_app"),
        ("🕐", "Clock",           "World clocks, stopwatch & alarms",   "clock_app"),
        ("✅", "Task Manager", "Lists, tasks, subtasks & deadlines", "task_manager"),
        ("📐", "Unit Converter",  "Length, weight, temp, currency…",    "unit_converter"),
        ("🎬", "Screen Recorder", "Record screen & export as GIF",      "screen_recorder"),
        ("📱", "QR Generator", "Generate QR codes from text", "qr_generator"),
        ("📷", "QR Scanner", "Decode QR codes from images", "qr_scanner"),
        ("🔑", "Password Generator", "Generate secure passwords", "password_generator"),
        ("🎲", "Random Number", "Generate random numbers", "random_number"),
        ("🔗", "UUID Generator", "Generate UUIDs", "uuid_generator"),
        ("🔢", "Calculator", "Calculator with history", "calculator"),
    ],
    "file": [
        ("🗂️", "File Manager",    "Browse, duplicate scan & cleaner",  "file_manager"),
        ("#️⃣", "File Hash", "MD5/SHA hash of files", "file_hash"),
        ("🔢", "Number Prefix", "Add number prefixes to filenames", "number_prefix"),
        ("✏️", "Batch Renamer", "Rename files in bulk", "batch_renamer"),
        ("📊", "Size Analyzer", "Analyze folder sizes", "file_size_analyzer"),
        ("📄", "Text Merger", "Merge text files", "text_merger"),
    ],
    "media": [
        ("🎵", "MP4 → MP3", "Extract audio from video", "mp4_to_mp3"),
        ("🎬", "Media Modernizer", "Convert 3gp/avi/bmp to mp4/png", "media_modernizer"),
        ("🖼️", "Image Converter", "Convert image formats", "image_converter"),
        ("📐", "Image Resizer", "Resize images in bulk", "image_resizer"),
    ],
    "network": [
        ("🌍", "IP Info", "Look up IP information", "ip_info"),
        ("✅", "Site Checker", "Check website status", "website_checker"),
        ("📡", "HTTP Tester", "Send HTTP requests", "http_tester"),
        ("🔗", "URL Shortener",      "Shorten or expand URLs",          "url_shortener"),
        ("📸", "Website Screenshot", "Capture screenshots of websites", "website_screenshot"),
        ("🔍", "Port Scanner",       "Multithreaded TCP port scanner",  "port_scanner"),
    ],
    "developer": [
        ("🖼️", "Image ↔ Base64", "Convert images to Base64 and back", "image_base64"),
        ("🗄️",  "SQL Studio",  "SQLite DB manager — query, browse, export", "sql_studio"),
        ("🎨", "Color Picker", "HEX/RGB/HSL + palette generator",           "color_picker"),
        ("📋", "JSON Formatter", "Format and validate JSON", "json_formatter"),
        ("🔄", "Base64", "Encode/decode Base64", "base64_tool"),
        ("🕒", "Timestamp", "Convert Unix timestamps", "timestamp_converter"),
    ],
    "finance": [
        ("🏠", "Finance Dashboard",    "Central finance overview",          "finance_dashboard"),
        ("💸", "Expense Tracker",       "Track income and expenses",         "expense_tracker"),
        ("💰", "Budget App",            "Set and track spending limits",     "budget_app"),
        ("📊", "Spending Analyzer",     "Analyze spending patterns",         "spending_analyzer"),
        ("💵", "Cash Flow",             "Track money movement over time",    "cash_flow_tool"),
        ("📦", "Net Worth",             "Assets minus liabilities",          "net_worth_tracker"),
        ("📈", "Portfolio Tracker",     "Track stocks and investments",      "portfolio_tracker"),
        ("🪙", "Crypto Tracker",        "Track crypto holdings",             "crypto_tracker"),
        ("💳", "Subscriptions",         "Recurring payment tracker",         "subscription_tracker"),
        ("🔔", "Bill Reminder",         "Track due dates and bills",         "bill_reminder"),
        ("📉", "Debt Tracker",          "Track loans and balances",          "debt_tracker"),
        ("🏦", "Loan Calculator",       "Amortization and payments",         "loan_calculator"),
        ("💾", "Savings Tracker",       "Track savings toward goals",        "savings_tracker"),
        ("🎯", "Goal Planner",          "Define and track financial goals",  "goal_planner"),
        ("📊", "Investment Simulator",  "Simulate investment growth",        "investment_simulator"),
        ("🧮", "Tax Calculator",        "Estimate income tax",               "tax_calculator"),
        ("🧾", "Invoice Tool",          "Create and export invoices",        "invoice_tool"),
        ("🌍", "Currency Converter",    "Live exchange rates",               "currency_converter"),
        ("📷", "Receipt Scanner",       "Extract expenses from images",      "receipt_scanner"),
    ],
    "security": [
        ("🔐", "Password Vault", "Secure password manager", "password_vault"),
        ("📓", "Notebook", "Encrypted notes per person", "notebook"),
    ],
}

ALL_TOOLS = []
for cat, tools in TOOL_CARDS.items():
    for t in tools:
        ALL_TOOLS.append((t[0], t[1], t[2], t[3], cat))


class ToolCard(QFrame):
    clicked = Signal(str)

    def __init__(self, icon, name, desc, tool_id):
        super().__init__()
        self.tool_id = tool_id
        self.setFixedSize(180, 110)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background: #2D2D2D;
                border: 1px solid #3E3E3E;
                border-radius: 10px;
            }
            QFrame:hover {
                border: 1px solid #00BFA5;
                background: #1A3A35;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        name_lbl.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        layout.addWidget(name_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent;")
        layout.addWidget(desc_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.tool_id)


class Dashboard(QWidget):
    tool_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel("Welcome to MultiTool Studio")
        header.setFont(QFont("Segoe UI", 22, QFont.Bold))
        header.setStyleSheet("color: #00BFA5;")
        layout.addWidget(header)

        sub = QLabel(f"Your all-in-one productivity toolbox  •  {len(ALL_TOOLS)} tools available")
        sub.setStyleSheet("color: #888888; font-size: 13px;")
        layout.addWidget(sub)

        # Stats row
        stats = QHBoxLayout()
        for count, label, color in [
            (len(ALL_TOOLS), "Total Tools", "#00BFA5"),
            (4, "AI Tools", "#9C27B0"),
            (1, "Security Tools", "#F44336"),
            (3, "Media Tools", "#FF9800"),
        ]:
            card = QFrame()
            card.setFixedHeight(70)
            card.setStyleSheet(f"background: #252526; border: 1px solid {color}; border-radius: 8px; padding: 8px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            n = QLabel(str(count))
            n.setFont(QFont("Segoe UI", 20, QFont.Bold))
            n.setStyleSheet(f"color: {color}; border: none;")
            cl.addWidget(n)
            l = QLabel(label)
            l.setStyleSheet("color: #888888; font-size: 11px; border: none;")
            cl.addWidget(l)
            stats.addWidget(card)
        layout.addLayout(stats)

        # All tools grid
        grid_label = QLabel("All Tools")
        grid_label.setFont(QFont("Segoe UI", 15, QFont.Bold))
        grid_label.setStyleSheet("color: #CCCCCC; margin-top: 8px;")
        layout.addWidget(grid_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 0, 0)

        for i, (icon, name, desc, tool_id, cat) in enumerate(ALL_TOOLS):
            card = ToolCard(icon, name, desc, tool_id)
            card.clicked.connect(self.tool_selected.emit)
            grid.addWidget(card, i // 5, i % 5)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)


class CategoryView(QWidget):
    """Shows tools filtered by category."""
    tool_selected = Signal(str)

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self.category = category
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        tools = TOOL_CARDS.get(self.category, [])
        cat_names = {
            "ai": "🤖 AI Tools",
            "study": "📚 Study Tools",
            "games": "🎮 Games",
            "utility": "🔧 Utility Tools",
            "file": "📁 File Tools",
            "media": "🎬 Media Tools",
            "network": "🌐 Networking Tools",
            "developer": "💻 Developer Tools",
            "finance": "💰 Finance",
            "security": "🔒 Security Tools",
            
        }
        header = QLabel(cat_names.get(self.category, "Tools"))
        header.setFont(QFont("Segoe UI", 20, QFont.Bold))
        header.setStyleSheet("color: #00BFA5;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        for i, (icon, name, desc, tool_id) in enumerate(tools):
            card = ToolCard(icon, name, desc, tool_id)
            card.clicked.connect(self.tool_selected.emit)
            grid.addWidget(card, i // 4, i % 4)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)
