"""Initial schema: MedArchive/01_common/07-data-model.sql (DB-01, DB-02, DB-03, DB-08).

Revision ID: 0001_init
Revises:

Deviations from the reference DDL, all forced by running as ma_owner instead of a superuser:
- roles are not created here (ma_owner has no CREATEROLE); infra/postgres/init/01-roles.sh
  creates them and this revision only checks that they exist;
- ALTER FUNCTION ... OWNER TO ma_auth needs CREATE on schema app for the new owner, so it is
  granted for the two statements and revoked right after; EXECUTE is granted before the owner
  changes, because a non-owner GRANT only warns and grants nothing.
Fixed defect of the reference DDL: audit_documents() appended field names with `f || 'title'`,
which fails with "malformed array literal" on every UPDATE that changes a field.
"""

from collections.abc import Sequence

from alembic import op

revision = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_EXIST = """DO $$ BEGIN
  IF (SELECT count(*) FROM pg_catalog.pg_roles
      WHERE rolname IN ('ma_app', 'ma_worker', 'ma_auth')) <> 3 THEN
    RAISE EXCEPTION 'roles ma_app, ma_worker, ma_auth are missing: %',
      'run infra/postgres/init/01-roles.sh as superuser';
  END IF;
END $$"""

_EXTENSIONS = (
    "CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public",
    "CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public",
    # uuid in the composite GIN index documents_title_bidx
    "CREATE EXTENSION IF NOT EXISTS btree_gin WITH SCHEMA public",
)

