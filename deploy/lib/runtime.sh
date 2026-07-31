#!/usr/bin/env bash

# Shared helpers for Plexa deployment scripts. This file is intended to be
# sourced from scripts in deploy/.

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Plexa deployment scripts require bash." >&2
  exit 1
fi

PLEXA_DEPLOY_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLEXA_DEPLOY_DIR="$(cd "$PLEXA_DEPLOY_LIB_DIR/.." && pwd)"
PLEXA_REPO_ROOT="$(cd "$PLEXA_DEPLOY_DIR/.." && pwd)"

PLEXA_DEPLOY_ENV_KEYS=(
  ACME_EMAIL
  PLEXA_SITE_ADDRESS
  PLEXA_HTTP_PORT
  PLEXA_HTTPS_PORT
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  PLEXA_ENV
  PLEXA_DATABASE_URL
  PLEXA_DATABASE_SYNC_URL
  PLEXA_AUTH_MODE
  PLEXA_ENABLE_DEV_LOGIN
  PLEXA_ADMIN_USER_IDS
  PLEXA_CORS_ALLOWED_ORIGINS
  PLEXA_LOG_ENCRYPTION_KEY
  PLEXA_INFERENCE_BACKENDS
  PLEXA_INFERENCE_PROFILES
  PLEXA_INFERENCE_REQUIRED_BACKENDS
  VITE_APP_ENV
  VITE_API_BASE_URL
  TARGET_API_VERSION
  VITE_AUTH_MODE
  VITE_ENABLE_DEV_LOGIN
)

plexa_die() {
  echo "error: $*" >&2
  exit 1
}

plexa_warn() {
  echo "warning: $*" >&2
}

plexa_note() {
  echo "$*" >&2
}

plexa_cd_repo_root() {
  cd "$PLEXA_REPO_ROOT" || plexa_die "Unable to enter repository root: $PLEXA_REPO_ROOT"
}

plexa_resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi
  plexa_die "Python 3 is required, but neither python3 nor python was found."
}

plexa_require_command() {
  local command_name="$1"
  local install_hint="${2:-}"

  if command -v "$command_name" >/dev/null 2>&1; then
    return 0
  fi

  if [ -n "$install_hint" ]; then
    plexa_die "$command_name is required. $install_hint"
  fi
  plexa_die "$command_name is required."
}

plexa_require_env_file() {
  local env_file="$1"
  if [ ! -f "$env_file" ]; then
    plexa_die "Missing env file: $env_file"
  fi
}

plexa_compose() {
  local env_file="$1"
  local project_name="$2"
  shift 2

  local compose_env=(env)
  local key
  for key in "${PLEXA_DEPLOY_ENV_KEYS[@]}"; do
    compose_env+=("-u" "$key")
  done
  compose_env+=("PLEXA_DEPLOY_ENV_FILE=$env_file")

  "${compose_env[@]}" docker compose -p "$project_name" --env-file "$env_file" -f docker-compose.prod.yml "$@"
}

plexa_env_value() {
  local env_file="$1"
  local key="$2"

  awk -v key="$key" '
    /^[[:space:]]*($|#)/ { next }
    {
      split($0, parts, "=")
      if (parts[1] == key) {
        sub(/^[^=]*=/, "")
        print
        exit
      }
    }
  ' "$env_file"
}

plexa_http_get() {
  local url="$1"
  local timeout_s="${2:-5}"
  local api_key="${3:-}"
  local python_bin

  python_bin="$(plexa_resolve_python)"
  PLEXA_HTTP_BEARER_TOKEN="$api_key" "$python_bin" - "$url" "$timeout_s" <<'PY'
import os
import sys
from urllib import error, request

url = sys.argv[1]
timeout_s = float(sys.argv[2])
api_key = os.getenv("PLEXA_HTTP_BEARER_TOKEN", "")

headers = {"Accept": "application/json"}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

try:
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout_s) as response:
        body = response.read().decode("utf-8", errors="replace")
        print(body)
except error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
    raise SystemExit(1)
except Exception as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)
PY
}
