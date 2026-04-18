"""Вход через Google (credential) и выпуск JWT для API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from auth_deps import require_user
from auth_google import verify_google_credential
from auth_jwt import AuthUserClaims, JWT_EXP_DAYS, create_access_token
from models import AuthTokenResponse, AuthUserPublic, GoogleAuthRequest
from user_store import upsert_user_profile

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/google", response_model=AuthTokenResponse)
async def auth_google(request: Request, body: GoogleAuthRequest) -> AuthTokenResponse:
    redis = request.app.state.redis
    try:
        info = verify_google_credential(body.credential)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google: {e!s}") from e

    sub = str(info["sub"])
    email = str(info.get("email") or "")
    name = str(info.get("name") or (email or "User"))
    raw_pic = info.get("picture")
    avatar_url = str(raw_pic) if raw_pic else None

    await upsert_user_profile(
        redis,
        sub,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )

    token = create_access_token(
        sub=sub, email=email, name=name, picture=avatar_url
    )
    expires_in = JWT_EXP_DAYS * 86400
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=AuthUserPublic(
            id=sub,
            email=email,
            name=name,
            avatar_url=avatar_url,
        ),
    )


@router.get("/auth/me", response_model=AuthUserPublic)
async def auth_me(user: AuthUserClaims = Depends(require_user)) -> AuthUserPublic:
    return AuthUserPublic(
        id=user.sub,
        email=user.email,
        name=user.name,
        avatar_url=user.picture,
    )
