"""
Utility helpers for encrypting/decrypting provider secrets (e.g. API keys).
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.logging_config import logger
from app.settings import settings


def _derive_fernet_key(secret: str) -> bytes:
    """
    Derive a 32-byte Fernet key from the configured SECRET_KEY.

    Fernet expects a base64-encoded 32-byte key. We hash the shared secret
    and feed the digest through urlsafe_b64encode to meet the requirement.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key(settings.secret_key))


def encrypt_secret(value: str) -> bytes:
    """
    Encrypt a plaintext value and return the ciphertext bytes.
    """
    if not value:
        raise ValueError("Cannot encrypt empty value")
    token = _get_fernet().encrypt(value.encode("utf-8"))
    return token


def decrypt_secret(token: bytes | str) -> str:
    """
    Decrypt a Fernet token (bytes or base64 string) and return plaintext.
    """
    if isinstance(token, str):
        token_bytes = token.encode("utf-8")
    else:
        token_bytes = token
    try:
        plaintext = _get_fernet().decrypt(token_bytes)
    except InvalidToken as exc:  # pragma: no cover - defensive guard
        logger.error(f"Failed to decrypt secret: {exc}")
        raise ValueError("Invalid encrypted payload") from exc
    return plaintext.decode("utf-8")


__all__ = ["decrypt_secret", "encrypt_secret"]
