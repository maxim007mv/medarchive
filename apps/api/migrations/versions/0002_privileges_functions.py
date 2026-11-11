"""Write paths through SECURITY DEFINER functions, idempotency bodies, key bundle (ADR-044/045/047).

Revision ID: 0002_privileges_functions
Revises: 0001_init

Functions owned by ma_auth (NOLOGIN BYPASSRLS) are created under SET ROLE ma_auth with a
temporary CREATE on schema app. Every one of them pins search_path = pg_catalog, pg_temp, names
objects as app.*, takes the workspace from app.current_workspace() (except the worker scans) and
is executable by exactly one role. app.ensure_audit_partitions() is owned by ma_owner, which owns
app.audit_log and has no BYPASSRLS.

Downgrade fails on purpose when data cannot be restored: dropped key columns, erased keys of
deleted workspaces, idempotency rows of the new operations.
"""

from collections.abc import Sequence

from alembic import op

revision = "0002_privileges_functions"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = (
    # ADR-047: the field, file and blind-index keys are one keyset in dek_ciphertext.
    "ALTER TABLE app.workspaces DROP COLUMN bidx_key_ciphertext",
    # ADR-041: crypto-erasure sets dek_ciphertext = NULL, allowed only for a deleted workspace.
    "ALTER TABLE app.workspaces ALTER COLUMN dek_ciphertext DROP NOT NULL",
    """ALTER TABLE app.workspaces ADD CONSTRAINT workspaces_dek_kept_until_deleted
  CHECK (dek_ciphertext IS NOT NULL OR deleted_at IS NOT NULL)""",
    # 06-api-contract: original_name comes with POST /uploads, is stored encrypted and becomes
    # document_files.original_name_ct at POST /documents.
    "ALTER TABLE app.uploads ADD COLUMN original_name_ct bytea",
    # ADR-045
    "ALTER TABLE app.idempotency_keys DROP CONSTRAINT idempotency_keys_operation_check",
    """ALTER TABLE app.idempotency_keys ADD CONSTRAINT idempotency_keys_operation_check
  CHECK (operation IN ('documents.create', 'exports.create', 'suggestions.create',
                       'uploads.create', 'workspace.rotateKey'))""",
    "ALTER TABLE app.idempotency_keys ADD COLUMN response_body_ct bytea",
    """ALTER TABLE app.idempotency_keys ADD CONSTRAINT idempotency_keys_body_when_completed
  CHECK (response_body_ct IS NULL OR state = 'completed')""",
    """CREATE TABLE app.workspace_create_keys (
  key_sha256       bytea PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
  fingerprint      bytea NOT NULL CHECK (octet_length(fingerprint) = 32),
  state            text NOT NULL DEFAULT 'in_progress'
                   CHECK (state IN ('in_progress', 'completed')),
  response_status  smallint,
  workspace_id     uuid REFERENCES app.workspaces(id) ON DELETE CASCADE,
  response_body_ct bytea,
  expires_at       timestamptz NOT NULL DEFAULT now() + interval '24 hours',
  CHECK ((state = 'completed') = (response_status IS NOT NULL)),
  CHECK (state = 'in_progress' OR (workspace_id IS NOT NULL AND response_body_ct IS NOT NULL))
)""",
    "CREATE INDEX workspace_create_keys_expiring ON app.workspace_create_keys (expires_at)",
    # No policies: default deny for everyone except BYPASSRLS ma_auth, on top of no grants.
    "ALTER TABLE app.workspace_create_keys ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE app.workspace_create_keys FORCE ROW LEVEL SECURITY",
)

