"""Arq-воркер: генерация по Blueprint (CadQuery + MinIO)."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from arq.connections import RedisSettings
from dotenv import load_dotenv

_services_root = Path(__file__).resolve().parent.parent
load_dotenv(_services_root / ".env")

if str(_services_root) not in sys.path:
    sys.path.insert(0, str(_services_root))

from pydantic import ValidationError  # noqa: E402

from api.core.resolver import BlueprintResolutionError, resolve_blueprint_variables  # noqa: E402
from api.job_store import set_job_state  # noqa: E402
from api.models import ResolvedBlueprintPayload  # noqa: E402

from .core.bom import build_bom_from_blueprint, write_bom_csv  # noqa: E402
from .core.diagnostics import run_engineering_diagnostics  # noqa: E402
from .core.mjcf_gen import build_mjcf_xml  # noqa: E402
from .core.simulation import run_headless_simulation  # noqa: E402
from .core.python_exporter import generate_python_script  # noqa: E402
from .generator import (  # noqa: E402
    BlueprintGenerationError,
    build_assembly_from_blueprint,
    create_project_zip,
    export_artifacts,
    export_individual_parts_to_dir,
)
from .storage import (  # noqa: E402
    build_s3_client,
    ensure_bucket_exists,
    get_bucket_name,
    upload_artifact,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")

logger = logging.getLogger(__name__)


async def generate_blueprint_task(ctx, job_id: str, blueprint: dict) -> None:
    redis = ctx["redis"]
    bucket = get_bucket_name()
    s3 = build_s3_client(endpoint_url=S3_ENDPOINT)

    raw_blueprint = copy.deepcopy(blueprint)
    try:
        resolved_blueprint = resolve_blueprint_variables(copy.deepcopy(raw_blueprint))
        ResolvedBlueprintPayload.model_validate(resolved_blueprint)
    except BlueprintResolutionError as e:
        await set_job_state(
            redis,
            job_id,
            {
                "status": "failed",
                "artifacts": None,
                "error": str(e),
                "bom": None,
                "diagnostics": None,
            },
        )
        return
    except ValidationError as e:
        await set_job_state(
            redis,
            job_id,
            {
                "status": "failed",
                "artifacts": None,
                "error": f"Resolved blueprint validation: {json.dumps(e.errors(), default=str)}",
                "bom": None,
                "diagnostics": None,
            },
        )
        return

    def _upload_sync() -> tuple[
        str,
        str,
        str,
        str | None,
        str | None,
        list[str],
        dict,
        dict,
    ]:
        ensure_bucket_exists(s3, bucket)
        job_warnings: list[str] = []
        assembly = build_assembly_from_blueprint(resolved_blueprint, job_warnings)
        video_key: str | None = None
        script_key: str | None = None
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            assembly_dir = base / "assembly"
            parts_dir = base / "parts"
            scripts_dir = base / "scripts"
            sim_dir = base / "simulation"

            export_individual_parts_to_dir(
                resolved_blueprint, parts_dir, job_warnings
            )
            step_path, glb_path = export_artifacts(assembly, assembly_dir)

            bom = build_bom_from_blueprint(resolved_blueprint, job_warnings)
            write_bom_csv(base / "bom.csv", bom)

            diagnostics = run_engineering_diagnostics(resolved_blueprint, job_warnings)

            scripts_dir.mkdir(parents=True, exist_ok=True)
            sim_dir.mkdir(parents=True, exist_ok=True)
            xml_path = sim_dir / "simulation.xml"
            xml_path.write_text(build_mjcf_xml(resolved_blueprint), encoding="utf-8")
            (scripts_dir / "build_model.py").write_text(
                generate_python_script(resolved_blueprint),
                encoding="utf-8",
            )

            mp4_path = sim_dir / "physics_preview.mp4"
            try:
                sim_err = run_headless_simulation(xml_path, mp4_path)
            except Exception as e:
                msg = f"physics preview: неожиданная ошибка симуляции: {e!s}"
                logger.warning("%s", msg, exc_info=True)
                job_warnings.append(msg)
            else:
                if sim_err is not None:
                    job_warnings.extend(sim_err)
                else:
                    vk = f"{job_id}/physics_preview.mp4"
                    try:
                        upload_artifact(
                            s3,
                            bucket=bucket,
                            local_path=mp4_path,
                            object_key=vk,
                        )
                        video_key = vk
                    except Exception as e:
                        msg = (
                            f"physics preview: не удалось загрузить MP4 в S3: {e!s}"
                        )
                        logger.warning("%s", msg, exc_info=True)
                        job_warnings.append(msg)

            zip_path = base / "project.zip"
            create_project_zip(base, zip_path)

            glb_key = f"{job_id}/model.glb"
            step_key = f"{job_id}/model.step"
            zip_key = f"{job_id}/project.zip"
            sk = f"{job_id}/build_model.py"
            upload_artifact(s3, bucket=bucket, local_path=glb_path, object_key=glb_key)
            upload_artifact(s3, bucket=bucket, local_path=step_path, object_key=step_key)
            upload_artifact(s3, bucket=bucket, local_path=zip_path, object_key=zip_key)
            upload_artifact(
                s3,
                bucket=bucket,
                local_path=scripts_dir / "build_model.py",
                object_key=sk,
            )
            script_key = sk
        return glb_key, step_key, zip_key, video_key, script_key, job_warnings, bom, diagnostics

    try:
        await set_job_state(
            redis,
            job_id,
            {"status": "in_progress", "artifacts": None, "error": None},
        )
        glb_key, step_key, zip_key, video_key, script_key, job_warnings, bom, diagnostics = (
            await asyncio.to_thread(_upload_sync)
        )
        artifacts: dict = {
            "glb_key": glb_key,
            "step_key": step_key,
            "zip_key": zip_key,
        }
        if video_key:
            artifacts["video_key"] = video_key
        if script_key:
            artifacts["script_key"] = script_key
        await set_job_state(
            redis,
            job_id,
            {
                "status": "completed",
                "artifacts": artifacts,
                "error": None,
                "warnings": job_warnings,
                "blueprint": raw_blueprint,
                "bom": bom,
                "diagnostics": diagnostics,
            },
        )
    except BlueprintGenerationError as e:
        await set_job_state(
            redis,
            job_id,
            {
                "status": "failed",
                "artifacts": None,
                "error": str(e),
                "bom": None,
                "diagnostics": None,
            },
        )
    except Exception as e:
        await set_job_state(
            redis,
            job_id,
            {
                "status": "failed",
                "artifacts": None,
                "error": str(e),
                "bom": None,
                "diagnostics": None,
            },
        )


class WorkerSettings:
    functions = [generate_blueprint_task]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    job_timeout = 600
