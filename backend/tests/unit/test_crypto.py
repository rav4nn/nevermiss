from __future__ import annotations

from cryptography.fernet import Fernet

from app.core import crypto


def test_encrypt_decrypt_round_trip() -> None:
    crypto._get_fernet.cache_clear()

    original_get_settings = crypto.get_settings
    test_key = Fernet.generate_key().decode("utf-8")

    class SettingsStub:
        encryption_key = test_key

    crypto.get_settings = lambda: SettingsStub()  # type: ignore[assignment]
    try:
        ciphertext = crypto.encrypt("hello")
        assert ciphertext != "hello"
        assert crypto.decrypt(ciphertext) == "hello"
    finally:
        crypto.get_settings = original_get_settings
        crypto._get_fernet.cache_clear()


def test_decrypt_with_wrong_key_raises_crypto_error() -> None:
    crypto._get_fernet.cache_clear()

    first_key = Fernet.generate_key().decode("utf-8")
    second_key = Fernet.generate_key().decode("utf-8")

    class SettingsStub:
        def __init__(self, encryption_key: str) -> None:
            self.encryption_key = encryption_key

    original_get_settings = crypto.get_settings
    crypto.get_settings = lambda: SettingsStub(first_key)  # type: ignore[assignment]

    try:
        ciphertext = crypto.encrypt("hello")
        crypto._get_fernet.cache_clear()
        crypto.get_settings = lambda: SettingsStub(second_key)  # type: ignore[assignment]

        try:
            crypto.decrypt(ciphertext)
        except crypto.CryptoError:
            pass
        else:
            raise AssertionError("Expected CryptoError when decrypting with the wrong key.")
    finally:
        crypto.get_settings = original_get_settings
        crypto._get_fernet.cache_clear()
