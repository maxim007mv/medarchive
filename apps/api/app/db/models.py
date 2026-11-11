"""ORM mapping of schema app after migration 0002. Migrations own the DDL; these models do not.

Relationships are lazy="raise": load them with selectinload/joinedload explicitly (no N+1).
sessions, access_keys, workspace_create_keys and purge_queue have no grants for ma_app: they are
mapped for reading in tests and the worker, writes go through the 0002 functions (docs/db.md).
"""

import uuid
from datetime import date, datetime
from ipaddress import IPv4Network, IPv6Network
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Computed,
    DateTime,
    FetchedValue,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    LargeBinary,
    MetaData,
    SmallInteger,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry, relationship

_NOW = text("now()")
_WORKSPACE_FK = "app.workspaces.id"


class Base(DeclarativeBase):
    registry = registry(
        metadata=MetaData(schema="app"),
        type_annotation_map={
            datetime: DateTime(timezone=True),
            bytes: LargeBinary,
            str: Text,
            uuid.UUID: Uuid,
        },
    )


class DocumentType(Base):
    __tablename__ = "document_types"

    code: Mapped[str] = mapped_column(primary_key=True)
    title_ru: Mapped[str]
    sort_order: Mapped[int] = mapped_column(SmallInteger)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    # Tink keyset bundle under KEK (ADR-047); NULL after crypto-erasure (ADR-041).
    dek_ciphertext: Mapped[bytes | None]
    kek_key_id: Mapped[str]
    deleted_at: Mapped[datetime | None]
    purge_after: Mapped[datetime | None]
    # IANA name, e.g. Europe/Moscow; NULL for archives created before migration 0003.
    timezone: Mapped[str | None]


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"))
    policy_version: Mapped[str]
    accepted_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    evidence_sha256: Mapped[bytes]
    withdrawn_at: Mapped[datetime | None]


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"))
    token_sha256: Mapped[bytes]
    created_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    idle_expires_at: Mapped[datetime]
    absolute_expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]


class AccessKey(Base):
    __tablename__ = "access_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"))
    lookup_id: Mapped[str] = mapped_column(CHAR(6))
    secret_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    revoked_at: Mapped[datetime | None]


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"))
    quarantine_key: Mapped[str]
    max_bytes: Mapped[int]
    status: Mapped[str] = mapped_column(server_default=text("'pending'"))
    reject_code: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    expires_at: Mapped[datetime]
    original_name_ct: Mapped[bytes | None]


class Document(Base):
    __tablename__ = "documents"
    # version and updated_at are set by the bump_version trigger: fetch them with RETURNING.
    __mapper_args__ = MappingProxyType({"eager_defaults": True})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"))
    type_code: Mapped[str] = mapped_column(ForeignKey("app.document_types.code"))
    title_ct: Mapped[bytes]
    title_bidx: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    note_ct: Mapped[bytes | None]
    document_date: Mapped[date | None]
    uploaded_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=_NOW, server_onupdate=FetchedValue()
    )
    version: Mapped[int] = mapped_column(server_default=text("1"), server_onupdate=FetchedValue())
    deleted_at: Mapped[datetime | None]
    list_key: Mapped[int] = mapped_column(
        Computed(
            "CASE WHEN document_date IS NULL THEN 2147483647"
            " ELSE (DATE '1900-01-01' - document_date) END",
            persisted=True,
        )
    )

    file: Mapped["DocumentFile | None"] = relationship(lazy="raise")


class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["app.documents.workspace_id", "app.documents.id"],
            ondelete="CASCADE",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID]
    object_key: Mapped[str]
    size_bytes: Mapped[int]
    sha256: Mapped[bytes]
    page_count: Mapped[int | None] = mapped_column(SmallInteger)
    original_name_ct: Mapped[bytes]
    content_type: Mapped[str] = mapped_column(server_default=text("'application/pdf'"))


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(primary_key=True)
    operation: Mapped[str]
    fingerprint: Mapped[bytes]
    state: Mapped[str] = mapped_column(server_default=text("'in_progress'"))
    response_status: Mapped[int | None] = mapped_column(SmallInteger)
    resource_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    expires_at: Mapped[datetime] = mapped_column(server_default=text("now() + interval '24 hours'"))
    # AEAD under the workspace key, AAD = workspace_id + key (ADR-045).
    response_body_ct: Mapped[bytes | None]


class WorkspaceCreateKey(Base):
    __tablename__ = "workspace_create_keys"

    key_sha256: Mapped[bytes] = mapped_column(primary_key=True)
    fingerprint: Mapped[bytes]
    state: Mapped[str] = mapped_column(server_default=text("'in_progress'"))
    response_status: Mapped[int | None] = mapped_column(SmallInteger)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(_WORKSPACE_FK, ondelete="CASCADE")
    )
    response_body_ct: Mapped[bytes | None]
    expires_at: Mapped[datetime] = mapped_column(server_default=text("now() + interval '24 hours'"))


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_WORKSPACE_FK, ondelete="CASCADE"))
    scope: Mapped[str]
    filter: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    document_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    total_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    expires_at: Mapped[datetime] = mapped_column(server_default=text("now() + interval '1 hour'"))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=_NOW)
    workspace_id: Mapped[uuid.UUID]
    session_id: Mapped[uuid.UUID | None]
    action: Mapped[str]
    entity_id: Mapped[uuid.UUID | None]
    # Names of changed fields only, never values.
    changed_fields: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    request_id: Mapped[str | None]
    ip_prefix: Mapped[IPv4Network | IPv6Network | None] = mapped_column(CIDR)


class PurgeQueue(Base):
    __tablename__ = "purge_queue"

    object_key: Mapped[str] = mapped_column(primary_key=True)
    reason: Mapped[str]
    enqueued_at: Mapped[datetime] = mapped_column(server_default=_NOW)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=_NOW)
