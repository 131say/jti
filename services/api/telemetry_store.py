"""Сохранение продуктовой телеметрии (события воронки) в Redis."""

from __future__ import annotations

import json
from typing import Any

TELEMETRY_LIST_KEY = "telemetry:v1"
TELEMETRY_MAX = 50_000


async def append_telemetry(redis: Any, record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False)
    await redis.lpush(TELEMETRY_LIST_KEY, line)
    await redis.ltrim(TELEMETRY_LIST_KEY, 0, TELEMETRY_MAX - 1)
