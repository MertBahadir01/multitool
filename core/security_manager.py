"""
Security Manager - handles encryption, key derivation, and crypto operations
"""
import os
import base64
import hashlib
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from core.config import PBKDF2_ITERATIONS, KEY_LENGTH


class SecurityManager:
    def __init__(self):
        self._fernet = None

    def hash_password(self, password: str) -> tuple[str, str]:
        """Hash a password with bcrypt. Returns (hash, salt)."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode(), salt.decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its bcrypt hash."""
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False

    def derive_key(self, master_password: str, salt: str) -> bytes:
        """Derive a Fernet encryption key from master password using PBKDF2."""
        salt_bytes = salt.encode() if isinstance(salt, str) else salt
        # Use first 16 bytes of salt as PBKDF2 salt
        pbkdf2_salt = hashlib.sha256(salt_bytes).digest()[:16]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=pbkdf2_salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return key

    def setup_encryption(self, master_password: str, salt: str):
        """Initialize Fernet encryption with derived key."""
        key = self.derive_key(master_password, salt)
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized. Call setup_encryption first.")
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string value."""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized. Call setup_encryption first.")
        decrypted = self._fernet.decrypt(ciphertext.encode())
        return decrypted.decode()

    def lock(self):
        """Clear the encryption key from memory."""
        self._fernet = None

    def is_unlocked(self) -> bool:
        return self._fernet is not None


security = SecurityManager()
