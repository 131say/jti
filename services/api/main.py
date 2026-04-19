from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from routes.auth import router as auth_router
from routes.jobs import router as jobs_router
from routes.leads import router as leads_router
from routes.projects import router as projects_router
from routes.telemetry import router as telemetry_router
from storage import build_s3_client, ensure_bucket_exists, get_bucket_name

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
S3_EXTERNAL_ENDPOINT = os.environ.get("S3_EXTERNAL_ENDPOINT", S3_ENDPOINT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    app.state.redis = Redis.from_url(REDIS_URL)
    app.state.arq_pool = await create_pool(redis_settings)

    bucket = get_bucket_name()
    app.state.s3_bucket = bucket
    app.state.s3_internal = build_s3_client(endpoint_url=S3_ENDPOINT)
    ensure_bucket_exists(app.state.s3_internal, bucket)
    app.state.s3_presign = build_s3_client(endpoint_url=S3_EXTERNAL_ENDPOINT)

    try:
        yield
    finally:
        await app.state.arq_pool.close()
        await app.state.redis.aclose()


app = FastAPI(title="AI-Forge API", version="0.1.0", lifespan=lifespan)

_cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(leads_router)
app.include_router(telemetry_router)


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
