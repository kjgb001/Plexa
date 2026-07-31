#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

usage() {
  cat <<'EOF'
Check local production-mode inference from the host, container, and /api/ready.

Usage:
  deploy/check-local-inference.sh [env-file]

Defaults:
  env-file: deploy/local-production.env
EOF
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

env_file="${1:-deploy/local-production.env}"
deploy/check-production.sh "$env_file" --mode local --stage poststart