_TABLES = (
    "CREATE SCHEMA app",
    r"""CREATE TABLE app.document_types (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z_]{2,32}$'),
  title_ru    text NOT NULL UNIQUE CHECK (char_length(title_ru) BETWEEN 2 AND 40),
  sort_order  smallint NOT NULL UNIQUE
)""",
    """INSERT INTO app.document_types VALUES
  ('analysis', 'Анализ', 10), ('conclusion', 'Заключение', 20), ('other', 'Другое', 30)""",
    """CREATE TABLE app.workspaces (
  id                  uuid PRIMARY KEY,
  created_at          timestamptz NOT NULL DEFAULT now(),
  dek_ciphertext      bytea NOT NULL CHECK (octet_length(dek_ciphertext) BETWEEN 32 AND 1024),
  bidx_key_ciphertext bytea NOT NULL CHECK (octet_length(bidx_key_ciphertext) BETWEEN 32 AND 1024),
  kek_key_id          text NOT NULL CHECK (char_length(kek_key_id) BETWEEN 1 AND 64),
  deleted_at          timestamptz,
  purge_after         timestamptz,
  CHECK ((deleted_at IS NULL) = (purge_after IS NULL))
)""",
    r"""CREATE TABLE app.consents (
  id              uuid PRIMARY KEY,
  workspace_id    uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  policy_version  text NOT NULL CHECK (policy_version ~ '^\d{4}-\d{2}-\d{2}$'),
  accepted_at     timestamptz NOT NULL DEFAULT now(),
  evidence_sha256 bytea NOT NULL CHECK (octet_length(evidence_sha256) = 32),
  withdrawn_at    timestamptz,
  CHECK (withdrawn_at IS NULL OR withdrawn_at >= accepted_at)
)""",
    """CREATE UNIQUE INDEX consents_one_active ON app.consents (workspace_id)
  WHERE withdrawn_at IS NULL""",
    """CREATE TABLE app.sessions (
  id                  uuid PRIMARY KEY,
  workspace_id        uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  token_sha256        bytea NOT NULL UNIQUE CHECK (octet_length(token_sha256) = 32),
  created_at          timestamptz NOT NULL DEFAULT now(),
  last_seen_at        timestamptz NOT NULL DEFAULT now(),
  idle_expires_at     timestamptz NOT NULL,
  absolute_expires_at timestamptz NOT NULL,
  revoked_at          timestamptz,
  CHECK (idle_expires_at <= absolute_expires_at AND absolute_expires_at > created_at)
)""",
    """CREATE INDEX sessions_workspace_active ON app.sessions (workspace_id)
  WHERE revoked_at IS NULL""",
    """CREATE TABLE app.access_keys (
  id            uuid PRIMARY KEY,
  workspace_id  uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  lookup_id     char(6) NOT NULL UNIQUE CHECK (lookup_id ~ '^[0-9A-HJKMNP-TV-Z]{6}$'),
  secret_hash   text NOT NULL CHECK (secret_hash LIKE '$argon2id$%'),
  created_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz
)""",
    """CREATE UNIQUE INDEX access_keys_one_active ON app.access_keys (workspace_id)
  WHERE revoked_at IS NULL""",
    """CREATE TABLE app.uploads (
  id             uuid PRIMARY KEY,
  workspace_id   uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  quarantine_key text NOT NULL UNIQUE,
  max_bytes      integer NOT NULL CHECK (max_bytes BETWEEN 1 AND 20971520),
  status         text NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'verified', 'consumed', 'rejected', 'expired')),
  reject_code    text CHECK (reject_code IN ('not_pdf', 'file_too_large', 'pdf_unreadable',
                                             'pdf_encrypted')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz NOT NULL,
  CHECK ((status = 'rejected') = (reject_code IS NOT NULL)),
  CHECK (expires_at > created_at)
)""",
    """CREATE INDEX uploads_expiring ON app.uploads (expires_at)
  WHERE status IN ('pending', 'verified')""",
    """CREATE TABLE app.documents (
  id             uuid PRIMARY KEY,
  workspace_id   uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  type_code      text NOT NULL REFERENCES app.document_types(code),
  title_ct       bytea NOT NULL CHECK (octet_length(title_ct) BETWEEN 29 AND 1024),
  title_bidx     bigint[] NOT NULL CHECK (cardinality(title_bidx) BETWEEN 1 AND 256),
  note_ct        bytea CHECK (note_ct IS NULL OR octet_length(note_ct) BETWEEN 29 AND 9000),
  document_date  date CHECK (document_date IS NULL OR document_date >= DATE '1900-01-01'),
  uploaded_at    timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  version        integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  deleted_at     timestamptz,
  list_key       integer GENERATED ALWAYS AS (
                   CASE WHEN document_date IS NULL THEN 2147483647
                        ELSE (DATE '1900-01-01' - document_date) END) STORED,
  CONSTRAINT documents_date_not_future
    CHECK (document_date IS NULL OR document_date <= (uploaded_at AT TIME ZONE 'UTC')::date + 1),
  CONSTRAINT documents_ws_id_uniq UNIQUE (workspace_id, id)
)""",
    """CREATE INDEX documents_list ON app.documents (workspace_id, list_key, uploaded_at, id)
  INCLUDE (type_code, document_date) WHERE deleted_at IS NULL""",
    """CREATE INDEX documents_by_upload ON app.documents (workspace_id, uploaded_at, id)
  WHERE deleted_at IS NULL""",
    """CREATE INDEX documents_title_bidx ON app.documents USING gin (workspace_id, title_bidx)
  WHERE deleted_at IS NULL""",
    """CREATE INDEX documents_to_purge ON app.documents (deleted_at)
  WHERE deleted_at IS NOT NULL""",
    r"""CREATE TABLE app.document_files (
  document_id      uuid PRIMARY KEY,
  workspace_id     uuid NOT NULL,
  object_key       text NOT NULL UNIQUE
                   CHECK (object_key ~ '^ws/[0-9a-f-]{36}/[0-9a-f-]{36}\.bin$'),
  size_bytes       integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 20971520),
  sha256           bytea NOT NULL CHECK (octet_length(sha256) = 32),
  page_count       smallint CHECK (page_count BETWEEN 1 AND 2000),
  original_name_ct bytea NOT NULL,
  content_type     text NOT NULL DEFAULT 'application/pdf' CHECK (content_type = 'application/pdf'),
  FOREIGN KEY (workspace_id, document_id)
    REFERENCES app.documents (workspace_id, id) ON DELETE CASCADE
)""",
    "CREATE INDEX document_files_dupe ON app.document_files (workspace_id, sha256)",
    """CREATE TABLE app.idempotency_keys (
  workspace_id    uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  key             text NOT NULL CHECK (char_length(key) BETWEEN 16 AND 64),
  operation       text NOT NULL
                  CHECK (operation IN ('documents.create', 'exports.create', 'suggestions.create')),
  fingerprint     bytea NOT NULL CHECK (octet_length(fingerprint) = 32),
  state           text NOT NULL DEFAULT 'in_progress' CHECK (state IN ('in_progress', 'completed')),
  response_status smallint,
  resource_id     uuid,
  created_at      timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz NOT NULL DEFAULT now() + interval '24 hours',
  PRIMARY KEY (workspace_id, key),
  CHECK ((state = 'completed') = (response_status IS NOT NULL))
)""",
    "CREATE INDEX idempotency_expiring ON app.idempotency_keys (expires_at)",
    """CREATE TABLE app.exports (
  id            uuid PRIMARY KEY,
  workspace_id  uuid NOT NULL REFERENCES app.workspaces(id) ON DELETE CASCADE,
  scope         text NOT NULL CHECK (scope IN ('all', 'filtered', 'selected')),
  filter        jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(filter) = 'object'),
  document_ids  uuid[] NOT NULL CHECK (cardinality(document_ids) BETWEEN 1 AND 5000),
  total_bytes   bigint NOT NULL CHECK (total_bytes >= 0),
  created_at    timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL DEFAULT now() + interval '1 hour'
)""",
    "CREATE INDEX exports_expiring ON app.exports (expires_at)",
    """CREATE TABLE app.audit_log (
  id             bigint GENERATED ALWAYS AS IDENTITY,
  occurred_at    timestamptz NOT NULL DEFAULT now(),
  workspace_id   uuid NOT NULL,
  session_id     uuid,
  action         text NOT NULL CHECK (action IN (
                   'workspace.create', 'workspace.delete', 'consent.accept', 'consent.withdraw',
                   'session.create', 'session.restore', 'session.restore_failed', 'session.revoke',
                   'access_key.issue', 'document.create', 'document.update', 'document.delete',
                   'document.purge', 'document.view', 'document.download', 'export.create',
                   'export.download')),
  entity_id      uuid,
  changed_fields text[],
  request_id     text CHECK (char_length(request_id) <= 64),
  ip_prefix      cidr,
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at)""",
    """CREATE TABLE app.audit_log_2026_11 PARTITION OF app.audit_log
  FOR VALUES FROM ('2026-11-01 00:00+00') TO ('2026-12-01 00:00+00')""",
    """CREATE TABLE app.audit_log_2026_12 PARTITION OF app.audit_log
  FOR VALUES FROM ('2026-12-01 00:00+00') TO ('2027-01-01 00:00+00')""",
    "CREATE TABLE app.audit_log_default PARTITION OF app.audit_log DEFAULT",
    "CREATE INDEX audit_log_ws_time ON app.audit_log (workspace_id, occurred_at DESC)",
    """CREATE TABLE app.purge_queue (
  object_key      text PRIMARY KEY,
  reason          text NOT NULL CHECK (reason IN (
                    'document_deleted', 'workspace_deleted', 'upload_rejected', 'upload_expired',
                    'orphan')),
  enqueued_at     timestamptz NOT NULL DEFAULT now(),
  attempts        smallint NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at timestamptz NOT NULL DEFAULT now()
)""",
    "CREATE INDEX purge_queue_due ON app.purge_queue (next_attempt_at)",
)

