#!/bin/sh
# Idempotent: safe to run on every `docker compose up`.
set -eu

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

# Buckets are created without versioning (ADR-047): deleted ciphertext must not survive.
mc mb --ignore-existing local/ma-quarantine local/ma-docs
mc anonymous set none local/ma-quarantine
mc anonymous set none local/ma-docs

# Raw uploads live one day.
mc ilm import local/ma-quarantine < /init/quarantine-lifecycle.json

mc admin policy create local ma-api /init/api-policy.json
mc admin user add local "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
mc admin policy attach local ma-api --user "$S3_ACCESS_KEY"
