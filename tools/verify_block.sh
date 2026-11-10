#!/usr/bin/env bash
# Gate of block N: tools/verify_block.sh N [--keep-stack] [--no-record]. See tools/verify_block.py.
set -euo pipefail

cd "$(dirname "$0")/.."
# Node from .nvmrc when nvm is installed; CI sets Node up itself.
if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  nvm use --silent
fi
exec uv run --quiet --python 3.12 tools/verify_block.py "$@"
