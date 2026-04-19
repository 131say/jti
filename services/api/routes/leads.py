"""Публичный сбор лидов (waitlist / feedback)."""

from __future__ import annotations

import asyncio
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from lead_store import append_lead, utc_iso

router = APIRouter(prefix="/api/v1", tags=["leads"])

_INTENTS = frozenset({"hobby", "startup", "enterprise"})


class LeadCreateRequest(BaseModel):
    email: EmailStr
    source: str = Field(min_length=1, max_length=128)
    intent: str = Field(min_length=1, max_length=32)
    message: str | None = Field(default=None, max_length=4000)


class LeadCreateResponse(BaseModel):
    ok: bool = True


def _telegram_notify_sync(text: str) -> None:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3500]}).encode(
        "utf-8"
    )
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        urllib.request.urlopen(req, timeout=6)  # noqa: S310
    except (urllib.error.URLError, OSError):
        return


@router.post("/leads", response_model=LeadCreateResponse)
async def create_lead(request: Request, body: LeadCreateRequest) -> LeadCreateResponse:
    intent = body.intent.strip().lower()
    if intent not in _INTENTS:
        raise HTTPException(
            status_code=422,
            detail=f"intent must be one of: {', '.join(sorted(_INTENTS))}",
        )
    redis = request.app.state.redis
    rec = {
        "email": str(body.email).strip().lower(),
        "source": body.source.strip()[:128],
        "intent": intent,
        "message": (body.message or "").strip()[:4000] or None,
        "created_at": utc_iso(),
        "ip": request.client.host if request.client else None,
    }
    await append_lead(redis, rec)

    lines = [
        "🛠 AI-Forge lead",
        f"email: {rec['email']}",
        f"source: {rec['source']}",
        f"intent: {rec['intent']}",
    ]
    if rec["message"]:
        lines.append(f"message: {rec['message'][:500]}")
    text = "\n".join(lines)
    await asyncio.to_thread(_telegram_notify_sync, text)

    return LeadCreateResponse(ok=True)
