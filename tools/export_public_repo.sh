#!/usr/bin/env bash
# Public copy without history: the tracked tree of REF in a new git repository with one commit by
# the given author. Nothing is pushed; the push commands are printed at the end.
# Usage: tools/export_public_repo.sh --author "Name <id+user@users.noreply.github.com>" [--out DIR] [--ref main]
set -euo pipefail

usage() {
  echo "usage: $0 --author \"Name <email>\" [--out DIR] [--ref REF]" >&2
  exit 2
}

author=""
out=""
ref=main
while [[ $# -gt 0 ]]; do
  case $1 in
    --author) author=${2-}; shift 2 || usage ;;
    --out) out=${2-}; shift 2 || usage ;;
    --ref) ref=${2-}; shift 2 || usage ;;
    *) usage ;;
  esac
done
[[ $author =~ ^([^<>]+)\ \<([^<>[:space:]]+@[^<>[:space:]]+)\>$ ]] || usage
name=${BASH_REMATCH[1]}
email=${BASH_REMATCH[2]}
command -v docker >/dev/null || { echo "docker is needed for gitleaks" >&2; exit 1; }

repo=$(git rev-parse --show-toplevel)
commit=$(git -C "$repo" rev-parse --verify --quiet "$ref^{commit}") || { echo "no commit $ref" >&2; exit 1; }
out=${out:-$(dirname "$repo")/medarchive-public}
mkdir -p "$(dirname "$out")"
out=$(cd "$(dirname "$out")" && pwd -P)/$(basename "$out")
case "$out/" in
  "$repo"/*) echo "--out must be outside $repo" >&2; exit 2 ;;
esac
[[ ! -e $out ]] || { echo "$out already exists" >&2; exit 1; }

mkdir "$out"
git -C "$repo" archive "$commit" | tar -x -C "$out"

# Same pinned image as `make gitleaks`; the exported .gitleaks.toml allowlists the API examples.
image=$(sed -n 's/^GITLEAKS_IMAGE := //p' "$repo/Makefile")
if ! docker run --rm -v "$out:/src:ro" "$image" dir /src --redact --no-banner; then
  echo "gitleaks reported findings in $out: nothing committed, review and delete the directory" >&2
  exit 1
fi

git -C "$out" init -q -b main
git -C "$out" add -A
# UTC, so the commit does not carry the local time zone.
TZ=UTC git -C "$out" -c user.name="$name" -c user.email="$email" -c commit.gpgsign=false \
  commit -q -m "chore: initial public release"

cat <<EOF
Exported $ref (${commit:0:7}) to $out as $(git -C "$out" rev-parse --short HEAD) by $name <$email>.
Publish to an empty GitHub repository:
  cd "$out"
  git remote add origin git@github.com:<user>/<repo>.git
  git push -u origin main
EOF
