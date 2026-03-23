# ⚙️ MultiTool Studio

**A modern, modular desktop productivity suite built with Python & PySide6.**

100+ integrated tools across 12 categories — AI, Finance, Games, Study, Utilities, and more — in a single dark-themed application with secure authentication, encrypted storage, live API data, and a plugin-based architecture.

---

## 📸 Overview

MultiTool Studio is a desktop application that replaces a dozen separate apps with one unified workspace. Every tool shares the same dark UI, user account, and database, while remaining independently usable. New tools can be dropped in as folders without touching the core code.

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/yourname/multitool_studio
cd multitool_studio

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

### Requirements

| Package | Version | Purpose |
|---|---|---|
| PySide6 | ≥ 6.5.0 | UI framework |
| opencv-python | ≥ 4.8.0 | AI / webcam tools |
| mediapipe | ≥ 0.10.0 | Face & gesture AI |
| qrcode[pil] | ≥ 7.4.2 | QR generation |
| Pillow | ≥ 10.0.0 | Image processing |
| numpy | ≥ 1.24.0 | Numerical operations |
| pandas | ≥ 2.0.0 | Data handling |
| requests | ≥ 2.31.0 | API calls (finance, currency) |
| bcrypt | ≥ 4.0.0 | Password hashing |
| cryptography | ≥ 41.0.0 | Note / vault encryption |

**Optional:**
```bash
pip install pytesseract pillow   # Receipt Scanner OCR
# + Tesseract-OCR: https://github.com/UB-Mannheim/tesseract/wiki
```

---

## 🗂️ Project Structure

```
multitool_studio/
├── main.py                  # Entry point
├── requirements.txt
├── multitool_studio.db      # SQLite database (auto-created)
│
├── core/
│   ├── auth_manager.py      # Login / session (auth_manager singleton)
│   ├── config.py            # APP_NAME, DB_PATH, colors, constants
│   └── plugin_manager.py    # TOOL_REGISTRY — auto-discovers tools
│
├── database/
│   └── database.py          # init_database(), get_connection()
│
├── services/
│   └── encryption_service.py  # encrypt(text, key) / decrypt(text, key)
│
├── ui/
│   ├── main_window.py       # MainWindow + tool_modules registry list
│   ├── dashboard.py         # TOOL_CARDS dict + CategoryView
│   ├── sidebar.py           # CATEGORIES list
│   ├── login_window.py      # Login / register screen
│   └── theme.py             # Global stylesheet
│
└── tools/                   # Every tool is a self-contained folder
    ├── <tool_name>/
    │   ├── __init__.py      # TOOL_META dict (required)
    │   └── <tool_name>_tool.py
    └── ...
```

---

## 🔌 Plugin Architecture

Every tool is a folder under `tools/`. The system auto-discovers any folder with a valid `__init__.py`.

### `__init__.py` format (required)

```python
from .my_tool import MyTool

TOOL_META = {
    "id":           "my_tool",
    "name":         "My Tool",
    "category":     "utility",   # must match a key in TOOL_CARDS
    "widget_class": MyTool,
}
```

### Tool widget pattern

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout

class MyTool(QWidget):
    name        = "My Tool"
    description = "What it does"

    def __init__(self, parent=None):
        super().__init__(parent)
        # build UI here
