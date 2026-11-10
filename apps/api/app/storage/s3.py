"""S3/MinIO adapter: the quarantine bucket for raw uploads and the docs bucket for ciphertext.

boto3 is synchronous; callers run these methods in a worker thread.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import IO, TYPE_CHECKING, Any, BinaryIO, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.core.errors import ErrorCode, ProblemError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

PDF_CONTENT_TYPE = "application/pdf"
RETRY_AFTER_SECONDS = "60"
_CLIENT_CONFIG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
    connect_timeout=3,
    read_timeout=30,
    retries={"max_attempts": 3, "mode": "standard"},
)
_MISSING_OBJECT_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


class StorageUnavailableError(ProblemError):
    """Object storage did not answer; the API returns 503 `storage_unavailable`."""

    def __init__(self) -> None:
        super().__init__(
            ErrorCode.STORAGE_UNAVAILABLE, headers={"Retry-After": RETRY_AFTER_SECONDS}
        )


@dataclass(frozen=True)
class PresignedPost:
    url: str
    fields: dict[str, str]


@dataclass(frozen=True)
class StoredObject:
    key: str
    last_modified: datetime


class Bucket:
    def __init__(self, client: "S3Client", name: str) -> None:
        self._client = client
        self.name = name

    def size(self, key: str) -> int | None:
        """Size in bytes, or None if there is no such object."""
        try:
            head = self._client.head_object(Bucket=self.name, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _MISSING_OBJECT_CODES:
                return None
            raise StorageUnavailableError from exc
        except BotoCoreError as exc:
            raise StorageUnavailableError from exc
        return head["ContentLength"]

    def download(self, key: str, destination: IO[bytes]) -> None:
        with _unavailable_on_error():
            self._client.download_fileobj(self.name, key, destination)

    def upload(self, key: str, source: IO[bytes]) -> None:
        with _unavailable_on_error():
            self._client.upload_fileobj(source, self.name, key)

    def open(self, key: str) -> BinaryIO:
        """Readable stream of the whole object; the caller closes it."""
        with _unavailable_on_error():
            body = self._client.get_object(Bucket=self.name, Key=key)["Body"]
        # StreamingBody is an io.IOBase with read() and readable(), which is all Tink needs.
        return cast("BinaryIO", body)

    def delete(self, key: str) -> None:
        """Deleting a missing key is a no-op, so retries are safe."""
        with _unavailable_on_error():
            self._client.delete_object(Bucket=self.name, Key=key)

    def list(self, prefix: str) -> Iterator[StoredObject]:
        with _unavailable_on_error():
            pages = self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self.name, Prefix=prefix
            )
            for page in pages:
                for item in page.get("Contents", []):
                    yield StoredObject(key=item["Key"], last_modified=item["LastModified"])


class ObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        public_endpoint: str,
        access_key: str,
        secret_key: str,
        quarantine_bucket: str,
        docs_bucket: str,
    ) -> None:
        credentials: dict[str, Any] = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": "us-east-1",
            "config": _CLIENT_CONFIG,
        }
        client = boto3.client("s3", endpoint_url=endpoint, **credentials)
        # Signing is local; this client only builds URLs for the host the browser can reach.
        self._presign_client = boto3.client("s3", endpoint_url=public_endpoint, **credentials)
        self.quarantine = Bucket(client, quarantine_bucket)
        self.docs = Bucket(client, docs_bucket)

    @classmethod
    def from_settings(cls, settings: Settings) -> "ObjectStorage":
        return cls(
            endpoint=settings.s3_endpoint,
            public_endpoint=settings.s3_public_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key.get_secret_value(),
            quarantine_bucket=settings.s3_bucket_quarantine,
            docs_bucket=settings.s3_bucket_docs,
        )

    def presign_quarantine_upload(
        self, key: str, *, max_bytes: int, expires_in_seconds: int
    ) -> PresignedPost:
        """Browser POST policy for exactly `key`, a PDF content type and 1..max_bytes bytes."""
        post = self._presign_client.generate_presigned_post(
            Bucket=self.quarantine.name,
            Key=key,
            Fields={"Content-Type": PDF_CONTENT_TYPE},
            Conditions=[
                {"Content-Type": PDF_CONTENT_TYPE},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expires_in_seconds,
        )
        return PresignedPost(url=post["url"], fields=dict(post["fields"]))


@contextmanager
def _unavailable_on_error() -> Iterator[None]:
    try:
        yield
    except (ClientError, BotoCoreError) as exc:
        raise StorageUnavailableError from exc
