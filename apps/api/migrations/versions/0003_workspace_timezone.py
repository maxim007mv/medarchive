"""Workspace time zone for GET /session (expand only).

Revision ID: 0003_workspace_timezone
Revises: 0002_privileges_functions

A parameter cannot be added with CREATE OR REPLACE, so create_workspace is dropped and created
again; p_timezone defaults to NULL, and four-argument calls resolve to the new function. ma_app
reads the column through its existing SELECT on workspaces under ws_isolation.
"""

from collections.abc import Sequence

from alembic import op

revision = "0003_workspace_timezone"
down_revision: str | None = "0002_privileges_functions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_WORKSPACE = """CREATE FUNCTION app.create_workspace(
  p_dek_ciphertext bytea, p_kek_key_id text, p_policy_version text, p_evidence_sha256 bytea{tz_arg})
RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  workspace uuid := app.require_workspace();
  created timestamptz;
BEGIN
  INSERT INTO app.workspaces (id, dek_ciphertext, kek_key_id{tz_column})
  VALUES (workspace, p_dek_ciphertext, p_kek_key_id{tz_value})
  RETURNING created_at INTO created;
  INSERT INTO app.consents (id, workspace_id, policy_version, evidence_sha256)
  VALUES (gen_random_uuid(), workspace, p_policy_version, p_evidence_sha256);
  RETURN created;
END $$"""
_WITH_TIMEZONE = _CREATE_WORKSPACE.format(
    tz_arg=",\n  p_timezone text DEFAULT NULL", tz_column=", timezone", tz_value=", p_timezone"
)
_WITHOUT_TIMEZONE = _CREATE_WORKSPACE.format(tz_arg="", tz_column="", tz_value="")


def _replace_create_workspace(old_signature: str, new_definition: str, new_signature: str) -> None:
    # Functions are owned by ma_auth (ADR-044): recreate them under its role, as in 0002.
    _execute(
        (
            "GRANT CREATE ON SCHEMA app TO ma_auth",
            "SET LOCAL ROLE ma_auth",
            f"DROP FUNCTION {old_signature}",
            new_definition,
            f"REVOKE ALL ON FUNCTION {new_signature} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION {new_signature} TO ma_app",
            "RESET ROLE",
            "REVOKE CREATE ON SCHEMA app FROM ma_auth",
        )
    )


def _execute(statements: Sequence[str]) -> None:
    # One statement per call: asyncpg prepares every statement and rejects multi-command strings.
    bind = op.get_bind()
    for statement in statements:
        bind.exec_driver_sql(statement)


def upgrade() -> None:
    # IANA name; the API validates it against the zone database, the CHECK only bounds the size.
    _execute(
        (
            """ALTER TABLE app.workspaces ADD COLUMN timezone text
  CONSTRAINT workspaces_timezone_length CHECK (char_length(timezone) BETWEEN 1 AND 64)""",
        )
    )
    _replace_create_workspace(
        "app.create_workspace(bytea, text, text, bytea)",
        _WITH_TIMEZONE,
        "app.create_workspace(bytea, text, text, bytea, text)",
    )


def downgrade() -> None:
    _replace_create_workspace(
        "app.create_workspace(bytea, text, text, bytea, text)",
        _WITHOUT_TIMEZONE,
        "app.create_workspace(bytea, text, text, bytea)",
    )
    _execute(("ALTER TABLE app.workspaces DROP COLUMN timezone",))
