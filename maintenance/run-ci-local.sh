#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
maintenance_cd_repo_root

mode="full"
if [ "${1:-}" = "--quick" ]; then
  mode="quick"
  shift
fi
if [ "$#" -ne 0 ]; then
  maintenance_die "Usage: maintenance/run-ci-local.sh [--quick]"
fi

maintenance_require_command node "Install the Node.js version pinned in .github/workflows/ci.yml."
maintenance_require_command npm "Install npm with the Node.js version pinned in .github/workflows/ci.yml."
maintenance_require_command uv "Install the uv version pinned in .github/workflows/ci.yml."
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/plexa-uv-cache-${UID:-user}}"
export npm_config_cache="${npm_config_cache:-${TMPDIR:-/tmp}/plexa-npm-cache-${UID:-user}}"

required_node_version="$(sed -n 's/^[[:space:]]*node-version:[[:space:]]*\([0-9][0-9.]*\).*/\1/p' .github/workflows/ci.yml | head -n 1)"
required_uv_version="$(awk '
  /uses:[[:space:]]*astral-sh\/setup-uv@/ { in_setup_uv=1; next }
  in_setup_uv && /version:/ {
    value=$0
    sub(/^[^:]*:[[:space:]]*/, "", value)
    gsub(/["[:space:]]/, "", value)
    print value
    exit
  }
' .github/workflows/ci.yml)"
installed_node_version="$(node --version | sed 's/^v//')"
installed_uv_version="$(uv --version | awk '{print $2}')"

if [ "$installed_node_version" != "$required_node_version" ]; then
  if [ "$mode" = "full" ]; then
    maintenance_die "Node.js $required_node_version is required for an exact CI run; found $installed_node_version."
  fi
  maintenance_warn "CI uses Node.js $required_node_version; quick mode is using $installed_node_version."
fi
if [ "$installed_uv_version" != "$required_uv_version" ]; then
  if [ "$mode" = "full" ]; then
    maintenance_die "uv $required_uv_version is required for an exact CI run; found $installed_uv_version."
  fi
  maintenance_warn "CI uses uv $required_uv_version; quick mode is using $installed_uv_version."
fi

maintenance_note "Checking workflow policy and shell syntax..."
maintenance/audit-ci.sh
bash -n deploy/*.sh deploy/lib/*.sh maintenance/*.sh maintenance/lib/*.sh
uv lock --check

if [ "$mode" = "quick" ]; then
  if [ ! -x plexa_portal/node_modules/.bin/eslint ]; then
    maintenance_die "Portal dependencies are missing. Run the full check once or run npm ci in plexa_portal/."
  fi
  npm --prefix plexa_portal run lint
  npm --prefix plexa_portal run build
  maintenance_note "Quick checks passed. This did not perform a clean install, dependency audit, migrations, or tests."
  exit 0
fi

maintenance_require_command docker "Install Docker Engine with the Compose plugin and ensure the daemon is reachable."

maintenance_note "Installing and auditing the exact portal dependency tree..."
npm --prefix plexa_portal ci --ignore-scripts
npm --prefix plexa_portal audit --audit-level=high
npm --prefix plexa_portal run lint
npm --prefix plexa_portal run build

maintenance_note "Building the authored and generated documentation..."
docs/build_docs.sh

maintenance_note "Synchronizing the exact server dependency tree..."
uv sync --frozen

postgres_image="$(sed -n 's/^[[:space:]]*PLEXA_CI_POSTGRES_IMAGE:[[:space:]]*\(postgres:[^[:space:]]*\).*/\1/p' .github/workflows/ci.yml | head -n 1)"
postgres_fallback_image="$(sed -n 's/^[[:space:]]*PLEXA_CI_POSTGRES_FALLBACK_IMAGE:[[:space:]]*\([^[:space:]]*\).*/\1/p' .github/workflows/ci.yml | head -n 1)"
if [ -z "$postgres_image" ] || [[ "$postgres_image" != *@sha256:* ]] || \
  [ -z "$postgres_fallback_image" ] || [[ "$postgres_fallback_image" != *@sha256:* ]]; then
  maintenance_die "Could not find a digest-pinned PostgreSQL CI image."
fi

container_name="plexa-maintenance-postgres-$$"
cleanup() {
  docker stop "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

maintenance_note "Pulling the isolated PostgreSQL image..."
maintenance_pull_image "$postgres_image" "$postgres_fallback_image"
maintenance_note "Starting an isolated PostgreSQL container from $MAINTENANCE_PULLED_IMAGE..."
docker run --detach --rm \
  --name "$container_name" \
  --env POSTGRES_DB=plexa_test \
  --env POSTGRES_USER=plexa \
  --env POSTGRES_PASSWORD=plexa_maintenance_password \
  --publish 127.0.0.1::5432 \
  "$MAINTENANCE_PULLED_IMAGE" >/dev/null

for _ in $(seq 1 30); do
  if docker exec "$container_name" pg_isready -U plexa -d plexa_test >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! docker exec "$container_name" pg_isready -U plexa -d plexa_test >/dev/null 2>&1; then
  maintenance_die "The isolated PostgreSQL container did not become ready."
fi

postgres_port="$(docker port "$container_name" 5432/tcp | sed -n 's/.*:\([0-9][0-9]*\)$/\1/p' | head -n 1)"
if [ -z "$postgres_port" ]; then
  maintenance_die "Could not determine the isolated PostgreSQL host port."
fi

export PLEXA_DATABASE_URL="postgresql+asyncpg://plexa:plexa_maintenance_password@127.0.0.1:${postgres_port}/plexa_test"
export PLEXA_DATABASE_SYNC_URL="postgresql://plexa:plexa_maintenance_password@127.0.0.1:${postgres_port}/plexa_test"
export PLEXA_TEST_DATABASE_URL="$PLEXA_DATABASE_URL"
export PLEXA_TEST_DATABASE_SYNC_URL="$PLEXA_DATABASE_SYNC_URL"

maintenance_note "Running the migration compatibility sequence..."
uv run --frozen alembic -c plexa_server/alembic.ini upgrade head
uv run --frozen alembic -c plexa_server/alembic.ini downgrade 20260523_01
uv run --frozen python plexa_server/tests/migrations/verify_hardening_upgrade.py seed
uv run --frozen alembic -c plexa_server/alembic.ini upgrade head
uv run --frozen python plexa_server/tests/migrations/verify_hardening_upgrade.py verify

maintenance_note "Running the PostgreSQL-backed server suite..."
uv run --frozen pytest -q plexa_server/tests
maintenance_note "Full local CI passed."
