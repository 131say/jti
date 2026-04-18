"""CRUD проектов (Redis) — облачное сохранение и ссылки ?project=."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from models import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectRecord,
    ProjectUpdateRequest,
)
from project_store import get_project, set_project

router = APIRouter(prefix="/api/v1", tags=["projects"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
    except ValueError:
        return False
    return True


@router.post("/projects", response_model=ProjectCreateResponse)
async def create_project(request: Request, body: ProjectCreateRequest) -> ProjectCreateResponse:
    redis = request.app.state.redis
    project_id = str(uuid.uuid4())
    now = _utc_now_iso()
    record = ProjectRecord(
        project_id=project_id,
        name=body.name.strip() or "Untitled Project",
        version="2.0",
        blueprint=body.blueprint,
        last_artifacts=body.last_artifacts,
        created_at=now,
        updated_at=now,
    )
    await set_project(redis, project_id, record.model_dump(mode="json"))
    return ProjectCreateResponse(project_id=project_id)


@router.get("/projects/{project_id}", response_model=ProjectRecord)
async def read_project(project_id: str, request: Request) -> ProjectRecord:
    if not _is_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a UUID")
    redis = request.app.state.redis
    raw = await get_project(redis, project_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        return ProjectRecord.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"stored project is invalid: {e!s}",
        ) from e


@router.put("/projects/{project_id}", response_model=ProjectRecord)
async def update_project(
    project_id: str,
    request: Request,
    body: ProjectUpdateRequest,
) -> ProjectRecord:
    if not _is_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a UUID")
    redis = request.app.state.redis
    raw = await get_project(redis, project_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        current = ProjectRecord.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"stored project is invalid: {e!s}",
        ) from e

    name = body.name.strip() if body.name is not None else current.name
    if not name:
        name = "Untitled Project"
    blueprint = body.blueprint if body.blueprint is not None else current.blueprint
    last_artifacts = (
        body.last_artifacts
        if body.last_artifacts is not None
        else current.last_artifacts
    )

    updated = ProjectRecord(
        project_id=current.project_id,
        name=name,
        version="2.0",
        blueprint=blueprint,
        last_artifacts=last_artifacts,
        created_at=current.created_at,
        updated_at=_utc_now_iso(),
    )
    await set_project(redis, project_id, updated.model_dump(mode="json"))
    return updated
