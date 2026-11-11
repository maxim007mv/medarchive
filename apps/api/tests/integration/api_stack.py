"""The real application over throwaway PostgreSQL, MinIO and Redis, for API-level tests.

`database` and `storage` come from conftest.py; this module adds Redis, a KEK file and the app
with its lifespan. Each client gets its own address: limits are per IP and Redis is shared.
"""

import secrets
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import tink
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from testcontainers.community.redis import RedisContainer
from tink import aead, json_proto_keyset_format, secret_key_access

from app.core.config import Settings
from app.main import create_app
from app.storage.s3 import ObjectStorage

REDIS_IMAGE = "redis:7-alpine"
BASE_URL = "https://api.test"
POLICY_VERSION = "2026-11-10"
CONSENT = {"consent": {"policy_version": POLICY_VERSION, "accepted": True}}
ACCESS_KEY_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){5}$"


def redis_container() -> Iterator[str]:
    with RedisContainer(REDIS_IMAGE) as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


def write_kek(path: Path) -> Path:
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    path.write_text(json_proto_keyset_format.serialize(handle, secret_key_access.TOKEN))
    return path


def settings_for(database_url: str, redis_url: str, kek_path: Path) -> Settings:
    # S3 values are placeholders: the app gets the test ObjectStorage after startup.
    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        s3_endpoint="http://storage.invalid",
        s3_public_endpoint="http://storage.invalid",
        s3_access_key="unused",
        s3_secret_key="unused",  # noqa: S106  # placeholder, never sent anywhere
        kek_keyset_path=kek_path,
        csrf_secret=secrets.token_urlsafe(32),
        page_token_key=secrets.token_urlsafe(32),
    )


@dataclass
class Api:
    app: FastAPI

    def client(self, ip: str | None = None) -> AsyncClient:
        address = (
            ip or f"10.{secrets.randbelow(250)}.{secrets.randbelow(250)}.{secrets.randbelow(250)}"
        )
        return AsyncClient(
            transport=ASGITransport(app=self.app, client=(address, 40000)), base_url=BASE_URL
        )


@asynccontextmanager
async def running_api(settings: Settings, storage: ObjectStorage) -> AsyncIterator[Api]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        app.state.storage = storage
        yield Api(app)


async def create_archive(client: AsyncClient, key: str | None = None) -> Response:
    """POST /workspaces with accepted consent; the session cookie stays in the client."""
    response = await client.post(
        "/api/v1/workspaces",
        json=CONSENT,
        headers={"Idempotency-Key": key or secrets.token_hex(16)},
    )
    assert response.status_code == 201, response.text
    return response


def csrf(response: Response) -> dict[str, str]:
    return {"X-CSRF-Token": response.json()["csrf_token"]}
