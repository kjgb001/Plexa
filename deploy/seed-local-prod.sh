#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

usage() {
  cat <<'EOF'
Seed local production-mode Plexa with development course data.

Usage:
  deploy/seed-local-prod.sh [env-file]

Defaults:
  env-file: deploy/local-production.env

The target is intentionally fixed to dev because local-prod uses the running
production container against its private Postgres volume.
EOF
}

env_file="${1:-deploy/local-production.env}"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod}"

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

plexa_require_env_file "$env_file"

plexa_compose "$env_file" "$project_name" exec -T plexa_server \
  python -m plexa_server.utils.seed_dev_data --target dev
