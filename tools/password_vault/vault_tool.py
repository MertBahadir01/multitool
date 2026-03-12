"""
Password Vault – Secure Password Manager Tool
Encrypted storage with Fernet, key derived via PBKDF2 from master password
"""
import random
import string
import pyperclip
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QFormLayout, QTextEdit, QMessageBox, QHeaderView, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from core.plugin_manager import ToolInterface
from core.auth_manager import auth
from core.security_manager import security
from database.database import db


class PasswordVaultTool(ToolInterface):
    name = "Password Vault"
    description = "Secure encrypted password manager"
    icon = "🗄️"
    category = "Security"

    def get_widget(self):
        return PasswordVaultWidget()


class AddEditDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Add Entry" if not entry else "Edit Entry")
        self.setFixedSize(480, 420)
        self._build_ui()
        if entry:
            self._fill(entry)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("🔐 " + ("Edit Entry" if self.entry else "New Entry"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)

        form_group = QGroupBox()
        form = QFormLayout(form_group)
        form.setSpacing(12)

        self.service_edit = QLineEdit()
        self.service_edit.setPlaceholderText("e.g. GitHub, Gmail, Netflix")
        form.addRow("Service / Site:", self.service_edit)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username or email")
        form.addRow("Username:", self.username_edit)

        pwd_row = QHBoxLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        show_btn = QPushButton("👁")
        show_btn.setFixedWidth(36)
        show_btn.setObjectName("btn_secondary")
        show_btn.clicked.connect(self._toggle_show)
        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("btn_secondary")
        gen_btn.clicked.connect(self._generate_pwd)
        pwd_row.addWidget(self.password_edit)
        pwd_row.addWidget(show_btn)
        pwd_row.addWidget(gen_btn)
        form.addRow("Password:", pwd_row)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes...")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_edit)

        layout.addWidget(form_group)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Entry")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _toggle_show(self):
        if self.password_edit.echoMode() == QLineEdit.Password:
            self.password_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)

    def _generate_pwd(self):
        chars = string.ascii_letters + string.digits + "!@#$%^&*()"
        pwd = ''.join(random.SystemRandom().choice(chars) for _ in range(20))
        self.password_edit.setText(pwd)
        self.password_edit.setEchoMode(QLineEdit.Normal)

    def _fill(self, entry):
        self.service_edit.setText(entry.get("service_name", ""))
        self.username_edit.setText(entry.get("username", ""))
        try:
            decrypted = security.decrypt(entry.get("encrypted_password", ""))
            self.password_edit.setText(decrypted)
        except Exception:
            self.password_edit.setText("")
        self.notes_edit.setPlainText(entry.get("notes", "") or "")

    def get_data(self):
        return {
            "service_name": self.service_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


class PasswordVaultWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._entries = []
        self._clipboard_timer = None
        self._build_ui()
        self._load_entries()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("🗄️ Password Vault")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        header_row.addWidget(title)
        header_row.addStretch()

        security_badge = QLabel("🔐 AES-256 Encrypted")
        security_badge.setStyleSheet("""
            background: #00BFA520;
            color: #00BFA5;
            border: 1px solid #00BFA540;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_row.addWidget(security_badge)
        layout.addLayout(header_row)

        desc = QLabel("All passwords are encrypted with your master password and stored locally.")
        desc.setStyleSheet("color: #777777; font-size: 12px;")
        layout.addWidget(desc)

        # Toolbar
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search services, usernames...")
        self.search_input.textChanged.connect(self._search)
        toolbar.addWidget(self.search_input, 1)

        add_btn = QPushButton("➕  Add Entry")
        add_btn.clicked.connect(self._add_entry)
        toolbar.addWidget(add_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00BFA5; font-size: 12px;")
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Service", "Username", "Password", "Notes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 120)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        # Action buttons
        action_row = QHBoxLayout()
        self.copy_btn = QPushButton("📋  Copy Password")
        self.copy_btn.clicked.connect(self._copy_password)
        self.edit_btn = QPushButton("✏️  Edit")
        self.edit_btn.setObjectName("btn_secondary")
        self.edit_btn.clicked.connect(self._edit_entry)
        self.delete_btn = QPushButton("🗑  Delete")
        self.delete_btn.setObjectName("btn_danger")
        self.delete_btn.clicked.connect(self._delete_entry)
        action_row.addWidget(self.copy_btn)
        action_row.addWidget(self.edit_btn)
        action_row.addWidget(self.delete_btn)
        action_row.addStretch()

        self.entry_count = QLabel("")
        self.entry_count.setStyleSheet("color: #777777; font-size: 12px;")
        action_row.addWidget(self.entry_count)
        layout.addLayout(action_row)

    def _load_entries(self, search=""):
        user_id = auth.get_user_id()
        if not user_id:
            return
        self._entries = [dict(e) for e in db.get_vault_entries(user_id, search)]
        self._render_table()

    def _render_table(self):
        self.table.setRowCount(0)
        for entry in self._entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(entry.get("service_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("username", "")))
            pwd_item = QTableWidgetItem("••••••••••")
            self.table.setItem(row, 2, pwd_item)
            self.table.setItem(row, 3, QTableWidgetItem(entry.get("notes", "") or ""))
        self.entry_count.setText(f"{len(self._entries)} entr{'y' if len(self._entries) == 1 else 'ies'}")

    def _search(self, text):
        self._load_entries(text)

    def _get_selected_entry(self):
        rows = self.table.selectedItems()
        if not rows:
            return None, -1
        row = self.table.currentRow()
        if row < 0 or row >= len(self._entries):
            return None, -1
        return self._entries[row], row

    def _add_entry(self):
        dialog = AddEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["service_name"] or not data["password"]:
                QMessageBox.warning(self, "Validation", "Service and password are required.")
                return
            try:
                encrypted = security.encrypt(data["password"])
                db.add_vault_entry(
                    auth.get_user_id(),
                    data["service_name"],
                    data["username"],
                    encrypted,
                    data["notes"]
                )
                self._load_entries()
                self._show_status("✓ Entry added successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _edit_entry(self):
        entry, _ = self._get_selected_entry()
        if not entry:
            QMessageBox.information(self, "Info", "Please select an entry to edit.")
            return
        dialog = AddEditDialog(self, entry)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                encrypted = security.encrypt(data["password"])
                db.update_vault_entry(
                    entry["id"],
                    data["service_name"],
                    data["username"],
                    encrypted,
                    data["notes"]
                )
                self._load_entries()
                self._show_status("✓ Entry updated")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update: {e}")

    def _delete_entry(self):
        entry, _ = self._get_selected_entry()
        if not entry:
            QMessageBox.information(self, "Info", "Please select an entry to delete.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete entry for '{entry['service_name']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            db.delete_vault_entry(entry["id"])
            self._load_entries()
            self._show_status("✓ Entry deleted")

    def _copy_password(self):
        entry, _ = self._get_selected_entry()
        if not entry:
            QMessageBox.information(self, "Info", "Please select an entry.")
            return
        try:
            decrypted = security.decrypt(entry["encrypted_password"])
            pyperclip.copy(decrypted)
            self._show_status(f"✓ Password copied! Auto-clear in 30s")
            if self._clipboard_timer:
                self._clipboard_timer.stop()
            self._clipboard_timer = QTimer()
            self._clipboard_timer.setSingleShot(True)
            self._clipboard_timer.timeout.connect(self._clear_clipboard)
            self._clipboard_timer.start(30000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to decrypt: {e}")

    def _clear_clipboard(self):
        try:
            pyperclip.copy("")
            self._show_status("🔒 Clipboard cleared")
        except Exception:
            pass

    def _show_status(self, msg):
        self.status_label.setText(msg)
        QTimer.singleShot(4000, lambda: self.status_label.setText(""))