```

### Registering a new tool (3 steps)

1. Drop the folder into `tools/`
2. Add to `tool_modules` in `ui/main_window.py`:
   ```python
   ("my_tool", "tools.my_tool", "MyTool"),
   ```
3. Add to the correct category list in `ui/dashboard.py`:
   ```python
   ("🔧", "My Tool", "What it does", "my_tool"),
   ```

---

## 🧰 Tools Reference

### 🤖 AI Tools

| Tool | Description |
|---|---|
| 🧠 Face Reader | Detect emotions in real time from webcam |
| 🎂 Age Estimator | Estimate age from a face image |
| 👤 Face Detector | Locate and highlight faces in images |
| 📦 Object Detector | Detect and label objects in images |

### 🔧 Utility Tools

| Tool | Description |
|---|---|
| 📱 QR Generator | Generate QR codes from any text or URL |
| 📷 QR Scanner | Decode QR codes from image files |
| 🔑 Password Generator | Customisable secure password generator |
| 🎲 Random Number | Random integers or floats with range control |
| 🔗 UUID Generator | Generate v4 UUIDs |
| 🕐 Clock | World clocks, stopwatch, countdown, alarms |
| 📒 Quick Notes | Fast DB-backed notes with tags and image attachments |
| 📐 Unit Converter | Length, weight, temperature, currency, and more |
| 🗂️ File Manager | Browse, duplicate finder, large-file scanner |
| 🎬 Screen Recorder | Record screen, export as GIF (requires ffmpeg) |
| ✅ Task Manager | Lists, tasks, subtasks, priorities, due dates |

### 📁 File Tools

| Tool | Description |
|---|---|
| #️⃣ File Hash | MD5 / SHA-256 / SHA-512 hash of any file |
| ✏️ Batch Renamer | Rename files in bulk with pattern rules |
| 📊 Size Analyzer | Folder size breakdown with chart |
| 📄 Text Merger | Concatenate multiple text files |

### 🎬 Media Tools

| Tool | Description |
|---|---|
| 🎵 MP4 → MP3 | Extract audio track from video |
| 🖼️ Image Converter | Convert between PNG, JPG, WEBP, BMP, etc. |
| 📐 Image Resizer | Bulk resize images to target dimensions |

### 🌐 Networking

| Tool | Description |
|---|---|
| 🌍 IP Info | Look up geolocation and ISP for any IP |
| ✅ Site Checker | Check HTTP status of any URL |
| 📡 HTTP Tester | Send GET/POST/PUT/DELETE requests, view response |

### 💻 Developer Tools

| Tool | Description |
|---|---|
| 📋 JSON Formatter | Format, validate and minify JSON |
| 🔄 Base64 | Encode / decode Base64 strings |
| 🕒 Timestamp | Convert Unix timestamps to human dates |
| 🖼️ Image ↔ Base64 | Encode images to Base64 or decode back |

### 🔒 Security Tools

| Tool | Description |
|---|---|
| 🔐 Password Vault | Encrypted credential manager (bcrypt + AES) |
| 📓 Notebook | Encrypted hierarchical notes (categories → people → notes) |

### 📚 Study Tools

| Tool | Description |
|---|---|
| 📖 Study Lessons | Lesson library with progress tracking |
| 📝 Study Exams | Exam scheduling and result logging |
| 🧪 Study Tests | Practice tests with scoring |
| 📊 Study Progress | Visual progress dashboard |
| 🃏 Study Flashcards | Spaced-repetition flashcard deck |
| ⏱️ Study Timer | Pomodoro-style focus timer |
| 📚 Study Resources | Resource links and notes organiser |
| 🎯 Study Goals | Goal setting with deadline tracking |
| 📋 Exam Detail | Per-subject score entry (TYT / AYT / YDT) |
| 📈 Exam Progress | Charts: trend, heatmap, weak topics |

### 🎮 Games (with global leaderboard)

| Tool | Description |
|---|---|
| 🔢 Sudoku | 4×4 / 9×9 / 16×16, Easy–Expert difficulty |
| 🐍 Snake | Classic snake, speed scales with score |
| 🐦 Flappy Bird | Tap / Space to fly, pipe score tracking |
| ✖️ Tic Tac Toe | PvP or vs unbeatable minimax AI |
| 💣 Minesweeper | Easy / Medium / Hard, first-click safety |
| 🟦 Tetris | All 7 tetrominoes, wall-kick rotation, levels |
| ⚡ Reaction Time | Millisecond-precision reaction test |
| 🃏 Memory Match | Card-flip matching game, 4×4 / 4×5 / 6×6 |
| 🏓 Pong | Player vs AI, ball speed increases |
| 🔢 2048 | Sliding tile puzzle, 4×4 grid |
| 💥 Block Blast | Drag-and-drop block placement, clear rows |
| 🟩 Wordle | Turkish (default) + English, 6 attempts, on-screen keyboard |
| 🧱 Breakout | Paddle + ball + brick grid, levels |
| 👾 Space Invaders | Alien grid, alien fire, levels |
| 🔴 Connect Four | PvP or vs alpha-beta minimax AI |
| 👻 Pac-Man | Full maze, dots, power pellets, 4 ghosts |

All games share a single `game_scores` table — every score is attributed to the logged-in user and shown in a global leaderboard panel inside each game.

### 💰 Finance Tools

All finance tools are in Turkish, share 8 DB tables, and pull live data from free APIs (no API key needed).

| Tool | Description |
|---|---|
| 🏠 Finance Dashboard | Combined KPI cards, cash flow chart, budget and savings overview |
| 💸 Expense Tracker | Add / delete transactions, category breakdown, monthly trend |
| 📊 Budget App | Per-category monthly limits with live progress bars |
| 🏦 Loan Calculator | Monthly payment, full amortisation schedule, balance vs interest chart |
| 🎯 Savings Tracker | Named goals, progress bars, months-to-goal estimate |
| 📈 Portfolio Tracker | Stock holdings, live Yahoo Finance prices, P&L, 6-month chart |
| 🔔 Subscription Tracker | Recurring billing, monthly/yearly cost rollup |
| 💱 Currency Converter | TRY-based live rates (exchangerate-api), 1-year chart |
| 🧾 Invoice Tool | Line items, KDV (VAT) calculation, PDF export |
| 🧾 Tax Calculator | Turkish 2024 income tax brackets, per-bracket breakdown |
| ₿ Crypto Tracker | CoinGecko live prices, 90-day chart, TRY conversion |
| 🔍 Spending Analyzer | Category heatmap, period filter, trend chart |
| 💎 Net Worth Tracker | Assets minus liabilities |
| 📅 Bill Reminder | Due-date alerts, overdue highlighting, paid toggle |
| 📊 Investment Simulator | Compound growth with monthly contributions |
| 💳 Debt Tracker | Remaining balance, monthly payment, payoff timeline |
| 🏖️ Retirement Planner | Age-based projection, sustainability estimate |
| 💹 Cash Flow | Monthly income / expense / net with dual charts |
| 🎯 Goal Planner | Financial targets with deadline countdown |
| 🧾 Receipt Scanner | pytesseract OCR from photo, auto-extract amount, save to expenses |

**Finance APIs (all free, no key):**
- Exchange rates: `api.exchangerate-api.com`
- Crypto prices: `api.coingecko.com`
- Stock history: `query1.finance.yahoo.com`

All API calls run in background threads — the UI never freezes.

---

## 🗄️ Database

SQLite (`multitool_studio.db`), auto-created on first run via `init_database()`.

| Table | Used by |
|---|---|
| `users` | Auth |
| `password_vault` | Password Vault |
| `app_settings` | Global settings |
| `notebook_categories / people / notes / note_images` | Notebook |
| `calculator_history` | Calculator |
| `quick_notes / note_images` | Quick Notes |
| `task_lists / tasks / task_subtasks` | Task Manager |
| `game_scores` | All 16 games |
| `fin_transactions` | Expense Tracker, Cash Flow, Spending Analyzer, Dashboard |
| `fin_budgets` | Budget App, Dashboard |
| `fin_savings` | Savings Tracker, Goal Planner, Dashboard |
| `fin_assets` | Portfolio Tracker, Crypto Tracker |
| `fin_subscriptions` | Subscription Tracker |
| `fin_debts` | Debt Tracker |
| `fin_net_worth` | Net Worth Tracker |
| `fin_bills` | Bill Reminder |

---

## 🔐 Security

Sensitive data is encrypted at rest using the `cryptography` library (Fernet / AES-128):

- **Password Vault** entries — encrypted with the user's login password
- **Notebook** note content and attached images — encrypted with a separate master password
- **Exam Detail** wrong-question photos and notes — encrypted

Passwords are hashed with `bcrypt` (cost factor 12). The plaintext password never touches the database.

---

## 🏗️ Architecture Notes

### Auth

```python
from core.auth_manager import auth_manager

