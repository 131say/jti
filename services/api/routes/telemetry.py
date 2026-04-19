"""Приём продуктовых событий с фронта (first-party, обход AdBlock/CORS на сторонние домены)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from telemetry_store import append_telemetry

router = APIRouter(prefix="/api/v1", tags=["telemetry"])

class TelemetryEventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: int | None = Field(default=None, ge=0)
    path: str | None = Field(default=None, max_length=512)

    @field_validator("payload")
    @classmethod
    def payload_not_too_deep(cls, v: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError("payload must be JSON-serializable") from e
        if len(raw.encode("utf-8")) > 32_000:
            raise ValueError("payload too large")
        return v


@router.post("/telemetry")
async def ingest_telemetry(
    request: Request,
    body: TelemetryEventRequest,
) -> dict[str, bool]:
    redis = request.app.state.redis
    rec = {
        "event": body.event.strip()[:128],
        "payload": body.payload,
        "ts": body.ts,
        "path": (body.path or "")[:512] or None,
        "ip": request.client.host if request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:512] or None,
    }
    await append_telemetry(redis, rec)
    return {"ok": True}