_TRIGGERS = (
    """CREATE FUNCTION app.bump_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.uploaded_at IS DISTINCT FROM OLD.uploaded_at THEN
    RAISE EXCEPTION 'uploaded_at is immutable' USING ERRCODE = 'check_violation';
  END IF;
  NEW.version := OLD.version + 1;
  NEW.updated_at := now();
  RETURN NEW;
END $$""",
    """CREATE TRIGGER documents_bump BEFORE UPDATE ON app.documents
  FOR EACH ROW EXECUTE FUNCTION app.bump_version()""",
    """CREATE FUNCTION app.audit_documents() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
DECLARE f text[] := '{}';
BEGIN
  IF TG_OP = 'UPDATE' THEN
    -- array_append, not f || 'title': the untyped literal would be parsed as a text[] literal.
    IF NEW.title_ct IS DISTINCT FROM OLD.title_ct THEN f := array_append(f, 'title'); END IF;
    IF NEW.type_code IS DISTINCT FROM OLD.type_code THEN f := array_append(f, 'type'); END IF;
    IF NEW.document_date IS DISTINCT FROM OLD.document_date THEN
      f := array_append(f, 'document_date');
    END IF;
    IF NEW.note_ct IS DISTINCT FROM OLD.note_ct THEN f := array_append(f, 'note'); END IF;
    INSERT INTO app.audit_log (workspace_id, session_id, action, entity_id, changed_fields,
                               request_id)
    VALUES (NEW.workspace_id, nullif(current_setting('app.session_id', true), '')::uuid,
            CASE WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                 THEN 'document.delete' ELSE 'document.update' END,
            NEW.id, f, current_setting('app.request_id', true));
  ELSIF TG_OP = 'INSERT' THEN
    INSERT INTO app.audit_log (workspace_id, session_id, action, entity_id, request_id)
    VALUES (NEW.workspace_id, nullif(current_setting('app.session_id', true), '')::uuid,
            'document.create', NEW.id, current_setting('app.request_id', true));
  END IF;
  RETURN NULL;
END $$""",
    """CREATE TRIGGER documents_audit AFTER INSERT OR UPDATE ON app.documents
  FOR EACH ROW EXECUTE FUNCTION app.audit_documents()""",
)

