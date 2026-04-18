"""JWT сессии API (HS256) после верификации Google ID token."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from pydantic import BaseModel, Field

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_EXP_DAYS = int(os.environ.get("JWT_EXP_DAYS", "7"))
JWT_ALG = "HS256"


class AuthUserClaims(BaseModel):
    """Полезная нагрузка нашего access_token."""

    sub: str = Field(min_length=1, description="Стабильный id (Google sub)")
    email: str = ""
    name: str = ""
    picture: str | None = None


def require_jwt_secret() -> str:
    if not JWT_SECRET.strip():
        raise RuntimeError("JWT_SECRET is not set")
    return JWT_SECRET


def create_access_token(
    *,
    sub: str,
    email: str,
    name: str,
    picture: str | None,
    exp_days: int | None = None,
) -> str:
    secret = require_jwt_secret()
    now = datetime.now(timezone.utc)
    delta = timedelta(days=exp_days if exp_days is not None else JWT_EXP_DAYS)
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "picture": picture,
        "iat": now,
        "exp": now + delta,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALG)


def decode_access_token(token: str) -> AuthUserClaims:
    secret = require_jwt_secret()
    try:
        raw = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALG],
            options={"require": ["exp", "sub"]},
        )
    except ExpiredSignatureError as e:
        raise ValueError("token expired") from e
    except InvalidTokenError as e:
        raise ValueError("invalid token") from e
    return AuthUserClaims.model_validate(raw)