_GRANTS = (
    # ADR-045: an in_progress row is removed when the response is 4xx/5xx (RLS scopes it).
    "GRANT DELETE ON app.idempotency_keys TO ma_app",
    # Retry bookkeeping of the purge worker (attempts, next_attempt_at).
    "GRANT UPDATE ON app.purge_queue TO ma_worker",
    "GRANT INSERT, UPDATE ON app.workspaces, app.sessions, app.access_keys TO ma_auth",
    "GRANT SELECT, INSERT, UPDATE ON app.consents TO ma_auth",
    "GRANT INSERT ON app.purge_queue TO ma_auth",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON app.workspace_create_keys TO ma_auth",
    "GRANT SELECT ON app.documents, app.uploads, app.exports, app.idempotency_keys TO ma_auth",
    # soft_delete_document; its UPDATE fires the audit trigger as ma_auth.
    "GRANT UPDATE ON app.documents TO ma_auth",
    "GRANT INSERT ON app.audit_log TO ma_auth",
)

_AUDIT_PARTITIONS = (
    """CREATE FUNCTION app.ensure_audit_partitions() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  months_ahead CONSTANT integer := 2;
  -- UTC wall clock: adding a month to timestamptz would follow the session time zone.
  month_start timestamp;
  partition_name text;
  created integer := 0;
BEGIN
  -- Two workers at once would both see the partition missing.
  PERFORM pg_advisory_xact_lock(hashtext('app.ensure_audit_partitions'));
  FOR i IN 0..months_ahead LOOP
    month_start := date_trunc('month', now() AT TIME ZONE 'UTC') + make_interval(months => i);
    partition_name := 'audit_log_' || to_char(month_start, 'YYYY_MM');
    IF to_regclass('app.' || partition_name) IS NULL THEN
      EXECUTE format('CREATE TABLE app.%I PARTITION OF app.audit_log FOR VALUES FROM (%L) TO (%L)',
                     partition_name, month_start AT TIME ZONE 'UTC',
                     (month_start + interval '1 month') AT TIME ZONE 'UTC');
      created := created + 1;
    END IF;
  END LOOP;
  RETURN created;
END $$""",
    "REVOKE ALL ON FUNCTION app.ensure_audit_partitions() FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION app.ensure_audit_partitions() TO ma_worker",
    "SELECT app.ensure_audit_partitions()",
)

