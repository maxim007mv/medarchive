#!/usr/bin/env bash
# Runs once, on an empty data volume, as the superuser (docker-entrypoint-initdb.d).
# Roles must exist before migration 0001: ma_owner cannot create a BYPASSRLS role itself.
set -euo pipefail

psql --no-psqlrc --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set db="$POSTGRES_DB" \
  --set owner_password="$MA_OWNER_PASSWORD" \
  --set app_password="$MA_APP_PASSWORD" \
  --set worker_password="$MA_WORKER_PASSWORD" <<'SQL'
CREATE ROLE ma_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE ma_app LOGIN NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE ma_worker LOGIN NOBYPASSRLS PASSWORD :'worker_password';
CREATE ROLE ma_auth NOLOGIN BYPASSRLS;

-- Migration 0001 runs ALTER FUNCTION ... OWNER TO ma_auth, which needs SET on ma_auth;
-- without INHERIT, ma_owner gets none of ma_auth's privileges.
GRANT ma_auth TO ma_owner WITH INHERIT FALSE, SET TRUE;

-- The owner creates the app schema and the trusted extensions in public.
ALTER DATABASE :"db" OWNER TO ma_owner;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO ma_app, ma_worker;
SQL
