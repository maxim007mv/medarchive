"""Throwaway MinIO for integration tests.

On Docker Desktop for macOS run with TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock:
the Ryuk reaper cannot mount ~/.docker/run/docker.sock.
"""

from collections.abc import Iterator

import boto3
import pytest
from testcontainers.community.minio import MinioContainer

from app.storage.s3 import ObjectStorage

MINIO_IMAGE = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
QUARANTINE_BUCKET, DOCS_BUCKET = "ma-quarantine", "ma-docs"


@pytest.fixture(scope="session")
def storage() -> Iterator[ObjectStorage]:
    """Both buckets in a throwaway MinIO; the API credentials are the root user here."""
    with MinioContainer(image=MINIO_IMAGE) as minio:
        config = minio.get_config()
        endpoint = f"http://{config['endpoint']}"
        admin = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name="us-east-1",
        )
        for bucket in (QUARANTINE_BUCKET, DOCS_BUCKET):
            admin.create_bucket(Bucket=bucket)
        yield ObjectStorage(
            endpoint=endpoint,
            public_endpoint=endpoint,
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            quarantine_bucket=QUARANTINE_BUCKET,
            docs_bucket=DOCS_BUCKET,
        )