_AUTH_FUNCTIONS = (
    "ALTER FUNCTION app.resolve_session(bytea) SET search_path = pg_catalog, pg_temp",
    "ALTER FUNCTION app.find_access_key(text) SET search_path = pg_catalog, pg_temp",
    """CREATE FUNCTION app.require_workspace() RETURNS uuid
LANGUAGE plpgsql STABLE SET search_path = pg_catalog, pg_temp AS $$
DECLARE workspace uuid := app.current_workspace();
BEGIN
  IF workspace IS NULL THEN
    RAISE EXCEPTION 'app.workspace_id is not set in this transaction'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN workspace;
END $$""",
    """CREATE FUNCTION app.create_workspace(
  p_dek_ciphertext bytea, p_kek_key_id text, p_policy_version text, p_evidence_sha256 bytea)
RETURNS timestamptz LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  workspace uuid := app.require_workspace();
  created timestamptz;
BEGIN
  INSERT INTO app.workspaces (id, dek_ciphertext, kek_key_id)
  VALUES (workspace, p_dek_ciphertext, p_kek_key_id)
  RETURNING created_at INTO created;
  INSERT INTO app.consents (id, workspace_id, policy_version, evidence_sha256)
  VALUES (gen_random_uuid(), workspace, p_policy_version, p_evidence_sha256);
  RETURN created;
END $$""",
    """CREATE FUNCTION app.create_session(
  p_token_sha256 bytea, p_idle_ttl interval, p_absolute_ttl interval)
RETURNS TABLE(session_id uuid, idle_expires_at timestamptz, absolute_expires_at timestamptz)
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  INSERT INTO app.sessions (id, workspace_id, token_sha256, idle_expires_at, absolute_expires_at)
  SELECT gen_random_uuid(), w.id, p_token_sha256, now() + p_idle_ttl, now() + p_absolute_ttl
  FROM app.workspaces w
  WHERE w.id = app.require_workspace() AND w.deleted_at IS NULL
  RETURNING id, idle_expires_at, absolute_expires_at
$$""",
    """CREATE FUNCTION app.touch_session(p_session_id uuid, p_idle_ttl interval)
RETURNS timestamptz LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  UPDATE app.sessions s
  SET last_seen_at = now(), idle_expires_at = least(now() + p_idle_ttl, s.absolute_expires_at)
  WHERE s.id = p_session_id AND s.workspace_id = app.require_workspace()
    AND s.revoked_at IS NULL AND now() < s.idle_expires_at AND now() < s.absolute_expires_at
  RETURNING s.idle_expires_at
$$""",
    """CREATE FUNCTION app.revoke_sessions(p_session_id uuid DEFAULT NULL)
RETURNS integer LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  WITH revoked AS (
    UPDATE app.sessions s SET revoked_at = now()
    WHERE s.workspace_id = app.require_workspace() AND s.revoked_at IS NULL
      AND (p_session_id IS NULL OR s.id = p_session_id)
    RETURNING 1)
  SELECT count(*)::integer FROM revoked
$$""",
    """CREATE FUNCTION app.issue_access_key(p_lookup_id text, p_secret_hash text)
RETURNS TABLE(access_key_id uuid, revoked_previous boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  workspace uuid := app.require_workspace();
  revoked integer;
BEGIN
  -- Serialises concurrent rotations: both would otherwise try to insert an active key.
  PERFORM 1 FROM app.workspaces w WHERE w.id = workspace AND w.deleted_at IS NULL FOR UPDATE;
  IF NOT FOUND THEN
    RETURN;
  END IF;
  UPDATE app.access_keys k SET revoked_at = now()
  WHERE k.workspace_id = workspace AND k.revoked_at IS NULL;
  GET DIAGNOSTICS revoked = ROW_COUNT;
  INSERT INTO app.access_keys AS k (id, workspace_id, lookup_id, secret_hash)
  VALUES (gen_random_uuid(), workspace, p_lookup_id, p_secret_hash)
  RETURNING k.id INTO access_key_id;
  revoked_previous := revoked > 0;
  RETURN NEXT;
END $$""",
    """CREATE FUNCTION app.revoke_access_key() RETURNS boolean LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  WITH revoked AS (
    UPDATE app.access_keys k SET revoked_at = now()
    WHERE k.workspace_id = app.require_workspace() AND k.revoked_at IS NULL
    RETURNING 1)
  SELECT count(*) > 0 FROM revoked
$$""",
    """CREATE FUNCTION app.delete_workspace() RETURNS timestamptz
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  workspace uuid := app.require_workspace();
  purge_at timestamptz;
BEGIN
  UPDATE app.workspaces w
  SET deleted_at = now(), purge_after = now() + interval '24 hours', dek_ciphertext = NULL
  WHERE w.id = workspace AND w.deleted_at IS NULL
  RETURNING w.purge_after INTO purge_at;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;
  UPDATE app.sessions s SET revoked_at = now()
  WHERE s.workspace_id = workspace AND s.revoked_at IS NULL;
  UPDATE app.access_keys k SET revoked_at = now()
  WHERE k.workspace_id = workspace AND k.revoked_at IS NULL;
  UPDATE app.consents c SET withdrawn_at = now()
  WHERE c.workspace_id = workspace AND c.withdrawn_at IS NULL;
  RETURN purge_at;
END $$""",
    # ma_app cannot soft-delete itself: with the RESTRICTIVE SELECT policy hide_deleted, the new
    # row of UPDATE ... SET deleted_at = now() WHERE id = ... must stay visible, so it is rejected.
    """CREATE FUNCTION app.soft_delete_document(p_document_id uuid) RETURNS boolean
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  WITH deleted AS (
    UPDATE app.documents d SET deleted_at = now()
    WHERE d.id = p_document_id AND d.workspace_id = app.require_workspace()
      AND d.deleted_at IS NULL
    RETURNING 1)
  SELECT count(*) > 0 FROM deleted
$$""",
    """CREATE FUNCTION app.enqueue_purge(p_object_key text, p_reason text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  object_id CONSTANT text := '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
BEGIN
  -- Only ws/{workspace}/{id}.bin (ma-docs) and q/{workspace}/{id}.bin (ma-quarantine).
  IF p_object_key !~ ('^(ws|q)/' || app.require_workspace()::text || '/' || object_id || '\\.bin$')
  THEN
    RAISE EXCEPTION 'object key is outside the current workspace'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  -- No conflict target: naming one needs SELECT on it, and the primary key is the only one.
  INSERT INTO app.purge_queue (object_key, reason) VALUES (p_object_key, p_reason)
  ON CONFLICT DO NOTHING;
END $$""",
    """CREATE FUNCTION app.claim_workspace_create_key(p_key_sha256 bytea, p_fingerprint bytea)
RETURNS TABLE(is_new boolean, state text, fingerprint bytea, response_status smallint,
              workspace_id uuid, response_body_ct bytea)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  DELETE FROM app.workspace_create_keys k
  WHERE k.key_sha256 = p_key_sha256 AND k.expires_at <= now();
  -- A concurrent claim of the same key waits here until the other transaction ends.
  INSERT INTO app.workspace_create_keys AS k (key_sha256, fingerprint)
  VALUES (p_key_sha256, p_fingerprint)
  ON CONFLICT (key_sha256) DO NOTHING;
  is_new := FOUND;
  SELECT k.state, k.fingerprint, k.response_status, k.workspace_id, k.response_body_ct
  INTO state, fingerprint, response_status, workspace_id, response_body_ct
  FROM app.workspace_create_keys k WHERE k.key_sha256 = p_key_sha256;
  RETURN NEXT;
END $$""",
    """CREATE FUNCTION app.complete_workspace_create_key(
  p_key_sha256 bytea, p_response_status integer, p_response_body_ct bytea)
RETURNS boolean LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  WITH completed AS (
    UPDATE app.workspace_create_keys k
    SET state = 'completed', response_status = p_response_status,
        response_body_ct = p_response_body_ct, workspace_id = app.require_workspace()
    WHERE k.key_sha256 = p_key_sha256 AND k.state = 'in_progress'
    RETURNING 1)
  SELECT count(*) > 0 FROM completed
$$""",
    """CREATE FUNCTION app.release_workspace_create_key(p_key_sha256 bytea)
RETURNS boolean LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  WITH released AS (
    DELETE FROM app.workspace_create_keys k
    WHERE k.key_sha256 = p_key_sha256 AND k.state = 'in_progress'
    RETURNING 1)
  SELECT count(*) > 0 FROM released
$$""",
    """CREATE FUNCTION app.workspaces_due_for_purge(p_limit integer)
RETURNS TABLE(workspace_id uuid) LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  SELECT due.id FROM (
    SELECT w.id FROM app.workspaces w WHERE w.purge_after <= now()
    UNION SELECT d.workspace_id FROM app.documents d
          WHERE d.deleted_at <= now() - interval '24 hours'
    UNION SELECT u.workspace_id FROM app.uploads u WHERE u.expires_at <= now()
    UNION SELECT e.workspace_id FROM app.exports e WHERE e.expires_at <= now()
    UNION SELECT i.workspace_id FROM app.idempotency_keys i WHERE i.expires_at <= now()
  ) due
  LIMIT least(greatest(p_limit, 0), 500)
$$""",
    """CREATE FUNCTION app.purge_expired_workspace_create_keys(p_limit integer)
RETURNS integer LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
  WITH purged AS (
    DELETE FROM app.workspace_create_keys k
    WHERE k.key_sha256 IN (
      SELECT e.key_sha256 FROM app.workspace_create_keys e WHERE e.expires_at <= now()
      LIMIT least(greatest(p_limit, 0), 500))
    RETURNING 1)
  SELECT count(*)::integer FROM purged
$$""",
)

