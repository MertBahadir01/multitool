If you want to create a new tool, or add a tool using AI, you can use the prompt below.

The following prompt is provided as a template you can use when building a new tool.

---

**SYSTEM CONTEXT — MultiTool Studio**

I'm giving you a zip of my PySide6 desktop app called MultiTool Studio. Before writing anything, read these files fully:
- `ui/main_window.py` — tool registry
- `ui/dashboard.py` — TOOL_CARDS
- `database/database.py` — all tables
- `services/encryption_service.py` — encrypt/decrypt
- `core/auth_manager.py` — auth_manager, current_user, get_user_id()
- `tools/password_vault/vault_ui.py` — **this is the exact pattern every new tool must follow**
- `tools/password_vault/vault_service.py` — **this is the exact pattern every new service must follow**

**Rules you must follow without exception:**
1. Every tool class is a plain `QWidget` subclass with `name` and `description` class attributes — no `ToolInterface`, no `get_widget()`
2. `__init__.py` uses relative import: `from .tool_file import ToolClass`
3. If the tool needs DB, add only the new `c.execute(CREATE TABLE IF NOT EXISTS ...)` blocks to `database.py` — nothing else changes in that file
4. If the tool needs encryption, use `from services.encryption_service import encrypt, decrypt` — never invent a new encryption method
5. If the tool needs the current user, use `from core.auth_manager import auth_manager`
6. If the tool needs a lock screen (for sensitive data), copy the locked/unlocked widget pattern from `vault_ui.py` exactly
7. Deliver: the complete new tool folder(s) ready to drop into `tools/`, plus a single `CHANGES_NEEDED.txt` listing only the lines to add in `main_window.py`, `dashboard.py`, and `database.py`
8. Never rewrite existing files in full — only show the exact lines to add

**I want to add:** [DESCRIBE YOUR TOOL HERE]

