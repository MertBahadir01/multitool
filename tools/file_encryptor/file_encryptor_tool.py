"""File Encryptor — encrypt/decrypt files with a password using AES-256-GCM via cryptography lib."""
import os, base64
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QGroupBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont

MAGIC = b"MTS1"  # MultiTool Studio v1


def _derive_key(password: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return kdf.derive(password.encode())


def encrypt_file(src, dst, password):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt  = os.urandom(16)
    nonce = os.urandom(12)
    key   = _derive_key(password, salt)
    with open(src, "rb") as f:
        data = f.read()
    ct = AESGCM(key).encrypt(nonce, data, None)
    with open(dst, "wb") as f:
        f.write(MAGIC + salt + nonce + ct)


def decrypt_file(src, dst, password):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    with open(src, "rb") as f:
        blob = f.read()
    if not blob.startswith(MAGIC):
        raise ValueError("Not a valid encrypted file.")
    blob  = blob[len(MAGIC):]
    salt  = blob[:16]
    nonce = blob[16:28]
    ct    = blob[28:]
    key   = _derive_key(password, salt)
    data  = AESGCM(key).decrypt(nonce, ct, None)
    with open(dst, "wb") as f:
        f.write(data)


class _Worker(QThread):
    done  = Signal(bool, str)
    def __init__(self, mode, src, dst, pw):
        super().__init__()
        self.mode, self.src, self.dst, self.pw = mode, src, dst, pw
    def run(self):
        try:
            if self.mode == "encrypt":
                encrypt_file(self.src, self.dst, self.pw)
            else:
                decrypt_file(self.src, self.dst, self.pw)
            self.done.emit(True, self.dst)
        except Exception as e:
            self.done.emit(False, str(e))


class FileEncryptorTool(QWidget):
    name        = "File Encryptor"
    description = "Encrypt and decrypt files with a password (AES-256-GCM)"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src = ""
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        sub = QLabel("Encrypt any file with a password. Uses AES-256-GCM via the cryptography library.")
        sub.setStyleSheet("color: #888888;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        # File
        fb = QGroupBox("File")
        fl = QHBoxLayout(fb)
        self.file_lbl = QLabel("No file selected")
        self.file_lbl.setStyleSheet("color: #888888;")
        fl.addWidget(self.file_lbl, 1)
        b = QPushButton("Browse")
        b.clicked.connect(self._browse)
        fl.addWidget(b)
        lay.addWidget(fb)

        # Password
        pb = QGroupBox("Password")
        pl = QVBoxLayout(pb)
        row = QHBoxLayout()
        self.pw_in = QLineEdit()
        self.pw_in.setEchoMode(QLineEdit.Password)
        self.pw_in.setPlaceholderText("Enter password...")
        row.addWidget(self.pw_in)
        show = QCheckBox("Show")
        show.toggled.connect(lambda v: self.pw_in.setEchoMode(QLineEdit.Normal if v else QLineEdit.Password))
        row.addWidget(show)
        pl.addLayout(row)
        lay.addWidget(pb)

        # Buttons
        btn_row = QHBoxLayout()
        enc_btn = QPushButton("Encrypt File")
        enc_btn.clicked.connect(self._encrypt)
        btn_row.addWidget(enc_btn)
        dec_btn = QPushButton("Decrypt File")
        dec_btn.setObjectName("secondary")
        dec_btn.clicked.connect(self._decrypt)
        btn_row.addWidget(dec_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.status_lbl = QLabel("")
        lay.addWidget(self.status_lbl)

        note = QLabel("Requires: pip install cryptography")
        note.setStyleSheet("color: #555555; font-size: 11px;")
        lay.addWidget(note)
        lay.addStretch()

    def _browse(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select File")
        if f:
            self._src = f
            self.file_lbl.setText(f)
            self.file_lbl.setStyleSheet("color: #CCCCCC;")

    def _encrypt(self):
        if not self._check(): return
        dst, _ = QFileDialog.getSaveFileName(self, "Save Encrypted File", self._src + ".locked")
        if not dst: return
        self._run("encrypt", dst)

    def _decrypt(self):
        if not self._check(): return
        default = self._src[:-7] if self._src.endswith(".locked") else self._src + ".decrypted"
        dst, _ = QFileDialog.getSaveFileName(self, "Save Decrypted File", default)
        if not dst: return
        self._run("decrypt", dst)

    def _check(self):
        if not self._src:
            self.status_lbl.setText("Please select a file.")
            self.status_lbl.setStyleSheet("color: #F44336;")
            return False
        if not self.pw_in.text():
            self.status_lbl.setText("Please enter a password.")
            self.status_lbl.setStyleSheet("color: #F44336;")
            return False
        return True

    def _run(self, mode, dst):
        self.status_lbl.setText("Working...")
        self.status_lbl.setStyleSheet("color: #888888;")
        self._worker = _Worker(mode, self._src, dst, self.pw_in.text())
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok, msg):
        if ok:
            self.status_lbl.setText(f"Done: {msg}")
            self.status_lbl.setStyleSheet("color: #00BFA5;")
        else:
            self.status_lbl.setText(f"Error: {msg}")
            self.status_lbl.setStyleSheet("color: #F44336;")
