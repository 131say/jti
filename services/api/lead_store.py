"""Сохранение лидов в Redis (список JSON, MVP)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

LEADS_LIST_KEY = "leads:v1"
LEADS_MAX = 10_000


async def append_lead(redis: Any, record: dict[str, Any]) -> None:
    """LPUSH + LTRIM: новые сверху."""
    line = json.dumps(record, ensure_ascii=False)
    await redis.lpush(LEADS_LIST_KEY, line)
    await redis.ltrim(LEADS_LIST_KEY, 0, LEADS_MAX - 1)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
