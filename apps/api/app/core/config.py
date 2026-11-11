from functools import lru_cache
from pathlib import Path

from pydantic import Field, IPvAnyNetwork, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration from the environment; fails at startup if anything is missing."""

    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    database_url: str
    redis_url: str

    s3_endpoint: str
    # Endpoint the browser sees in presigned POST URLs (the compose network name is not reachable).
    s3_public_endpoint: str
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_bucket_quarantine: str = "ma-quarantine"
    s3_bucket_docs: str = "ma-docs"

    # Tink keyset file mounted as a Docker secret (ADR-041); the key itself never enters the env.
    kek_keyset_path: Path

    csrf_secret: SecretStr = Field(min_length=32)
    # Two active keys during rotation: the current one encrypts, both decrypt (08-security, 5).
    page_token_key: SecretStr = Field(min_length=32)
    page_token_key_previous: SecretStr | None = None

    # Proxies whose X-Forwarded-For is believed, e.g. the compose network of the Next.js
    # container (ADR-048): `TRUSTED_PROXIES='["172.16.0.0/12"]'`. Empty = only the TCP peer.
    trusted_proxies: list[IPvAnyNetwork] = []
    # Off only for functional E2E and load runs of the gate; TC-082 and TC-098 need it on.
    rate_limits_enabled: bool = True

    log_level: str = "INFO"
    # Empty locally: Sentry is not initialised at all.
    sentry_dsn: str = ""
    environment: str = "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
