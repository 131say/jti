"""Зависимости FastAPI: Bearer JWT."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from auth_jwt import AuthUserClaims, decode_access_token


async def get_optional_user(request: Request) -> AuthUserClaims | None:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        return decode_access_token(token)
    except ValueError:
        return None


async def require_user(
    user: AuthUserClaims | None = Depends(get_optional_user),
) -> AuthUserClaims:
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация (Authorization: Bearer …)",
        )
    return user
