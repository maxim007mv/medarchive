"""Sign-in data access through the SECURITY DEFINER functions of migration 0002 (ADR-044).

`ma_app` cannot write workspaces, sessions or access keys directly. Functions marked "inside
workspace_tx" take the workspace from `app.workspace_id`; the others run before a workspace is
known: they look a session or key up by its hash, or claim a creation key.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import IPv4Network, IPv6Network
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SESSION_IDLE_TTL = timedelta(days=30)
SESSION_ABSOLUTE_TTL = timedelta(days=180)

IpPrefix = IPv4Network | IPv6Network

# Plain INSERT: the ORM would add RETURNING, and ma_app may not read the append-only journal.
_INSERT_AUDIT = text(
    "INSERT INTO app.audit_log (workspace_id, session_id, action, request_id, ip_prefix)"
    " VALUES (:workspace_id, :session_id, :action, :request_id, :ip_prefix)"
)


@dataclass(frozen=True, slots=True)
class NewSession:
    session_id: UUID
    idle_expires_at: datetime


@dataclass(frozen=True, slots=True)
class FoundAccessKey:
    workspace_id: UUID
    secret_hash: str


@dataclass(frozen=True, slots=True)
class CreateKeyClaim:
    is_new: bool
    state: str
    fingerprint: bytes
    workspace_id: UUID | None
    response_body_ct: bytes | None


async def claim_workspace_create_key(
    db: AsyncSession, key_sha256: bytes, fingerprint: bytes
) -> CreateKeyClaim:
    row = (
        await db.execute(
            text(
                "SELECT is_new, state, fingerprint, workspace_id, response_body_ct"
                " FROM app.claim_workspace_create_key(:key_sha256, :fingerprint)"
            ),
            {"key_sha256": key_sha256, "fingerprint": fingerprint},
        )
    ).one()
    return CreateKeyClaim(
        is_new=row.is_new,
        state=row.state,
        fingerprint=row.fingerprint,
        workspace_id=row.workspace_id,
        response_body_ct=row.response_body_ct,
    )


async def complete_workspace_create_key(
    db: AsyncSession, key_sha256: bytes, response_status: int, response_body_ct: bytes
) -> None:
    """Inside workspace_tx of the created workspace."""
    await db.execute(
        text("SELECT app.complete_workspace_create_key(:key_sha256, :status, :body)"),
        {"key_sha256": key_sha256, "status": response_status, "body": response_body_ct},
    )


async def release_workspace_create_key(db: AsyncSession, key_sha256: bytes) -> None:
    await db.execute(
        text("SELECT app.release_workspace_create_key(:key_sha256)"), {"key_sha256": key_sha256}
    )


async def create_workspace(
    db: AsyncSession,
    *,
    dek_ciphertext: bytes,
    kek_key_id: str,
    policy_version: str,
    evidence_sha256: bytes,
) -> datetime:
    """Inside workspace_tx of the new id: workspace row and accepted consent; returns created_at."""
    created_at: datetime = (
        await db.execute(
            text("SELECT app.create_workspace(:dek, :kek_key_id, :policy_version, :evidence)"),
            {
                "dek": dek_ciphertext,
                "kek_key_id": kek_key_id,
                "policy_version": policy_version,
                "evidence": evidence_sha256,
            },
        )
    ).scalar_one()
    return created_at


async def create_session(db: AsyncSession, token_sha256: bytes) -> NewSession | None:
    """Inside workspace_tx; None if the workspace is deleted."""
    row = (
        await db.execute(
            text(
                "SELECT session_id, idle_expires_at"
                " FROM app.create_session(:token_sha256, :idle_ttl, :absolute_ttl)"
            ),
            {
                "token_sha256": token_sha256,
                "idle_ttl": SESSION_IDLE_TTL,
                "absolute_ttl": SESSION_ABSOLUTE_TTL,
            },
        )
    ).one_or_none()
    return None if row is None else NewSession(row.session_id, row.idle_expires_at)


async def touch_session(db: AsyncSession, session_id: UUID) -> datetime | None:
    """Inside workspace_tx: extend the idle timeout (never past the absolute one)."""
    idle_expires_at: datetime | None = (
        await db.execute(
            text("SELECT app.touch_session(:session_id, :idle_ttl)"),
            {"session_id": session_id, "idle_ttl": SESSION_IDLE_TTL},
        )
    ).scalar_one()
    return idle_expires_at


async def revoke_session(db: AsyncSession, session_id: UUID) -> None:
    """Inside workspace_tx."""
    await db.execute(text("SELECT app.revoke_sessions(:session_id)"), {"session_id": session_id})


async def issue_access_key(db: AsyncSession, lookup_id: str, secret_hash: str) -> bool:
    """Inside workspace_tx: revoke the active key and add a new one; True if one was revoked."""
    revoked_previous: bool = (
        await db.execute(
            text("SELECT revoked_previous FROM app.issue_access_key(:lookup_id, :secret_hash)"),
            {"lookup_id": lookup_id, "secret_hash": secret_hash},
        )
    ).scalar_one()
    return revoked_previous


async def find_access_key(db: AsyncSession, lookup_id: str) -> FoundAccessKey | None:
    """Active key of a live workspace by its public lookup id."""
    row = (
        await db.execute(
            text("SELECT workspace_id, secret_hash FROM app.find_access_key(:lookup_id)"),
            {"lookup_id": lookup_id},
        )
    ).one_or_none()
    return None if row is None else FoundAccessKey(row.workspace_id, row.secret_hash)


async def add_audit(
    db: AsyncSession,
    workspace_id: UUID,
    action: str,
    *,
    session_id: UUID | None,
    request_id: str,
    ip_prefix: IpPrefix | None,
) -> None:
    """Inside workspace_tx: one append-only audit row without any field values."""
    await db.execute(
        _INSERT_AUDIT,
        {
            "workspace_id": workspace_id,
            "action": action,
            "session_id": session_id,
            "request_id": request_id,
            "ip_prefix": ip_prefix,
        },
    )
