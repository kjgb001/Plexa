#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

env_file="${1:-deploy/production.env}"
backup_dir="${2:-backups}"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$backup_dir/plexa-$timestamp.dump"
temporary_path="$backup_path.partial"

cleanup() {
  rm -f "$temporary_path"
}
trap cleanup EXIT

mkdir -p "$backup_dir"
plexa_compose "$env_file" "$project_name" exec -T postgres \
  sh -c 'pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$temporary_path"
test -s "$temporary_path"
mv "$temporary_path" "$backup_path"
trap - EXIT
(
  cd "$backup_dir"
  sha256sum "$(basename "$backup_path")" > "$(basename "$backup_path").sha256"
)

printf 'Created %s and %s\n' "$backup_path" "$backup_path.sha256"
printf 'Back up the deployment env and encryption keyring separately.\n'
