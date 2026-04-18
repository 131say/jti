"""Индекс проектов по владельцу (Redis sorted set: score = unix time)."""

from __future__ import annotations

import time
from typing import Any


def owner_index_key(owner_id: str) -> str:
    return f"aiforge:user_projects:{owner_id}"


async def index_add_project(redis: Any, owner_id: str, project_id: str) -> None:
    await redis.zadd(owner_index_key(owner_id), {project_id: time.time()})


async def index_touch_project(redis: Any, owner_id: str, project_id: str) -> None:
    """Обновить позицию в списке «недавние» (после PUT)."""
    await redis.zadd(owner_index_key(owner_id), {project_id: time.time()})


async def index_remove_project(redis: Any, owner_id: str, project_id: str) -> None:
    await redis.zrem(owner_index_key(owner_id), project_id)


async def list_project_ids_for_owner(redis: Any, owner_id: str) -> list[str]:
    raw = await redis.zrevrange(owner_index_key(owner_id), 0, -1)
    out: list[str] = []
    for x in raw:
        out.append(x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x))
    return out
