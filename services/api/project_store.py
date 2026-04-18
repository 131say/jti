"""Проекты в Redis (облачное сохранение + шаринг по ссылке)."""

from __future__ import annotations

import json
from typing import Any

PROJECT_KEY_PREFIX = "aiforge:project:"


def project_key(project_id: str) -> str:
    return f"{PROJECT_KEY_PREFIX}{project_id}"


async def set_project(redis: Any, project_id: str, state: dict[str, Any]) -> None:
    await redis.set(project_key(project_id), json.dumps(state, ensure_ascii=False))


async def get_project(redis: Any, project_id: str) -> dict[str, Any] | None:
    raw = await redis.get(project_key(project_id))
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def delete_project(redis: Any, project_id: str) -> None:
    await redis.delete(project_key(project_id))
