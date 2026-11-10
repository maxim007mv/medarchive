-- Медархив: схема БД v1 (PostgreSQL 17+, проверено на 17 и 18)
-- Эталон миграций apps/api/migrations: часть 1 = ревизия 0001_init, часть 2 = схема и права ревизии
-- 0002_privileges_functions (ADR-044, ADR-045, ADR-047). Исполняемая истина: миграции; этот файл
-- держится в соответствии с ними. В репозитории роли создаёт infra/postgres/init/01-roles.sh,
-- миграции идут от ma_owner. Приложение работает ролью ma_app (без BYPASSRLS).
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gin;   -- uuid в составном GIN-индексе
CREATE SCHEMA IF NOT EXISTS app;
SET search_path = app, public;

-- 1. Справочник типов (lookup-таблица вместо ENUM: новый тип = INSERT, без ALTER TYPE)
CREATE TABLE document_types (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z_]{2,32}$'),
  title_ru    text NOT NULL UNIQUE CHECK (char_length(title_ru) BETWEEN 2 AND 40),
  sort_order  smallint NOT NULL UNIQUE
);
INSERT INTO document_types VALUES ('analysis','Анализ',10),('conclusion','Заключение',20),('other','Другое',30);

-- 2. Пространство (архив одного человека). Ключи шифрования хранятся только в зашифрованном KMS виде.
CREATE TABLE workspaces (
  id                 uuid PRIMARY KEY,
  created_at         timestamptz NOT NULL DEFAULT now(),
  dek_ciphertext     bytea NOT NULL CHECK (octet_length(dek_ciphertext) BETWEEN 32 AND 1024),  -- Tink keyset, зашифрован KEK в KMS
  bidx_key_ciphertext bytea NOT NULL CHECK (octet_length(bidx_key_ciphertext) BETWEEN 32 AND 1024), -- ключ слепого индекса
  kek_key_id         text NOT NULL CHECK (char_length(kek_key_id) BETWEEN 1 AND 64),
  deleted_at         timestamptz,
  purge_after        timestamptz,
  CHECK ((deleted_at IS NULL) = (purge_after IS NULL))
);

-- 3. Согласие на обработку данных о здоровье (152-ФЗ, ст. 9 и ст. 10 ч. 2 п. 1)
CREATE TABLE consents (
  id              uuid PRIMARY KEY,
  workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  policy_version  text NOT NULL CHECK (policy_version ~ '^\d{4}-\d{2}-\d{2}$'),
  accepted_at     timestamptz NOT NULL DEFAULT now(),
  evidence_sha256 bytea NOT NULL CHECK (octet_length(evidence_sha256) = 32), -- хэш показанного текста + метаданных
  withdrawn_at    timestamptz,
  CHECK (withdrawn_at IS NULL OR withdrawn_at >= accepted_at)
);
CREATE UNIQUE INDEX consents_one_active ON consents (workspace_id) WHERE withdrawn_at IS NULL;

-- 4. Сессии: в БД только SHA-256 токена
CREATE TABLE sessions (
  id            uuid PRIMARY KEY,
  workspace_id  uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  token_sha256  bytea NOT NULL UNIQUE CHECK (octet_length(token_sha256) = 32),
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  idle_expires_at     timestamptz NOT NULL,
  absolute_expires_at timestamptz NOT NULL,
  revoked_at    timestamptz,
  CHECK (idle_expires_at <= absolute_expires_at AND absolute_expires_at > created_at)
);
CREATE INDEX sessions_workspace_active ON sessions (workspace_id) WHERE revoked_at IS NULL;

-- 5. Ключ доступа: публичный префикс для поиска + Argon2id секрета
CREATE TABLE access_keys (
  id            uuid PRIMARY KEY,
  workspace_id  uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  lookup_id     char(6) NOT NULL UNIQUE CHECK (lookup_id ~ '^[0-9A-HJKMNP-TV-Z]{6}$'),  -- Crockford Base32
  secret_hash   text NOT NULL CHECK (secret_hash LIKE '$argon2id$%'),
  created_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz
);
CREATE UNIQUE INDEX access_keys_one_active ON access_keys (workspace_id) WHERE revoked_at IS NULL;

