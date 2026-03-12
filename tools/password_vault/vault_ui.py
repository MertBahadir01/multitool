"""Full-featured Password Vault UI with encrypted storage."""

import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QTextEdit, QMessageBox,
    QGroupBox, QDialogButtonBox, QApplication, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from core.auth_manager import auth_manager
from tools.password_vault.vault_service import VaultService
from tools.password_generator.password_tool import generate_password


class EntryDialog(QDialog):
    """Add / Edit entry dialog."""
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Entry" if entry else "Add Entry")
        self.setFixedSize(440, 380)
        self._build_ui()
        if entry:
            self.service_input.setText(entry.get("service_name", ""))
            self.user_input.setText(entry.get("username", ""))
            self.notes_input.setPlainText(entry.get("notes", ""))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Service / Website:"))
        self.service_input = QLineEdit(); self.service_input.setPlaceholderText("e.g. GitHub, Gmail")
        layout.addWidget(self.service_input)

        layout.addWidget(QLabel("Username / Email:"))
        self.user_input = QLineEdit(); self.user_input.setPlaceholderText("username@example.com")
        layout.addWidget(self.user_input)

        layout.addWidget(QLabel("Password:"))
        pw_row = QHBoxLayout()
        self.pw_input = QLineEdit(); self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("Enter password")
        pw_row.addWidget(self.pw_input)
        show_btn = QPushButton("👁")
        show_btn.setFixedWidth(36)
        show_btn.setObjectName("secondary")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(lambda c: self.pw_input.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password))
        pw_row.addWidget(show_btn)
        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("secondary")
        gen_btn.clicked.connect(self._gen_password)
        pw_row.addWidget(gen_btn)
        layout.addLayout(pw_row)

        layout.addWidget(QLabel("Notes (optional):"))
        self.notes_input = QTextEdit(); self.notes_input.setMaximumHeight(80)
        layout.addWidget(self.notes_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _gen_password(self):
        pw = generate_password(length=18, use_upper=True, use_lower=True, use_digits=True, use_symbols=True)
        self.pw_input.setText(pw)
        self.pw_input.setEchoMode(QLineEdit.Normal)

    def get_data(self):
        return {
            "service": self.service_input.text().strip(),
            "username": self.user_input.text().strip(),
            "password": self.pw_input.text(),
            "notes": self.notes_input.toPlainText().strip(),
        }


class MasterPasswordDialog(QDialog):
    """Prompt for master password to unlock vault."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unlock Password Vault")
        self.setFixedSize(380, 220)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel("🔐 Enter your master password to unlock the vault")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("Master password (your login password)")
        self.pw_input.returnPressed.connect(self.accept)
        layout.addWidget(self.pw_input)

        self.status = QLabel("")
        layout.addWidget(self.status)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_password(self):
        return self.pw_input.text()


class PasswordVaultTool(QWidget):
    name = "Password Vault"
    description = "Secure encrypted password manager"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vault = None
        self._entries = []
        self._clipboard_timer = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Locked screen
        self.locked_widget = QWidget()
        lw = QVBoxLayout(self.locked_widget)
        lw.setAlignment(Qt.AlignCenter)
        lock_icon = QLabel("🔐")
        lock_icon.setFont(QFont("Segoe UI Emoji", 48))
        lock_icon.setAlignment(Qt.AlignCenter)
        lw.addWidget(lock_icon)
        lock_title = QLabel("Password Vault Locked")
        lock_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        lock_title.setAlignment(Qt.AlignCenter)
        lock_title.setStyleSheet("color: #00BFA5;")
        lw.addWidget(lock_title)
        lock_sub = QLabel("Your passwords are encrypted.\nEnter your account password to unlock.")
        lock_sub.setAlignment(Qt.AlignCenter)
        lock_sub.setStyleSheet("color: #888888;")
        lw.addWidget(lock_sub)
        unlock_btn = QPushButton("🔓 Unlock Vault")
        unlock_btn.setFixedWidth(200)
        unlock_btn.clicked.connect(self._unlock)
        lw.addWidget(unlock_btn, alignment=Qt.AlignCenter)
        layout.addWidget(self.locked_widget)

        # Vault screen
        self.vault_widget = QWidget()
        vw = QVBoxLayout(self.vault_widget)
        vw.setContentsMargins(24, 24, 24, 24)
        vw.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🔐 Password Vault")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        hdr.addWidget(title)
        hdr.addStretch()
        lock_again = QPushButton("🔒 Lock")
        lock_again.setObjectName("secondary")
        lock_again.clicked.connect(self._lock)
        hdr.addWidget(lock_again)
        vw.addLayout(hdr)

        # Search + Add
        ctrl = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Search service or username...")
        self.search.textChanged.connect(self._search)
        ctrl.addWidget(self.search)
        add_btn = QPushButton("+ Add Entry")
        add_btn.clicked.connect(self._add_entry)
        ctrl.addWidget(add_btn)
        vw.addLayout(ctrl)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Service", "Username", "Notes", "Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 180)
        self.table.doubleClicked.connect(self._on_double_click)
        vw.addWidget(self.table)

        # Action buttons
        btns = QHBoxLayout()
        copy_btn = QPushButton("📋 Copy Password")
        copy_btn.clicked.connect(self._copy_password)
        btns.addWidget(copy_btn)
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.setObjectName("secondary")
        edit_btn.clicked.connect(self._edit_entry)
        btns.addWidget(edit_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete_entry)
        btns.addWidget(del_btn)
        btns.addStretch()
        self.clip_lbl = QLabel("")
        self.clip_lbl.setStyleSheet("color: #00BFA5; font-size: 12px;")
        btns.addWidget(self.clip_lbl)
        vw.addLayout(btns)

        layout.addWidget(self.vault_widget)
        self.vault_widget.hide()

    def _unlock(self):
        if not auth_manager.current_user:
            QMessageBox.warning(self, "Error", "Not logged in."); return
        dlg = MasterPasswordDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        master_pw = dlg.get_password()
        # Verify against stored bcrypt hash
        import bcrypt
        stored_hash = auth_manager.current_user["password_hash"].encode()
        if not bcrypt.checkpw(master_pw.encode(), stored_hash):
            QMessageBox.critical(self, "Error", "Invalid master password."); return
        self._vault = VaultService(auth_manager.get_user_id(), master_pw)
        self.locked_widget.hide()
        self.vault_widget.show()
        self._load_entries()

    def _lock(self):
        self._vault = None
        self.vault_widget.hide()
        self.locked_widget.show()

    def _load_entries(self, search=""):
        if not self._vault: return
        self._entries = self._vault.get_all(search)
        self.table.setRowCount(0)
        for e in self._entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(e["service_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(e["username"]))
            self.table.setItem(row, 2, QTableWidgetItem(e.get("notes", "") or ""))
            created = str(e.get("created_at", ""))[:16]
            self.table.setItem(row, 3, QTableWidgetItem(created))

    def _search(self, text):
        self._load_entries(text)

    def _get_selected_entry(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._entries): return None
        return self._entries[row]

    def _add_entry(self):
        dlg = EntryDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        data = dlg.get_data()
        if not data["service"] or not data["password"]:
            QMessageBox.warning(self, "Error", "Service and password are required."); return
        self._vault.add_entry(data["service"], data["username"], data["password"], data["notes"])
        self._load_entries(self.search.text())

    def _edit_entry(self):
        entry = self._get_selected_entry()
        if not entry: QMessageBox.information(self, "Select", "Please select an entry."); return
        try:
            dec_pw = self._vault.decrypt_password(entry["encrypted_password"])
        except Exception:
            dec_pw = ""
        dlg = EntryDialog(self, entry)
        dlg.pw_input.setText(dec_pw)
        if dlg.exec() != QDialog.Accepted: return
        data = dlg.get_data()
        self._vault.update_entry(entry["id"], data["service"], data["username"], data["password"], data["notes"])
        self._load_entries(self.search.text())

    def _delete_entry(self):
        entry = self._get_selected_entry()
        if not entry: return
        reply = QMessageBox.question(self, "Delete", f"Delete '{entry['service_name']}'?",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._vault.delete_entry(entry["id"])
            self._load_entries(self.search.text())

    def _copy_password(self):
        entry = self._get_selected_entry()
        if not entry: QMessageBox.information(self, "Select", "Select an entry first."); return
        try:
            pw = self._vault.decrypt_password(entry["encrypted_password"])
            QApplication.clipboard().setText(pw)
            self.clip_lbl.setText("✅ Copied! Clears in 30s")
            # Auto-clear clipboard
            if self._clipboard_timer: self._clipboard_timer.stop()
            self._clipboard_timer = QTimer(self)
            self._clipboard_timer.setSingleShot(True)
            self._clipboard_timer.timeout.connect(self._clear_clipboard)
            self._clipboard_timer.start(30000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Decryption failed: {e}")

    def _clear_clipboard(self):
        QApplication.clipboard().clear()
        self.clip_lbl.setText("🗑️ Clipboard cleared")
        QTimer.singleShot(3000, lambda: self.clip_lbl.setText(""))

    def _on_double_click(self, index):
        self._copy_password()