user = auth_manager.current_user   # dict: {id, username, ...}
uid  = auth_manager.get_user_id()  # int or None
```

### Encryption

```python
from services.encryption_service import encrypt, decrypt

ciphertext = encrypt("hello", "my-password")
plaintext  = decrypt(ciphertext, "my-password")
```

### Non-blocking API calls (Finance / Games)

```python
from tools.finance_service.finance_base import fetch_async

fetch_async(
    fn=lambda: requests.get("https://...").json(),   # runs in thread
    callback=self._on_result                          # called on main thread
)
```

### Charts

`MiniChart` and `BarChart` in `finance_base.py` are pure `QPainter` widgets — no external charting library needed. They resize responsively and support multiple series with gradient fills.

---

## 🛠️ Adding a New Category

1. `ui/sidebar.py` — add to `CATEGORIES`:
   ```python
   ("🔬", "Science", "science"),
   ```

2. `ui/dashboard.py` — add to `TOOL_CARDS` and `cat_names`:
   ```python
   "science": [("🔬", "My Tool", "Description", "my_tool")],
   # in cat_names:
   "science": "🔬 Science",
   ```

3. Drop tool folder(s) into `tools/`

4. Register in `ui/main_window.py` `tool_modules`

---

## 📦 Building an Executable

```bash
# Windows
build_windows.bat

# Manual (any platform)
pyinstaller main.spec
```

Output: `dist/MultiTool Studio/`

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Credits

Built with [PySide6](https://doc.qt.io/qtforpython/), [MediaPipe](https://mediapipe.dev/), [OpenCV](https://opencv.org/), [CoinGecko API](https://www.coingecko.com/en/api), [ExchangeRate-API](https://www.exchangerate-api.com/), and [Yahoo Finance](https://finance.yahoo.com/).
