"""Верификация Google Sign-In (ID token)."""

from __future__ import annotations

import os
from typing import Any

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as ga_requests

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def require_google_client_id() -> str:
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID is not set")
    return GOOGLE_CLIENT_ID


def verify_google_credential(credential: str) -> dict[str, Any]:
    """
    credential — строка JWT из Google Login / One Tap (поле credential).
    """
    cid = require_google_client_id()
    req = ga_requests.Request()
    # google-auth проверяет audience, срок и подпись.
    info: dict[str, Any] = google_id_token.verify_oauth2_token(
        credential,
        req,
        cid,
    )
    if info.get("sub") is None:
        raise ValueError("Google token has no sub")
    return info
