from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoError(ValueError):
    """Raised when encryption or decryption cannot be completed safely."""


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = get_settings().encryption_key.encode("utf-8")
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise CryptoError("Invalid encryption key configuration.") from exc


def encrypt(plaintext: str) -> str:
    try:
        token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    except CryptoError:
        raise
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CryptoError("Unable to encrypt value.") from exc
    return token.decode("utf-8")


def decrypt(ciphertext: str) -> str:
    try:
        plaintext = _get_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise CryptoError("Unable to decrypt value.") from exc
    except CryptoError:
        raise
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CryptoError("Unable to decrypt value.") from exc
    return plaintext.decode("utf-8")
