"""Password vault data access layer."""
from database.database import get_connection
from services.encryption_service import encrypt, decrypt


class VaultService:
    def __init__(self, user_id: int, master_password: str):
        self.user_id = user_id
        self.master_password = master_password

    def add_entry(self, service, username, password, notes=""):
        enc = encrypt(password, self.master_password)
        conn = get_connection()
        conn.execute(
            "INSERT INTO password_vault (user_id, service_name, username, encrypted_password, notes) VALUES (?,?,?,?,?)",
            (self.user_id, service, username, enc, notes)
        )
        conn.commit(); conn.close()

    def update_entry(self, entry_id, service, username, password, notes=""):
        enc = encrypt(password, self.master_password)
        conn = get_connection()
        conn.execute(
            "UPDATE password_vault SET service_name=?, username=?, encrypted_password=?, notes=? WHERE id=? AND user_id=?",
            (service, username, enc, notes, entry_id, self.user_id)
        )
        conn.commit(); conn.close()

    def delete_entry(self, entry_id):
        conn = get_connection()
        conn.execute("DELETE FROM password_vault WHERE id=? AND user_id=?", (entry_id, self.user_id))
        conn.commit(); conn.close()

    def get_all(self, search=""):
        conn = get_connection()
        if search:
            rows = conn.execute(
                "SELECT * FROM password_vault WHERE user_id=? AND (service_name LIKE ? OR username LIKE ?) ORDER BY service_name",
                (self.user_id, f"%{search}%", f"%{search}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM password_vault WHERE user_id=? ORDER BY service_name",
                (self.user_id,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def decrypt_password(self, encrypted_password) -> str:
        return decrypt(encrypted_password, self.master_password)
