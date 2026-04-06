from __future__ import annotations

import jwt

from app.core.errors import AppError, ErrorCode


def decode_nextauth_token(token: str, secret: str) -> dict[str, object]:
    """
    Decode and verify a NextAuth HS256 JWT.

    Validates signature, expiry, and algorithm. Raises AppError(UNAUTHENTICATED)
    on any failure. Never logs the raw token value.

    Returns the decoded payload dict on success.
    """
    try:
        payload: dict[str, object] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Token has expired.",
            status_code=401,
        )
    except jwt.InvalidAlgorithmError:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Token uses an unsupported algorithm.",
            status_code=401,
        )
    except jwt.PyJWTError:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Invalid token.",
            status_code=401,
        )

    return payload
