"""Загрузка артефактов в S3-совместимое хранилище (MinIO)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

_S3_CONFIG = Config(signature_version="s3v4", s3={"addressing_style": "path"})


def _env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def build_s3_client(*, endpoint_url: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=_env("S3_ACCESS_KEY", "aiforge"),
        aws_secret_access_key=_env("S3_SECRET_KEY", "aiforge_secret"),
        region_name=os.environ.get("S3_REGION", "us-east-1"),
        config=_S3_CONFIG,
    )


def ensure_bucket_exists(s3: Any, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchBucket", "NotFound"):
            s3.create_bucket(Bucket=bucket)
            return
        raise


def upload_artifact(
    s3: Any,
    *,
    bucket: str,
    local_path: Path,
    object_key: str,
) -> None:
    s3.upload_file(str(local_path), bucket, object_key)


def get_bucket_name() -> str:
    return os.environ.get("S3_BUCKET", "artifacts")
