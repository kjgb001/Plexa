#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

env_file="${1:-deploy/production.env}"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod}"

if [ ! -f "$env_file" ]; then
  cat >&2 <<EOF
Missing env file: $env_file

Create it first, for example:
  deploy/create-production-env.sh --domain plexa.example.edu --email admin@example.edu --inference-url https://inference.example.edu/v1 --model llama3.1
EOF
  exit 1
fi

plexa_compose "$env_file" "$project_name" up -d --build

plexa_compose "$env_file" "$project_name" ps
