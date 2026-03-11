"""Encrypt/decrypt credential secrets. Uses Fernet (symmetric) with key from env."""
import logging
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

DEFAULT_SALT = b"ansible-ui-credential-salt"
ENV_KEY = "ANSIBLE_UI_SECRET_KEY"


def _get_key() -> bytes:
    raw = os.getenv(ENV_KEY)
    if raw and len(raw) >= 32:
        return base64.urlsafe_b64encode(raw.encode("utf-8")[:32].ljust(32)[:32])
    # Derive from a known default — NOT safe for production.
    # All credentials encrypted with this key can be decrypted by anyone
    # who reads this source code.  Set ANSIBLE_UI_SECRET_KEY to a random
    # 32-character string in production.
    logger.warning(
        "SECURITY WARNING: %s is not set or is shorter than 32 characters. "
        "A predictable default encryption key is being used. "
        "Set %s to a random 32+ character string in production.",
        ENV_KEY,
        ENV_KEY,
    )
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
