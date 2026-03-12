"""Fernet encryption with PBKDF2 key derivation."""

import base64
import os
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


SALT = b"multitool_studio_salt_2024_secure"  # In production: store per-user salt in DB


def derive_key(master_password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return key


def encrypt(plaintext: str, master_password: str) -> bytes:
    key = derive_key(master_password)
    f = Fernet(key)
    return f.encrypt(plaintext.encode())


def decrypt(ciphertext: bytes, master_password: str) -> str:
    key = derive_key(master_password)
    f = Fernet(key)
    return f.decrypt(ciphertext).decode()
