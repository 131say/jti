"""Профили пользователей в Redis (отображение в UI)."""

from __future__ import annotations

import json
from typing import Any


def user_key(user_id: str) -> str:
    return f"aiforge:user:{user_id}"


async def upsert_user_profile(
    redis: Any,
    user_id: str,
    *,
    email: str,
    name: str,
    avatar_url: str | None,
) -> None:
    payload = {
        "id": user_id,
        "email": email,
        "name": name,
        "avatar_url": avatar_url,
    }
    await redis.set(user_key(user_id), json.dumps(payload, ensure_ascii=False))


async def get_user_profile(redis: Any, user_id: str) -> dict[str, Any] | None:
    raw = await redis.get(user_key(user_id))
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)
