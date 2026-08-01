#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

if [ "$#" -lt 3 ] || [ "$3" != "--confirm" ]; then
  echo "Usage: deploy/restore-production.sh <env-file> <backup.dump> --confirm" >&2
  exit 2
fi

env_file="$1"
backup_path="$2"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod}"

if [ ! -f "$backup_path" ] || [ ! -f "$backup_path.sha256" ]; then
  echo "Backup or checksum file is missing." >&2
  exit 1
fi

backup_dir="$(cd "$(dirname "$backup_path")" && pwd)"
backup_name="$(basename "$backup_path")"
(
  cd "$backup_dir"
  sha256sum --check "$backup_name.sha256"
)
plexa_compose "$env_file" "$project_name" stop caddy plexa_server plexa_retention

plexa_compose "$env_file" "$project_name" exec -T postgres \
  sh -c 'pg_restore --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$backup_path"
plexa_compose "$env_file" "$project_name" run --rm plexa_migrate
plexa_compose "$env_file" "$project_name" up -d plexa_server plexa_retention caddy

echo "Restore complete. Run deploy/check-production.sh next."
