"""Состояние задач в Redis (общий формат для API и Arq-воркера)."""

from __future__ import annotations

import json
from typing import Any

JOB_KEY_PREFIX = "aiforge:job:"


def job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


async def set_job_state(redis: Any, job_id: str, state: dict[str, Any]) -> None:
    await redis.set(job_key(job_id), json.dumps(state, ensure_ascii=False))


async def get_job_state(redis: Any, job_id: str) -> dict[str, Any] | None:
    raw = await redis.get(job_key(job_id))
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)
