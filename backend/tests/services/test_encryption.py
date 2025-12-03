import pytest

from app.services.encryption import decrypt_secret, encrypt_secret


def test_encrypt_secret_roundtrip():
    plaintext = "sk-test-123"
    token = encrypt_secret(plaintext)

    assert isinstance(token, bytes)
    decrypted = decrypt_secret(token)
    assert decrypted == plaintext


def test_encrypt_secret_rejects_empty():
    with pytest.raises(ValueError):
        encrypt_secret("")


def test_decrypt_secret_invalid_payload():
    with pytest.raises(ValueError):
        decrypt_secret(b"not-a-valid-token")
