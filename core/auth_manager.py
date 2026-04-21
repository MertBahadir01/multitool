"""User authentication using bcrypt."""

import bcrypt
from database.database import get_connection


class AuthManager:
    def __init__(self):
        self.current_user = None
        self._logout_callbacks = []

    def register(self, username: str, password: str) -> tuple[bool, str]:
        if not username or not password:
            return False, "Username and password required."
        if len(password) < 8:
            return False, "Password must be at least 8 characters."
        try:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn = get_connection()
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, pw_hash)
            )
            conn.commit()
            conn.close()
            return True, "Account created successfully."
        except Exception as e:
            return False, f"Registration failed: {e}"

    def login(self, username: str, password: str) -> tuple[bool, str]:
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            conn.close()
            if not row:
                return False, "Invalid username or password."
            if bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                self.current_user = dict(row)
                return True, "Login successful."
            return False, "Invalid username or password."
        except Exception as e:
            return False, f"Login error: {e}"

    def logout(self):
        """Clear all session state and notify registered callbacks."""
        self.current_user = None
        for cb in list(self._logout_callbacks):
            try:
                cb()
            except Exception:
                pass

    def register_logout_callback(self, callback):
        """Register a callable to be invoked on logout."""
        self._logout_callbacks.append(callback)

    def unregister_logout_callback(self, callback):
        """Remove a previously registered logout callback."""
        try:
            self._logout_callbacks.remove(callback)
        except ValueError:
            pass

    def is_logged_in(self) -> bool:
        return self.current_user is not None

    def get_user_id(self):
        return self.current_user["id"] if self.current_user else None


auth_manager = AuthManager()
