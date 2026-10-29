"""OPTIONAL: copy the quality report to an S3 bucket.

Disabled unless ATLAS_S3_BUCKET is set. boto3 is imported lazily, so the rest of the
project (and the tests) never need it or an AWS account.
"""
from __future__ import annotations

import os
from pathlib import Path


def export_report(report_path: Path, client=None, bucket: str | None = None, prefix: str = "atlas/reports/") -> str | None:
    bucket = bucket or os.environ.get("ATLAS_S3_BUCKET")
    if not bucket:
        return None
    if client is None:
        import boto3  # optional dependency: pip install ".[aws]"

        client = boto3.client("s3")
    key = f"{prefix}{report_path.name}"
    client.upload_file(str(report_path), bucket, key)
    return f"s3://{bucket}/{key}"
