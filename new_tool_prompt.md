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

**Study Section Integration (for study-related tools):**

When adding a new Study tool (like Lessons, Exams, Flashcards, Timer, etc.), follow this standard structure:

---

══════════════════════════════════════════════════════════════════════════
CHANGES NEEDED — Study Section
3 existing files to edit. Everything else is new folders to drop in.
══════════════════════════════════════════════════════════════════════════

── 1. database/database.py ───────────────────────────────────────────────
Paste the full contents of  `database_additions.py` inside `init_database()`,
after the `calculator_history` block, before `conn.commit()`.
(12 `c.execute` blocks — one per table)

── 2. ui/main_window.py ──────────────────────────────────────────────────
Inside `_register_tools()`, add these 8 lines to `tool_modules` list:

```
    ("study_lessons",   "tools.study_lessons",   "StudyLessonsTool"),
    ("study_exams",     "tools.study_exams",     "StudyExamsTool"),
    ("study_tests",     "tools.study_tests",     "StudyTestsTool"),
    ("study_progress",  "tools.study_progress",  "StudyProgressTool"),
    ("study_flashcards","tools.study_flashcards","StudyFlashcardsTool"),
    ("study_timer",     "tools.study_timer",     "StudyTimerTool"),
    ("study_resources", "tools.study_resources", "StudyResourcesTool"),
    ("study_goals",     "tools.study_goals",     "StudyGoalsTool"),
```

── 3a. ui/dashboard.py — add TOOL_CARDS entry ────────────────────────────
Add this new key to the `TOOL_CARDS` dict:

```
"study": [
    ("📚", "Lessons",          "Organize lessons & resources",      "study_lessons"),
    ("📊", "Exam Logging",     "Log TYT/AYT scores per subject",    "study_exams"),
    ("📝", "Test Capture",      "Capture questions with photos",      "study_tests"),
    ("📈", "Progress Tracker", "Charts for exam & study progress",  "study_progress"),
    ("🃏", "Flashcards",       "Spaced repetition flashcards",      "study_flashcards"),
    ("⏱️", "Study Timer",      "Pomodoro timer with logging",        "study_timer"),
    ("📖", "Resource Library", "Books, PDFs, links & videos",       "study_resources"),
    ("🎯", "Goals & Reminders","Set goals and track deadlines",      "study_goals"),
],
```

── 3b. ui/dashboard.py — update cat_names in CategoryView._build_ui ──────
Add this line to the `cat_names` dict:

```
        "study": "📚 Study Tools",
```

── 4. ui/sidebar.py ──────────────────────────────────────────────────────
Add this line to the `CATEGORIES` list (before or after the security entry):

```
("📚", "Study Tools", "study"),
```

── New folders (drop into tools/) ────────────────────────────────────────
tools/study_lessons/         ← contains `study_service.py` (shared by ALL tools)
tools/study_exams/
tools/study_tests/
tools/study_progress/
tools/study_flashcards/
tools/study_timer/
tools/study_resources/
tools/study_goals/

`study_service.py` lives in `tools/study_lessons/` and is imported by all other study tools as:

```
from tools.study_lessons.study_service import <ServiceClass>
```

No changes needed to any other existing file.
══════════════════════════════════════════════════════════════════════════

**I want to add:** [DESCRIBE YOUR TOOL HERE]
