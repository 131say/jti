from __future__ import annotations

import asyncio
import uuid

from arq.connections import ArqRedis
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from redis.asyncio import Redis

from core.mate_solver import MateResolutionError
from core.resolver import BlueprintResolutionError, finalize_resolved_blueprint
from job_store import get_job_state, set_job_state
from models import (
    JobArtifacts,
    JobBom,
    JobCreateResponse,
    JobDiagnostics,
    JobStatusResponse,
    ResolvedBlueprintPayload,
)
from models_raw import RawBlueprintPayload
from services.ai_service import (
    AiBlueprintValidationError,
    AiJsonExtractionError,
    AiMissingApiKeyError,
    AiModelError,
    AiServiceError,
    generate_blueprint_from_prompt,
)
from storage import presigned_get_url

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(request: Request) -> JobCreateResponse:
    redis: Redis = request.app.state.redis
    pool: ArqRedis = request.app.state.arq_pool

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Ожидался JSON-объект")

    if "prompt" in body:
        if "metadata" in body:
            raise HTTPException(
                status_code=400,
                detail="Нельзя одновременно передавать prompt и поля Blueprint (например metadata).",
            )
        raw_prompt = body.get("prompt")
        if not isinstance(raw_prompt, str) or not raw_prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="Поле prompt должно быть непустой строкой.",
            )
        current_blueprint: RawBlueprintPayload | None = None
        if "current_blueprint" in body and body["current_blueprint"] is not None:
            cb = body.get("current_blueprint")
            if not isinstance(cb, dict):
                raise HTTPException(
                    status_code=400,
                    detail="current_blueprint должен быть объектом JSON.",
                )
            try:
                cb_raw = RawBlueprintPayload.model_validate(cb)
            except ValidationError as e:
                raise HTTPException(
                    status_code=422,
                    detail=jsonable_encoder(e.errors()),
                ) from e
            try:
                fin = finalize_resolved_blueprint(
                    cb_raw.model_dump(mode="json"), mate_warnings=None
                )
                ResolvedBlueprintPayload.model_validate(fin)
            except BlueprintResolutionError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            except MateResolutionError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            except ValidationError as e:
                raise HTTPException(
                    status_code=422,
                    detail=jsonable_encoder(e.errors()),
                ) from e
            current_blueprint = cb_raw
        diagnostics_context: dict | None = None
        if "diagnostics_context" in body and body["diagnostics_context"] is not None:
            dc = body.get("diagnostics_context")
            if not isinstance(dc, dict):
                raise HTTPException(
                    status_code=400,
                    detail="diagnostics_context должен быть JSON-объектом или null.",
                )
            diagnostics_context = dc

        try:
            payload = await asyncio.to_thread(
                generate_blueprint_from_prompt,
                raw_prompt.strip(),
                current_blueprint,
                diagnostics_context,
            )
        except AiMissingApiKeyError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except AiModelError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        except (AiJsonExtractionError, AiBlueprintValidationError) as e:
            raise HTTPException(
                status_code=422,
                detail=str(e),
            ) from e
        except AiServiceError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
    else:
        try:
            raw_payload = RawBlueprintPayload.model_validate(body)
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=jsonable_encoder(e.errors()),
            ) from e
        try:
            fin = finalize_resolved_blueprint(
                raw_payload.model_dump(mode="json"), mate_warnings=None
            )
            ResolvedBlueprintPayload.model_validate(fin)
        except BlueprintResolutionError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except MateResolutionError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=jsonable_encoder(e.errors()),
            ) from e
        payload = raw_payload

    job_id = str(uuid.uuid4())
    await set_job_state(
        redis,
        job_id,
        {
            "status": "queued",
            "artifacts": None,
            "error": None,
            "bom": None,
            "diagnostics": None,
        },
    )
    await pool.enqueue_job(
        "generate_blueprint_task",
        job_id,
        payload.model_dump(mode="json"),
    )
    return JobCreateResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, request: Request) -> JobStatusResponse:
    redis: Redis = request.app.state.redis
    raw = await get_job_state(redis, job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="job not found")

    artifacts = None
    art = raw.get("artifacts")
    if art:
        if raw.get("status") == "completed" and "glb_key" in art and "step_key" in art:
            s3 = request.app.state.s3_presign
            bucket = request.app.state.s3_bucket
            mjcf_url = None
            if art.get("mjcf_key"):
                mjcf_url = presigned_get_url(
                    s3, bucket=bucket, key=art["mjcf_key"]
                )
            zip_url = None
            if art.get("zip_key"):
                zip_url = presigned_get_url(
                    s3, bucket=bucket, key=art["zip_key"]
                )
            video_url = None
            if art.get("video_key"):
                video_url = presigned_get_url(
                    s3, bucket=bucket, key=art["video_key"]
                )
            script_url = None
            if art.get("script_key"):
                script_url = presigned_get_url(
                    s3, bucket=bucket, key=art["script_key"]
                )
            drawings_urls = None
            raw_dk = art.get("drawings_keys")
            if isinstance(raw_dk, list) and raw_dk:
                drawings_urls = [
                    presigned_get_url(s3, bucket=bucket, key=str(k))
                    for k in raw_dk
                ]
            pdf_url = None
            if art.get("pdf_key"):
                pdf_url = presigned_get_url(
                    s3, bucket=bucket, key=str(art["pdf_key"])
                )
            artifacts = JobArtifacts(
                glb_url=presigned_get_url(
                    s3, bucket=bucket, key=art["glb_key"]
                ),
                step_url=presigned_get_url(
                    s3, bucket=bucket, key=art["step_key"]
                ),
                mjcf_url=mjcf_url,
                zip_url=zip_url,
                video_url=video_url,
                script_url=script_url,
                drawings_urls=drawings_urls,
                pdf_url=pdf_url,
            )
        elif "glb_url" in art and "step_url" in art:
            artifacts = JobArtifacts(**art)

    bom_out: JobBom | None = None
    raw_bom = raw.get("bom")
    if isinstance(raw_bom, dict):
        try:
            bom_out = JobBom.model_validate(raw_bom)
        except ValidationError:
            bom_out = None

    diag_out: JobDiagnostics | None = None
    raw_diag = raw.get("diagnostics")
    if isinstance(raw_diag, dict):
        try:
            diag_out = JobDiagnostics.model_validate(raw_diag)
        except ValidationError:
            diag_out = None

    return JobStatusResponse(
        job_id=job_id,
        status=raw["status"],
        artifacts=artifacts,
        error=raw.get("error"),
        warnings=raw.get("warnings"),
        blueprint=raw.get("blueprint"),
        bom=bom_out,
        diagnostics=diag_out,
    )