_ROW_LEVEL_SECURITY = (
    "GRANT USAGE ON SCHEMA app TO ma_app, ma_worker",
    "GRANT SELECT ON app.document_types TO ma_app, ma_worker",
    """GRANT SELECT, INSERT, UPDATE ON app.documents, app.document_files, app.uploads, app.exports,
  app.idempotency_keys, app.consents TO ma_app""",
    "GRANT SELECT ON app.workspaces TO ma_app",
    "GRANT INSERT ON app.audit_log TO ma_app, ma_worker",
    "GRANT SELECT, INSERT, DELETE ON app.purge_queue TO ma_worker",
    """GRANT SELECT, UPDATE, DELETE ON app.documents, app.document_files, app.uploads, app.exports,
  app.idempotency_keys, app.workspaces TO ma_worker""",
    """CREATE FUNCTION app.current_workspace() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.workspace_id', true), '')::uuid $$""",
    """DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['workspaces', 'consents', 'sessions', 'access_keys', 'uploads',
                           'documents', 'document_files', 'idempotency_keys', 'exports',
                           'audit_log'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', t);
  END LOOP;
END $$""",
    """CREATE POLICY ws_isolation ON app.workspaces FOR ALL TO ma_app, ma_worker
  USING (id = app.current_workspace())""",
    """DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['consents', 'uploads', 'documents', 'document_files',
                           'idempotency_keys', 'exports'] LOOP
    EXECUTE format('CREATE POLICY ws_isolation ON app.%I FOR ALL TO ma_app, ma_worker '
                   'USING (workspace_id = app.current_workspace()) '
                   'WITH CHECK (workspace_id = app.current_workspace())', t);
  END LOOP;
END $$""",
    """CREATE POLICY audit_insert ON app.audit_log FOR INSERT TO ma_app, ma_worker
  WITH CHECK (workspace_id = app.current_workspace())""",
    """CREATE POLICY hide_deleted ON app.documents AS RESTRICTIVE FOR SELECT TO ma_app
  USING (deleted_at IS NULL)""",
)

_LOGIN_FUNCTIONS = (
    """CREATE FUNCTION app.resolve_session(p_token_sha256 bytea)
RETURNS TABLE(session_id uuid, workspace_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp AS $$
  SELECT s.id, s.workspace_id FROM app.sessions s JOIN app.workspaces w ON w.id = s.workspace_id
  WHERE s.token_sha256 = p_token_sha256 AND s.revoked_at IS NULL AND w.deleted_at IS NULL
    AND now() < s.idle_expires_at AND now() < s.absolute_expires_at
$$""",
    """CREATE FUNCTION app.find_access_key(p_lookup_id text)
RETURNS TABLE(access_key_id uuid, workspace_id uuid, secret_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp AS $$
  SELECT k.id, k.workspace_id, k.secret_hash
  FROM app.access_keys k JOIN app.workspaces w ON w.id = k.workspace_id
  WHERE k.lookup_id = p_lookup_id AND k.revoked_at IS NULL AND w.deleted_at IS NULL
$$""",
    "GRANT USAGE ON SCHEMA app TO ma_auth",
    "GRANT SELECT ON app.sessions, app.access_keys, app.workspaces TO ma_auth",
    """REVOKE ALL ON FUNCTION app.resolve_session(bytea), app.find_access_key(text)
  FROM PUBLIC""",
    """GRANT EXECUTE ON FUNCTION app.resolve_session(bytea), app.find_access_key(text)
  TO ma_app""",
    "GRANT EXECUTE ON FUNCTION app.current_workspace() TO ma_app, ma_worker",
    "GRANT CREATE ON SCHEMA app TO ma_auth",
    "ALTER FUNCTION app.resolve_session(bytea) OWNER TO ma_auth",
    "ALTER FUNCTION app.find_access_key(text) OWNER TO ma_auth",
    "REVOKE CREATE ON SCHEMA app FROM ma_auth",
)


def _execute(statements: Sequence[str]) -> None:
    # One statement per call: asyncpg prepares every statement and rejects multi-command strings.
    bind = op.get_bind()
    for statement in statements:
        bind.exec_driver_sql(statement)


def upgrade() -> None:
    _execute(
        (
            _ROLES_EXIST,
            *_EXTENSIONS,
            *_TABLES,
            *_TRIGGERS,
            *_ROW_LEVEL_SECURITY,
            *_LOGIN_FUNCTIONS,
        )
    )


def downgrade() -> None:
    # The schema owner drops objects of other owners (ma_auth functions) together with the schema.
    _execute(
        (
            "DROP SCHEMA app CASCADE",
            "DROP EXTENSION btree_gin",
            "DROP EXTENSION pgcrypto",
            "DROP EXTENSION pg_trgm",
        )
    )
