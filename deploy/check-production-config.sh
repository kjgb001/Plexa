#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

env_file="${1:-deploy/production.env}"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod-check}"

if [ ! -f "$env_file" ]; then
  echo "Missing env file: $env_file" >&2
  exit 1
fi

plexa_compose "$env_file" "$project_name" config