-- 6. Загрузки (presigned POST в карантинный бакет)
CREATE TABLE uploads (
  id             uuid PRIMARY KEY,
  workspace_id   uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  quarantine_key text NOT NULL UNIQUE,
  max_bytes      integer NOT NULL CHECK (max_bytes BETWEEN 1 AND 20971520),
  status         text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','verified','consumed','rejected','expired')),
  reject_code    text CHECK (reject_code IN ('not_pdf','file_too_large','pdf_unreadable','pdf_encrypted')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz NOT NULL,
  CHECK ((status = 'rejected') = (reject_code IS NOT NULL)),
  CHECK (expires_at > created_at)
);
CREATE INDEX uploads_expiring ON uploads (expires_at) WHERE status IN ('pending','verified');

-- 7. Документы. Название, заметка и имя файла зашифрованы (AES-256-GCM, AAD = id документа).
CREATE TABLE documents (
  id             uuid PRIMARY KEY,                        -- UUIDv7 из приложения (на PG 18 можно uuidv7())
  workspace_id   uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  type_code      text NOT NULL REFERENCES document_types(code),
  title_ct       bytea NOT NULL CHECK (octet_length(title_ct) BETWEEN 29 AND 1024),
  title_bidx     bigint[] NOT NULL CHECK (cardinality(title_bidx) BETWEEN 1 AND 256), -- слепой индекс триграмм
  note_ct        bytea CHECK (note_ct IS NULL OR octet_length(note_ct) BETWEEN 29 AND 9000),
  document_date  date CHECK (document_date IS NULL OR document_date >= DATE '1900-01-01'),
  uploaded_at    timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  version        integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  deleted_at     timestamptz,
  -- Ключ сортировки «дата документа по убыванию, без даты в конце» в одном направлении ASC:
  -- позволяет keyset-пагинацию сравнением кортежей (list_key, uploaded_at, id) > (...) прямо в Index Cond
  list_key       integer GENERATED ALWAYS AS (CASE WHEN document_date IS NULL THEN 2147483647 ELSE (DATE '1900-01-01' - document_date) END) STORED,
  CONSTRAINT documents_date_not_future CHECK (document_date IS NULL OR document_date <= (uploaded_at AT TIME ZONE 'UTC')::date + 1),
  CONSTRAINT documents_ws_id_uniq UNIQUE (workspace_id, id)   -- цель составных FK
);
-- Основной список: дата документа по убыванию, без даты в конце, при равенстве в порядке добавления
CREATE INDEX documents_list ON documents (workspace_id, list_key, uploaded_at, id)
  INCLUDE (type_code, document_date) WHERE deleted_at IS NULL;
-- Фильтр и сортировка по дате загрузки
CREATE INDEX documents_by_upload ON documents (workspace_id, uploaded_at, id) WHERE deleted_at IS NULL;
-- «Только без даты» и undated_excluded обслуживает documents_list (list_key = 2147483647), отдельный индекс не нужен
-- Поиск по подстроке через слепой индекс триграмм
CREATE INDEX documents_title_bidx ON documents USING gin (workspace_id, title_bidx) WHERE deleted_at IS NULL;
-- Очистка удалённых
CREATE INDEX documents_to_purge ON documents (deleted_at) WHERE deleted_at IS NOT NULL;

CREATE TABLE document_files (
  document_id      uuid PRIMARY KEY,
  workspace_id     uuid NOT NULL,
  object_key       text NOT NULL UNIQUE CHECK (object_key ~ '^ws/[0-9a-f-]{36}/[0-9a-f-]{36}\.bin$'),
  size_bytes       integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 20971520),
  sha256           bytea NOT NULL CHECK (octet_length(sha256) = 32),
  page_count       smallint CHECK (page_count BETWEEN 1 AND 2000),
  original_name_ct bytea NOT NULL,
  content_type     text NOT NULL DEFAULT 'application/pdf' CHECK (content_type = 'application/pdf'),
  FOREIGN KEY (workspace_id, document_id) REFERENCES documents (workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX document_files_dupe ON document_files (workspace_id, sha256);

-- 8. Идемпотентность (draft-ietf-httpapi-idempotency-key-header: ключ + отпечаток запроса)
CREATE TABLE idempotency_keys (
  workspace_id   uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  key            text NOT NULL CHECK (char_length(key) BETWEEN 16 AND 64),
  operation      text NOT NULL CHECK (operation IN ('documents.create','exports.create','suggestions.create')),
  fingerprint    bytea NOT NULL CHECK (octet_length(fingerprint) = 32),
  state          text NOT NULL DEFAULT 'in_progress' CHECK (state IN ('in_progress','completed')),
  response_status smallint,
  resource_id    uuid,
  created_at     timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz NOT NULL DEFAULT now() + interval '24 hours',
  PRIMARY KEY (workspace_id, key),
  CHECK ((state = 'completed') = (response_status IS NOT NULL))
);
CREATE INDEX idempotency_expiring ON idempotency_keys (expires_at);

-- 9. Экспорты: снимок набора документов, ссылка живёт 1 час
CREATE TABLE exports (
  id            uuid PRIMARY KEY,
  workspace_id  uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  scope         text NOT NULL CHECK (scope IN ('all','filtered','selected')),
  filter        jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(filter) = 'object'),
  document_ids  uuid[] NOT NULL CHECK (cardinality(document_ids) BETWEEN 1 AND 5000),
  total_bytes   bigint NOT NULL CHECK (total_bytes >= 0),
  created_at    timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL DEFAULT now() + interval '1 hour'
);
CREATE INDEX exports_expiring ON exports (expires_at);

-- 10. Журнал аудита: append-only, без содержимого документов, секционирован по месяцам
CREATE TABLE audit_log (
  id            bigint GENERATED ALWAYS AS IDENTITY,
  occurred_at   timestamptz NOT NULL DEFAULT now(),
  workspace_id  uuid NOT NULL,
  session_id    uuid,
  action        text NOT NULL CHECK (action IN ('workspace.create','workspace.delete','consent.accept','consent.withdraw',
                  'session.create','session.restore','session.restore_failed','session.revoke','access_key.issue',
                  'document.create','document.update','document.delete','document.purge','document.view','document.download',
                  'export.create','export.download')),
  entity_id     uuid,
  changed_fields text[],                 -- только имена полей, не значения
  request_id    text CHECK (char_length(request_id) <= 64),
  ip_prefix     cidr,                    -- IPv4 /24, IPv6 /48
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);
-- Границы в UTC: без +00 они зависят от часового пояса сервера. Следующие секции: app.ensure_audit_partitions() (0002)
CREATE TABLE audit_log_2026_11 PARTITION OF audit_log FOR VALUES FROM ('2026-11-01 00:00+00') TO ('2026-12-01 00:00+00');
CREATE TABLE audit_log_2026_12 PARTITION OF audit_log FOR VALUES FROM ('2026-12-01 00:00+00') TO ('2027-01-01 00:00+00');
CREATE TABLE audit_log_default PARTITION OF audit_log DEFAULT;
CREATE INDEX audit_log_ws_time ON audit_log (workspace_id, occurred_at DESC);

-- 11. Очередь физического удаления объектов
CREATE TABLE purge_queue (
  object_key      text PRIMARY KEY,
  reason          text NOT NULL CHECK (reason IN ('document_deleted','workspace_deleted','upload_rejected','upload_expired','orphan')),
  enqueued_at     timestamptz NOT NULL DEFAULT now(),
  attempts        smallint NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX purge_queue_due ON purge_queue (next_attempt_at);

-- 12. Триггеры: версия + updated_at, аудит изменений без значений
CREATE FUNCTION app.bump_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.uploaded_at IS DISTINCT FROM OLD.uploaded_at THEN
    RAISE EXCEPTION 'uploaded_at is immutable' USING ERRCODE = 'check_violation';
  END IF;
  NEW.version := OLD.version + 1;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER documents_bump BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION app.bump_version();

CREATE FUNCTION app.audit_documents() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE f text[] := '{}';
BEGIN
  IF TG_OP = 'UPDATE' THEN
    -- array_append, а не f || 'title': нетипизированный литерал разбирается как text[] и падает
    IF NEW.title_ct IS DISTINCT FROM OLD.title_ct THEN f := array_append(f, 'title'); END IF;
    IF NEW.type_code IS DISTINCT FROM OLD.type_code THEN f := array_append(f, 'type'); END IF;
    IF NEW.document_date IS DISTINCT FROM OLD.document_date THEN f := array_append(f, 'document_date'); END IF;
    IF NEW.note_ct IS DISTINCT FROM OLD.note_ct THEN f := array_append(f, 'note'); END IF;
    INSERT INTO app.audit_log (workspace_id, session_id, action, entity_id, changed_fields, request_id)
    VALUES (NEW.workspace_id, nullif(current_setting('app.session_id', true),'')::uuid,
            CASE WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN 'document.delete' ELSE 'document.update' END,
            NEW.id, f, current_setting('app.request_id', true));
  ELSIF TG_OP = 'INSERT' THEN
    INSERT INTO app.audit_log (workspace_id, session_id, action, entity_id, request_id)
    VALUES (NEW.workspace_id, nullif(current_setting('app.session_id', true),'')::uuid, 'document.create', NEW.id, current_setting('app.request_id', true));
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER documents_audit AFTER INSERT OR UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION app.audit_documents();

-- 13. Роли и Row-Level Security
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ma_app') THEN CREATE ROLE ma_app NOLOGIN NOBYPASSRLS; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ma_worker') THEN CREATE ROLE ma_worker NOLOGIN NOBYPASSRLS; END IF;
  -- ma_auth владеет только двумя функциями входа; логина нет
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ma_auth') THEN CREATE ROLE ma_auth NOLOGIN BYPASSRLS; END IF;
END $$;
GRANT USAGE ON SCHEMA app TO ma_app, ma_worker;
GRANT SELECT ON document_types TO ma_app, ma_worker;
GRANT SELECT, INSERT, UPDATE ON documents, document_files, uploads, exports, idempotency_keys, consents TO ma_app;
GRANT SELECT ON workspaces TO ma_app;
GRANT INSERT ON audit_log TO ma_app, ma_worker;
GRANT SELECT, INSERT, DELETE ON purge_queue TO ma_worker;
GRANT SELECT, UPDATE, DELETE ON documents, document_files, uploads, exports, idempotency_keys, workspaces TO ma_worker;
-- UPDATE/DELETE журнала аудита не выдаются никому, кроме владельца: журнал только дописывается.

CREATE FUNCTION app.current_workspace() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.workspace_id', true), '')::uuid $$;

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['workspaces','consents','sessions','access_keys','uploads','documents','document_files','idempotency_keys','exports','audit_log'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE app.%I FORCE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
CREATE POLICY ws_isolation ON workspaces FOR ALL TO ma_app, ma_worker USING (id = app.current_workspace());
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['consents','uploads','documents','document_files','idempotency_keys','exports'] LOOP
    EXECUTE format('CREATE POLICY ws_isolation ON app.%I FOR ALL TO ma_app, ma_worker USING (workspace_id = app.current_workspace()) WITH CHECK (workspace_id = app.current_workspace())', t);
  END LOOP;
END $$;
CREATE POLICY audit_insert ON audit_log FOR INSERT TO ma_app, ma_worker WITH CHECK (workspace_id = app.current_workspace());
-- Удалённые документы невидимы приложению даже при ошибке в запросе
CREATE POLICY hide_deleted ON documents AS RESTRICTIVE FOR SELECT TO ma_app USING (deleted_at IS NULL);

-- 14. Вход: единственный путь к sessions/access_keys без workspace_id в контексте
CREATE FUNCTION app.resolve_session(p_token_sha256 bytea) RETURNS TABLE(session_id uuid, workspace_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp AS $$
  SELECT s.id, s.workspace_id FROM app.sessions s JOIN app.workspaces w ON w.id = s.workspace_id
  WHERE s.token_sha256 = p_token_sha256 AND s.revoked_at IS NULL AND w.deleted_at IS NULL
    AND now() < s.idle_expires_at AND now() < s.absolute_expires_at
$$;
CREATE FUNCTION app.find_access_key(p_lookup_id text) RETURNS TABLE(access_key_id uuid, workspace_id uuid, secret_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = app, pg_temp AS $$
  SELECT k.id, k.workspace_id, k.secret_hash FROM app.access_keys k JOIN app.workspaces w ON w.id = k.workspace_id
  WHERE k.lookup_id = p_lookup_id AND k.revoked_at IS NULL AND w.deleted_at IS NULL
$$;
GRANT USAGE ON SCHEMA app TO ma_auth;
GRANT SELECT ON sessions, access_keys, workspaces TO ma_auth;
ALTER FUNCTION app.resolve_session(bytea) OWNER TO ma_auth;
ALTER FUNCTION app.find_access_key(text) OWNER TO ma_auth;
REVOKE ALL ON FUNCTION app.resolve_session(bytea), app.find_access_key(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.resolve_session(bytea), app.find_access_key(text) TO ma_app;
GRANT EXECUTE ON FUNCTION app.current_workspace() TO ma_app, ma_worker;
COMMIT;

-- Часть 2. Ревизия 0002_privileges_functions: схема и права.
-- Функции SECURITY DEFINER этой ревизии (тела в миграции, сигнатуры и поведение в docs/db.md; ADR-044):
-- владелец ma_auth, SET search_path = pg_catalog, pg_temp, архив из app.current_workspace(), EXECUTE одной роли.
--   ma_app:    create_workspace, create_session, touch_session, revoke_sessions, issue_access_key,
--              revoke_access_key, delete_workspace, soft_delete_document, enqueue_purge,
--              claim_workspace_create_key, complete_workspace_create_key, release_workspace_create_key
--   ma_worker: workspaces_due_for_purge, purge_expired_workspace_create_keys,
--              ensure_audit_partitions (владелец ma_owner, без BYPASSRLS)
--   никому:    require_workspace (внутренняя проверка контекста)
BEGIN;
SET search_path = app, public;

-- ADR-047: ключи полей, файлов и слепого индекса лежат одной связкой в dek_ciphertext.
ALTER TABLE workspaces DROP COLUMN bidx_key_ciphertext;
-- ADR-041: криптоудаление ставит dek_ciphertext = NULL, это допустимо только у удалённого архива.
ALTER TABLE workspaces ALTER COLUMN dek_ciphertext DROP NOT NULL;
ALTER TABLE workspaces ADD CONSTRAINT workspaces_dek_kept_until_deleted
  CHECK (dek_ciphertext IS NOT NULL OR deleted_at IS NOT NULL);
-- original_name из POST /uploads хранится зашифрованным до POST /documents (document_files.original_name_ct).
ALTER TABLE uploads ADD COLUMN original_name_ct bytea;

-- ADR-045: все операции с Idempotency-Key внутри архива и тело ответа.
ALTER TABLE idempotency_keys DROP CONSTRAINT idempotency_keys_operation_check;
ALTER TABLE idempotency_keys ADD CONSTRAINT idempotency_keys_operation_check
  CHECK (operation IN ('documents.create','exports.create','suggestions.create','uploads.create','workspace.rotateKey'));
ALTER TABLE idempotency_keys ADD COLUMN response_body_ct bytea;  -- AEAD ключом архива; заголовков не хранит
ALTER TABLE idempotency_keys ADD CONSTRAINT idempotency_keys_body_when_completed
  CHECK (response_body_ct IS NULL OR state = 'completed');

-- ADR-045: POST /workspaces, архива ещё нет. Ключ хранится как SHA-256. Политик и прав для ролей приложения нет:
-- доступ только через функции claim/complete/release_workspace_create_key и purge_expired_workspace_create_keys.
CREATE TABLE workspace_create_keys (
  key_sha256       bytea PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
  fingerprint      bytea NOT NULL CHECK (octet_length(fingerprint) = 32),
  state            text NOT NULL DEFAULT 'in_progress' CHECK (state IN ('in_progress','completed')),
  response_status  smallint,
  workspace_id     uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  response_body_ct bytea,
  expires_at       timestamptz NOT NULL DEFAULT now() + interval '24 hours',
  CHECK ((state = 'completed') = (response_status IS NOT NULL)),
  CHECK (state = 'in_progress' OR (workspace_id IS NOT NULL AND response_body_ct IS NOT NULL))
);
CREATE INDEX workspace_create_keys_expiring ON workspace_create_keys (expires_at);
ALTER TABLE workspace_create_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_create_keys FORCE ROW LEVEL SECURITY;

-- Права сверх части 1
GRANT DELETE ON idempotency_keys TO ma_app;   -- ADR-045: снять in_progress после ответа 4xx или 5xx (под RLS)
GRANT UPDATE ON purge_queue TO ma_worker;     -- счётчик попыток и next_attempt_at
GRANT INSERT, UPDATE ON workspaces, sessions, access_keys TO ma_auth;
GRANT SELECT, INSERT, UPDATE ON consents TO ma_auth;
GRANT INSERT ON purge_queue TO ma_auth;
GRANT SELECT, INSERT, UPDATE, DELETE ON workspace_create_keys TO ma_auth;
GRANT SELECT ON documents, uploads, exports, idempotency_keys TO ma_auth;
GRANT UPDATE ON documents TO ma_auth;         -- soft_delete_document: hide_deleted не даёт ma_app сделать это самому
GRANT INSERT ON audit_log TO ma_auth;         -- триггер аудита при soft_delete_document
ALTER FUNCTION app.resolve_session(bytea) SET search_path = pg_catalog, pg_temp;
ALTER FUNCTION app.find_access_key(text) SET search_path = pg_catalog, pg_temp;
COMMIT;
