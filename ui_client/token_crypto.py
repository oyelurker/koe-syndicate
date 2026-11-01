"""Encrypt OAuth secrets at rest; encryption keys stay outside the database."""
import os
from cryptography.fernet import Fernet
from common.security import SecurityError

PREFIX = "enc:v1:"


def cipher():
    try:
        return Fernet(os.environ["TOKEN_ENCRYPTION_KEY"].encode())
    except (KeyError, ValueError) as exc:
        raise SecurityError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt(value):
    return PREFIX + cipher().encrypt(value.encode()).decode() if value else None


def decrypt(value):
    if value is None:
        return None
    if not value.startswith(PREFIX):
        raise SecurityError("Unmigrated plaintext credential; run database initialization")
    return cipher().decrypt(value[len(PREFIX):].encode()).decode()
