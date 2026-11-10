#!/usr/bin/env bash
# alembic upgrade head, downgrade base, upgrade head on an empty PostgreSQL cluster that has the
# roles of infra/postgres/init, as the migrate service does (role ma_owner).
# Usage: tools/check_migrations.sh POSTGRES_MAJOR API_IMAGE
set -euo pipefail

major=$1
image=$2
name="medarchive_qa_pg$major"
password=$(python3 -c 'import secrets; print(secrets.token_hex(16))')

docker rm -f "$name" >/dev/null 2>&1 || true
docker network create "$name" >/dev/null
trap 'docker rm -f "$name" >/dev/null; docker network rm "$name" >/dev/null' EXIT

docker run -d --name "$name" --network "$name" \
  -e POSTGRES_DB=medarchive -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD="$password" \
  -e MA_OWNER_PASSWORD="$password" -e MA_APP_PASSWORD="$password" -e MA_WORKER_PASSWORD="$password" \
  -v "$PWD/infra/postgres/init:/docker-entrypoint-initdb.d:ro" "postgres:$major-alpine" >/dev/null

# TCP, not the socket: during init the server listens only on the socket.
for _ in $(seq 60); do
  docker exec "$name" pg_isready -q -h 127.0.0.1 -U postgres -d medarchive && break
  sleep 1
done
docker exec "$name" postgres --version

docker run --rm --network "$name" \
  -e DATABASE_URL="postgresql+asyncpg://ma_owner:$password@$name:5432/medarchive" "$image" \
  sh -c 'alembic upgrade head && alembic downgrade base && alembic upgrade head && alembic current'
echo "PostgreSQL $major: upgrade head, downgrade base, upgrade head passed"
