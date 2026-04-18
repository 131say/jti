"""CRUD проектов (Redis) с владельцем, приватностью и индексом workspace."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from auth_deps import get_optional_user, require_user
from auth_jwt import AuthUserClaims
from models import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectForkResponse,
    ProjectListResponse,
    ProjectRecord,
    ProjectSummary,
    ProjectUpdateRequest,
)
from project_index import (
    index_add_project,
    index_remove_project,
    index_touch_project,
    list_project_ids_for_owner,
)
from project_store import delete_project, get_project, set_project

router = APIRouter(prefix="/api/v1", tags=["projects"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
    except ValueError:
        return False
    return True


def _can_read_project(rec: ProjectRecord, user: AuthUserClaims | None) -> bool:
    """Legacy без owner_id — чтение для всех."""
    if rec.owner_id is None:
        return True
    if rec.is_public:
        return True
    if user is not None and user.sub == rec.owner_id:
        return True
    return False


@router.get("/projects", response_model=ProjectListResponse)
async def list_my_projects(
    request: Request,
    user: AuthUserClaims = Depends(require_user),
) -> ProjectListResponse:
    redis = request.app.state.redis
    ids = await list_project_ids_for_owner(redis, user.sub)
    summaries: list[ProjectSummary] = []
    for pid in ids:
        raw = await get_project(redis, pid)
        if raw is None:
            continue
        try:
            rec = ProjectRecord.model_validate(raw)
        except ValidationError:
            continue
        if rec.owner_id != user.sub:
            continue
        summaries.append(
            ProjectSummary(
                project_id=rec.project_id,
                name=rec.name,
                owner_id=rec.owner_id,
                is_public=rec.is_public,
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )
        )
    return ProjectListResponse(projects=summaries)


@router.post("/projects", response_model=ProjectCreateResponse)
async def create_project(
    request: Request,
    body: ProjectCreateRequest,
    user: AuthUserClaims = Depends(require_user),
) -> ProjectCreateResponse:
    redis = request.app.state.redis
    project_id = str(uuid.uuid4())
    now = _utc_now_iso()
    record = ProjectRecord(
        project_id=project_id,
        owner_id=user.sub,
        is_public=False,
        name=body.name.strip() or "Untitled Project",
        version="2.0",
        blueprint=body.blueprint,
        last_artifacts=body.last_artifacts,
        created_at=now,
        updated_at=now,
    )
    await set_project(redis, project_id, record.model_dump(mode="json"))
    await index_add_project(redis, user.sub, project_id)
    return ProjectCreateResponse(project_id=project_id)


@router.get("/projects/{project_id}", response_model=ProjectRecord)
async def read_project(
    project_id: str,
    request: Request,
    user: AuthUserClaims | None = Depends(get_optional_user),
) -> ProjectRecord:
    if not _is_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a UUID")
    redis = request.app.state.redis
    raw = await get_project(redis, project_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        rec = ProjectRecord.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"stored project is invalid: {e!s}",
        ) from e
    if not _can_read_project(rec, user):
        raise HTTPException(status_code=403, detail="нет доступа к проекту")
    return rec


@router.put("/projects/{project_id}", response_model=ProjectRecord)
async def update_project(
    project_id: str,
    request: Request,
    body: ProjectUpdateRequest,
    user: AuthUserClaims = Depends(require_user),
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

    claimed = False
    if current.owner_id is None:
        claimed = True
    elif current.owner_id != user.sub:
        raise HTTPException(status_code=403, detail="только владелец может изменять проект")

    name = body.name.strip() if body.name is not None else current.name
    if not name:
        name = "Untitled Project"
    blueprint = body.blueprint if body.blueprint is not None else current.blueprint
    last_artifacts = (
        body.last_artifacts
        if body.last_artifacts is not None
        else current.last_artifacts
    )
    is_public = current.is_public
    if body.is_public is not None:
        is_public = body.is_public

    owner_id = user.sub if claimed else current.owner_id

    updated = ProjectRecord(
        project_id=current.project_id,
        owner_id=owner_id,
        is_public=is_public,
        name=name,
        version="2.0",
        blueprint=blueprint,
        last_artifacts=last_artifacts,
        created_at=current.created_at,
        updated_at=_utc_now_iso(),
    )
    await set_project(redis, project_id, updated.model_dump(mode="json"))
    if claimed:
        await index_add_project(redis, user.sub, project_id)
    else:
        await index_touch_project(redis, user.sub, project_id)
    return updated


@router.delete("/projects/{project_id}")
async def remove_project(
    project_id: str,
    request: Request,
    user: AuthUserClaims = Depends(require_user),
) -> dict[str, str]:
    if not _is_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a UUID")
    redis = request.app.state.redis
    raw = await get_project(redis, project_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        current = ProjectRecord.model_validate(raw)
    except ValidationError:
        raise HTTPException(status_code=500, detail="stored project is invalid") from None
    if current.owner_id is None:
        raise HTTPException(
            status_code=403,
            detail="удаление legacy-проекта без владельца запрещено",
        )
    if current.owner_id != user.sub:
        raise HTTPException(status_code=403, detail="только владелец может удалить проект")
    await index_remove_project(redis, user.sub, project_id)
    await delete_project(redis, project_id)
    return {"status": "deleted"}


@router.post("/projects/{project_id}/fork", response_model=ProjectForkResponse)
async def fork_project(
    project_id: str,
    request: Request,
    user: AuthUserClaims = Depends(require_user),
) -> ProjectForkResponse:
    if not _is_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a UUID")
    redis = request.app.state.redis
    raw = await get_project(redis, project_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        src = ProjectRecord.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"stored project is invalid: {e!s}",
        ) from e
    if not _can_read_project(src, user):
        raise HTTPException(status_code=403, detail="нет доступа к проекту")

    new_id = str(uuid.uuid4())
    now = _utc_now_iso()
    base_name = src.name.strip() or "Untitled Project"
    fork_name = base_name if base_name.endswith(" (копия)") else f"{base_name} (копия)"

    dup = ProjectRecord(
        project_id=new_id,
        owner_id=user.sub,
        is_public=False,
        name=fork_name,
        version="2.0",
        blueprint=src.blueprint,
        last_artifacts=src.last_artifacts,
        created_at=now,
        updated_at=now,
    )
    await set_project(redis, new_id, dup.model_dump(mode="json"))
    await index_add_project(redis, user.sub, new_id)
    return ProjectForkResponse(project_id=new_id)
