#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

usage() {
  cat <<'EOF'
Create, start, seed, and verify a local production-mode Plexa stack.

Usage:
  deploy/smoke-local-prod.sh [options]

Options:
  --env-file PATH       Env file to use. Defaults to deploy/local-production.env.
  --model VALUE         Model for all inference profiles. Defaults to llama3.1.
  --fast-model VALUE    Optional model override for the fast profile.
  --reasoning-model VALUE
                       Optional model override for the reasoning profile.
  --api-key PATH        Optional file containing an inference bearer API key.
  --timeout VALUE       Optional inference timeout in seconds. Defaults to 30.0.
  --admin-user VALUE    Temporary admin user id. Defaults to admin.
  --force               Regenerate the env file if it already exists.
  --skip-seed           Do not seed development course data.
  -h, --help            Show this help text.
EOF
}

env_file="deploy/local-production.env"
model="llama3.1"
fast_model=""
reasoning_model=""
api_key_file=""
timeout_s="30.0"
admin_user="admin"
force="false"
seed_data="true"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --env-file)
      env_file="${2:-}"
      shift 2
      ;;
    --model)
      model="${2:-}"
      shift 2
      ;;
    --fast-model)
      fast_model="${2:-}"
      shift 2
      ;;
    --reasoning-model)
      reasoning_model="${2:-}"
      shift 2
      ;;
    --api-key)
      api_key_file="${2:-}"
      shift 2
      ;;
    --timeout)
      timeout_s="${2:-}"
      shift 2
      ;;
    --admin-user)
      admin_user="${2:-}"
      shift 2
      ;;
    --force)
      force="true"
      shift
      ;;
    --skip-seed)
      seed_data="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      plexa_die "Unknown option: $1"
      ;;
  esac
done

create_args=(--local --model "$model" --output "$env_file" --timeout "$timeout_s" --admin-user "$admin_user")
if [ -n "$fast_model" ]; then
  create_args+=(--fast-model "$fast_model")
fi
if [ -n "$reasoning_model" ]; then
  create_args+=(--reasoning-model "$reasoning_model")
fi
if [ -n "$api_key_file" ]; then
  create_args+=(--api-key "$api_key_file")
fi
if [ "$force" = "true" ]; then
  create_args+=(--force)
fi

if [ ! -f "$env_file" ] || [ "$force" = "true" ]; then
  deploy/create-production-env.sh "${create_args[@]}"
else
  plexa_note "Using existing $env_file. Pass --force to regenerate it."
fi

deploy/check-production.sh "$env_file" --mode local --stage prestart
deploy/start-production.sh "$env_file"

if [ "$seed_data" = "true" ]; then
  deploy/seed-local-prod.sh "$env_file"
fi

deploy/check-local-inference.sh "$env_file"

http_port="$(plexa_env_value "$env_file" PLEXA_HTTP_PORT)"
cat <<EOF

Local production-mode Plexa is ready:
  http://localhost:${http_port}

Temporary dev login is enabled for smoke testing.
EOF
