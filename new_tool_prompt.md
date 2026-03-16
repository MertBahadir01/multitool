If you want to create a new tool, or add a tool using AI, you can use the prompt below.

The following prompt is provided as a template you can use when building a new tool.

---

**SYSTEM CONTEXT — MultiTool Studio**

I'm giving you a zip of my PySide6 desktop app called MultiTool Studio. Before writing anything, read these files fully:

* `ui/main_window.py` — tool registry
* `ui/dashboard.py` — TOOL_CARDS
* `database/database.py` — all tables
* `services/encryption_service.py` — encrypt/decrypt
* `core/auth_manager.py` — auth_manager, current_user, get_user_id()
* `tools/password_vault/vault_ui.py` — **this is the exact pattern every new tool must follow**
* `tools/password_vault/vault_service.py` — **this is the exact pattern every new service must follow**

**Rules you must follow without exception:**

1. Every tool class is a plain `QWidget` subclass with `name` and `description` class attributes — no `ToolInterface`, no `get_widget()`
2. `__init__.py` uses relative import: `from .tool_file import ToolClass`
3. If the tool needs DB, add only the new `c.execute(CREATE TABLE IF NOT EXISTS ...)` blocks to `database.py` — nothing else changes in that file
4. If the tool needs encryption, use `from services.encryption_service import encrypt, decrypt` — never invent a new encryption method
5. If the tool needs the current user, use `from core.auth_manager import auth_manager`
6. If the tool needs a lock screen (for sensitive data), copy the locked/unlocked widget pattern from `vault_ui.py` exactly
7. Deliver: the complete new tool folder(s) ready to drop into `tools/`, plus a single `CHANGES_NEEDED.txt` listing only the lines to add in `main_window.py`, `dashboard.py`, and `database.py`
8. Never rewrite existing files in full — only show the exact lines to add

---

# Category Tool Integration (for any tool category)

When adding a new **tool category** (Study, Games, Security, Utilities, etc.), follow this standard structure.

══════════════════════════════════════════════════════════════════════════
CHANGES NEEDED — Category Tool Section
3 existing files to edit. Everything else is new folders to drop in.
══════════════════════════════════════════════════════════════════════════

---

## ── 1. `database/database.py` ───────────────────────────────────────────

Paste the **table creation blocks** for the new tools inside `init_database()`.

Place them **after the last existing tool block** and **before `conn.commit()`**.

Each tool may require its own table.

Example pattern:

```python
c.execute("""
CREATE TABLE IF NOT EXISTS <tool_table_name> (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
```

Multiple tables may be added depending on the tool.

---

## ── 2. `ui/main_window.py` ──────────────────────────────────────────────

Inside `_register_tools()`, add the new tools to the `tool_modules` list.

Format:

```python
("<tool_id>", "<tools.module_path>", "<ToolClassName>"),
```

Example:

```python
("game_snake",      "tools.game_snake",      "SnakeGameTool"),
("game_sudoku",     "tools.game_sudoku",     "SudokuGameTool"),
("security_hash",   "tools.security_hash",   "HashTool"),
("utility_qr",      "tools.utility_qr",      "QRGeneratorTool"),
```

Each entry registers a tool so the app can dynamically load it.

---

## ── 3a. `ui/dashboard.py` — add TOOL_CARDS entry ────────────────────────

Add a new key to the `TOOL_CARDS` dictionary for the category.

Format:

```python
"<category_key>": [
    ("icon", "Tool Name", "Short description", "tool_id"),
],
```

Example:

```python
"games": [
    ("🐍", "Snake",   "Classic snake arcade game", "game_snake"),
    ("🧩", "Sudoku",  "Play and solve Sudoku puzzles", "game_sudoku"),
],
```

---

## ── 3b. `ui/dashboard.py` — update `cat_names` in `CategoryView._build_ui` ─

Add the category display name.

Example:

```python
"games": "🎮 Games",
"study": "📚 Study Tools",
"security": "🔐 Security Tools",
```

---

## ── 4. `ui/sidebar.py` ──────────────────────────────────────────────────

Add the category entry to the `CATEGORIES` list.

Format:

```python
("icon", "Category Name", "category_key"),
```

Example:

```python
("🎮", "Games", "games"),
("📚", "Study Tools", "study"),
("🔐", "Security Tools", "security"),
("🛠", "Utilities", "utilities"),
```

---

# New folders (drop into `tools/`)

Each tool lives in its own folder.

```
tools/
 ├── game_snake/
 ├── game_sudoku/
 ├── security_hash/
 ├── utility_qr/
 ├── study_flashcards/
```

Each folder should contain the tool implementation.

Example:

```
tools/game_snake/
    tool.py
    game_logic.py
    assets/
```

---

# Optional Shared Service

If multiple tools share logic, create a **service file** inside one tool folder.

Example:

```
tools/study_lessons/tool_service.py
```

Other tools can import it like:

```python
from tools.study_lessons.tool_service import ServiceClass
```

No changes needed to any other existing file.

---

✅ Result:
This structure allows the multitool app to support **unlimited categories and tools** with minimal core modifications.


══════════════════════════════════════════════════════════════════════════

**I want to add:** [DESCRIBE YOUR TOOL HERE]
