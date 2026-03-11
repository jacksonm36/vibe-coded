"""Encrypt/decrypt credential secrets. Uses Fernet (symmetric) with key from env."""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DEFAULT_SALT = b"ansible-ui-credential-salt"
ENV_KEY = "ANSIBLE_UI_SECRET_KEY"


def _get_key() -> bytes:
    raw = os.getenv(ENV_KEY)
    if raw and len(raw) >= 32:
        return base64.urlsafe_b64encode(raw.encode("utf-8")[:32].ljust(32)[:32])
    # Derive from a default (not safe for production; set ANSIBLE_UI_SECRET_KEY)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=DEFAULT_SALT, iterations=480000)
    key = base64.urlsafe_b64encode(kdf.derive(b"ansible-ui-default-key"))
    return key


def encrypt_secret(plain: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(encrypted: str) -> str:
    if not encrypted:
        return ""
    f = Fernet(_get_key())
    return f.decrypt(encrypted.encode("ascii")).decode("utf-8")