# Signature -> the only role allowed to call it.
_EXECUTE_GRANTS = {
    "app.require_workspace()": None,
    "app.create_workspace(bytea, text, text, bytea)": "ma_app",
    "app.create_session(bytea, interval, interval)": "ma_app",
    "app.touch_session(uuid, interval)": "ma_app",
    "app.revoke_sessions(uuid)": "ma_app",
    "app.issue_access_key(text, text)": "ma_app",
    "app.revoke_access_key()": "ma_app",
    "app.delete_workspace()": "ma_app",
    "app.soft_delete_document(uuid)": "ma_app",
    "app.enqueue_purge(text, text)": "ma_app",
    "app.claim_workspace_create_key(bytea, bytea)": "ma_app",
    "app.complete_workspace_create_key(bytea, integer, bytea)": "ma_app",
    "app.release_workspace_create_key(bytea)": "ma_app",
    "app.workspaces_due_for_purge(integer)": "ma_worker",
    "app.purge_expired_workspace_create_keys(integer)": "ma_worker",
}


def _execute_grants() -> list[str]:
    statements = []
    for signature, role in _EXECUTE_GRANTS.items():
        statements.append(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        if role is not None:
            statements.append(f"GRANT EXECUTE ON FUNCTION {signature} TO {role}")
    return statements


def _execute(statements: Sequence[str]) -> None:
    # One statement per call: asyncpg prepares every statement and rejects multi-command strings.
    bind = op.get_bind()
    for statement in statements:
        bind.exec_driver_sql(statement)


def upgrade() -> None:
    _execute((*_SCHEMA, *_GRANTS, *_AUDIT_PARTITIONS))
    _execute(
        (
            "GRANT CREATE ON SCHEMA app TO ma_auth",
            "SET LOCAL ROLE ma_auth",
            *_AUTH_FUNCTIONS,
            *_execute_grants(),
            "RESET ROLE",
            "REVOKE CREATE ON SCHEMA app FROM ma_auth",
        )
    )


def downgrade() -> None:
    _execute(
        (
            "SET LOCAL ROLE ma_auth",
            *(f"DROP FUNCTION {signature}" for signature in reversed(_EXECUTE_GRANTS)),
            "ALTER FUNCTION app.resolve_session(bytea) SET search_path = app, pg_temp",
            "ALTER FUNCTION app.find_access_key(text) SET search_path = app, pg_temp",
            "RESET ROLE",
            "DROP FUNCTION app.ensure_audit_partitions()",
            "REVOKE INSERT ON app.audit_log FROM ma_auth",
            "REVOKE UPDATE ON app.documents FROM ma_auth",
            "REVOKE SELECT ON app.documents, app.uploads, app.exports, app.idempotency_keys "
            "FROM ma_auth",
            "REVOKE INSERT ON app.purge_queue FROM ma_auth",
            "REVOKE INSERT, UPDATE ON app.workspaces, app.sessions, app.access_keys FROM ma_auth",
            "REVOKE SELECT, INSERT, UPDATE ON app.consents FROM ma_auth",
            "REVOKE UPDATE ON app.purge_queue FROM ma_worker",
            "REVOKE DELETE ON app.idempotency_keys FROM ma_app",
            "DROP TABLE app.workspace_create_keys",
            "ALTER TABLE app.idempotency_keys DROP CONSTRAINT idempotency_keys_body_when_completed",
            "ALTER TABLE app.idempotency_keys DROP COLUMN response_body_ct",
            "ALTER TABLE app.idempotency_keys DROP CONSTRAINT idempotency_keys_operation_check",
            """ALTER TABLE app.idempotency_keys ADD CONSTRAINT idempotency_keys_operation_check
  CHECK (operation IN ('documents.create', 'exports.create', 'suggestions.create'))""",
            "ALTER TABLE app.uploads DROP COLUMN original_name_ct",
            "ALTER TABLE app.workspaces DROP CONSTRAINT workspaces_dek_kept_until_deleted",
            "ALTER TABLE app.workspaces ALTER COLUMN dek_ciphertext SET NOT NULL",
            """ALTER TABLE app.workspaces ADD COLUMN bidx_key_ciphertext bytea NOT NULL
  CHECK (octet_length(bidx_key_ciphertext) BETWEEN 32 AND 1024)""",
        )
    )
