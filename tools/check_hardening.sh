#!/usr/bin/env bash
# OPS-05 and OPS-07 on a running stack: images run as non-root with HEALTHCHECK; api, web and
# migrate have a read-only root fs, no capabilities and no-new-privileges; the API connects as
# ma_app, migrations as ma_owner, and ma_app cannot change the schema.
# Usage: tools/check_hardening.sh COMPOSE_PROJECT IMAGE_TAG
set -euo pipefail

project=$1
tag=$2
fail=0
dc() { docker compose -p "$project" "$@"; }
psql() { dc exec -T db psql -U postgres -d medarchive -Atc "$1"; }

for image in "medarchive/api:$tag" "medarchive/web:$tag"; do
  user=$(docker image inspect "$image" --format '{{.Config.User}}')
  health=$(docker image inspect "$image" --format '{{if .Config.Healthcheck}}yes{{else}}no{{end}}')
  echo "$image user=${user:-root} healthcheck=$health"
  case "$user" in '' | root | 0 | 0:*) fail=1 ;; esac
  [[ $health == yes ]] || fail=1
done

for service in api web migrate; do
  container=$(dc ps -aq "$service")
  read -r read_only caps options < <(docker inspect "$container" \
    --format '{{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}} {{.HostConfig.SecurityOpt}}')
  echo "$service read_only=$read_only cap_drop=$caps security_opt=$options"
  [[ $read_only == true && $caps == *ALL* && $options == *no-new-privileges* ]] || fail=1
done

for service in api web; do
  uid=$(dc exec -T "$service" id -u)
  echo "$service uid=$uid"
  [[ $uid != 0 ]] || fail=1
done

api_role=$(dc exec -T api printenv DATABASE_URL | sed -E 's#^[^:]+://([^:]+):.*#\1#')
migrate_role=$(dc config --format json | python3 -c \
  'import json, sys; url = json.load(sys.stdin)["services"]["migrate"]["environment"]["DATABASE_URL"]; print(url.split("//")[1].split(":")[0])')
echo "api role=$api_role migrate role=$migrate_role"
[[ $api_role == ma_app && $migrate_role == ma_owner ]] || fail=1

if [[ $(psql "select count(*) from pg_namespace where nspname = 'app'") == 1 ]]; then
  foreign=$(psql "select count(*) from pg_tables where schemaname = 'app' and tableowner <> 'ma_owner'")
  can_create=$(psql "select has_schema_privilege('ma_app', 'app', 'CREATE')")
  echo "app tables not owned by ma_owner=$foreign ma_app CREATE on app=$can_create"
  [[ $foreign == 0 && $can_create == f ]] || fail=1
else
  echo "schema app absent: no migrations yet"
fi

exit "$fail"
