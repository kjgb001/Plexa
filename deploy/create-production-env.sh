#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

usage() {
  cat <<'EOF'
Create a Plexa production env file for a single-domain deployment.

Usage:
  deploy/create-production-env.sh \
    --domain plexa.example.edu \
    --email admin@example.edu \
    --inference-url https://inference.example.edu/v1 \
    --model llama3.1

  deploy/create-production-env.sh --local --model llama3.1

Options:
  --local                Create a localhost production-mode smoke-test env.
  --domain VALUE         Public Plexa hostname, for example plexa.example.edu.
  --email VALUE          ACME contact email for Caddy certificate issuance.
  --inference-url VALUE  OpenAI-compatible inference base URL ending in /v1.
  --api-key PATH         Optional file containing an inference bearer API key.
  --timeout VALUE        Optional inference timeout in seconds. Defaults to 30.0.
  --model VALUE          Model name for default, fast, and reasoning profiles.
  --fast-model VALUE     Optional model override for the fast profile.
  --reasoning-model VALUE Optional model override for the reasoning profile.
  --admin-user VALUE     Temporary admin user id. Defaults to admin.
  --output VALUE         Env file path. Defaults to deploy/production.env.
  --force                Overwrite the output file if it already exists.
  -h, --help             Show this help text.

This creates a temporary dev-login production env for smoke testing. Replace
dev login with institutional auth before real student use.
EOF
}

domain=""
email=""
inference_url=""
api_key_file=""
timeout_s="30.0"
model=""
fast_model=""
reasoning_model=""
admin_user="admin"
output="deploy/production.env"
force="false"
local_mode="false"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --local)
      local_mode="true"
      output="deploy/local-production.env"
      domain=":80"
      email="admin@example.invalid"
      inference_url="http://host.docker.internal:11434/v1"
      shift
      ;;
    --domain)
      domain="${2:-}"
      shift 2
      ;;
    --email)
      email="${2:-}"
      shift 2
      ;;
    --inference-url)
      inference_url="${2:-}"
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
    --admin-user)
      admin_user="${2:-}"
      shift 2
      ;;
    --output)
      output="${2:-}"
      shift 2
      ;;
    --force)
      force="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_value() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    echo "Missing required option: $name" >&2
    usage >&2
    exit 2
  fi
}

reject_unsafe_env_value() {
  local name="$1"
  local value="$2"
  case "$value" in
    *'"'*|*'\'*|*$'\n'*)
      echo "$name must not contain quotes, backslashes, or newlines." >&2
      exit 2
      ;;
  esac
}

require_value "--domain" "$domain"
require_value "--email" "$email"
require_value "--inference-url" "$inference_url"
require_value "--model" "$model"

python_bin="$(plexa_resolve_python)"

if [ "$local_mode" != "true" ]; then
  case "$domain" in
    http://*|https://*|*/*|:*)
      echo "--domain should be a hostname only, for example plexa.example.edu." >&2
      exit 2
      ;;
  esac
fi

for pair in \
  "domain:$domain" \
  "email:$email" \
  "inference_url:$inference_url" \
  "timeout_s:$timeout_s" \
  "model:$model" \
  "fast_model:${fast_model:-$model}" \
  "reasoning_model:${reasoning_model:-$model}" \
  "admin_user:$admin_user"
do
  reject_unsafe_env_value "${pair%%:*}" "${pair#*:}"
done

if ! "$python_bin" - "$timeout_s" <<'PY'
import sys

try:
    timeout = float(sys.argv[1])
except ValueError:
    print("--timeout must be a number of seconds.", file=sys.stderr)
    raise SystemExit(1)

if timeout <= 0:
    print("--timeout must be greater than zero.", file=sys.stderr)
    raise SystemExit(1)
PY
then
  exit 2
fi

api_key=""
if [ -n "$api_key_file" ]; then
  if [ ! -f "$api_key_file" ]; then
    echo "--api-key file does not exist: $api_key_file" >&2
    exit 2
  fi
  if [ ! -r "$api_key_file" ]; then
    echo "--api-key file is not readable: $api_key_file" >&2
    exit 2
  fi
  api_key="$("$python_bin" - "$api_key_file" <<'PY'
from pathlib import Path
import sys

raw = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
if not raw:
    print("--api-key file is empty.", file=sys.stderr)
    raise SystemExit(1)
if "\n" in raw or "\r" in raw:
    print("--api-key file must contain a single line.", file=sys.stderr)
    raise SystemExit(1)
print(raw)
PY
)"
fi

if [ -e "$output" ] && [ "$force" != "true" ]; then
  echo "$output already exists. Pass --force to overwrite it." >&2
  exit 1
fi

fast_model="${fast_model:-$model}"
reasoning_model="${reasoning_model:-$model}"
postgres_password="$("$python_bin" -c 'import secrets; print(secrets.token_urlsafe(32))')"
log_encryption_key="$("$python_bin" -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"))')"
inference_backends="$("$python_bin" - "$inference_url" "$timeout_s" "$api_key" <<'PY'
import json
import sys

base_url = sys.argv[1]
timeout_s = float(sys.argv[2])
api_key = sys.argv[3]

backend = {
    "type": "openai-compatible",
    "base_url": base_url,
    "timeout_s": timeout_s,
}
if api_key:
    backend["api_key"] = api_key

print(json.dumps({"primary": backend}, separators=(",", ":")))
PY
)"
inference_profiles="$("$python_bin" - "$model" "$fast_model" "$reasoning_model" <<'PY'
import json
import sys

model, fast_model, reasoning_model = sys.argv[1:4]
profiles = {
    "default": {"backend_id": "primary", "model": model},
    "fast": {"backend_id": "primary", "model": fast_model},
    "reasoning": {"backend_id": "primary", "model": reasoning_model},
}

print(json.dumps(profiles, separators=(",", ":")))
PY
)"

mkdir -p "$(dirname "$output")"
if [ "$local_mode" = "true" ]; then
  site_url="http://localhost:8080"
  cors_origin="http://localhost:8080"
  http_port="8080"
  https_port="8443"
else
  site_url="https://$domain"
  cors_origin="https://$domain"
  http_port="80"
  https_port="443"
fi

cat > "$output" <<EOF
# Generated by deploy/create-production-env.sh.
# Keep this file out of git.

PLEXA_DEPLOY_ENV_FILE=$output

# Public site handled by Caddy.
PLEXA_SITE_ADDRESS=$domain
ACME_EMAIL=$email
PLEXA_HTTP_PORT=$http_port
PLEXA_HTTPS_PORT=$https_port

# Local Postgres container credentials.
POSTGRES_DB=plexa
POSTGRES_USER=plexa
POSTGRES_PASSWORD=$postgres_password

# Server runtime.
PLEXA_ENV=production
PLEXA_DATABASE_URL=postgresql+asyncpg://plexa:$postgres_password@postgres:5432/plexa
PLEXA_DATABASE_SYNC_URL=postgresql://plexa:$postgres_password@postgres:5432/plexa
PLEXA_AUTH_MODE=dev-header
PLEXA_ENABLE_DEV_LOGIN=true
PLEXA_ADMIN_USER_IDS=["$admin_user"]
PLEXA_CORS_ALLOWED_ORIGINS=["$cors_origin"]
PLEXA_LOG_ENCRYPTION_KEY=$log_encryption_key

# Backend-only inference target.
PLEXA_INFERENCE_BACKENDS=$inference_backends
PLEXA_INFERENCE_PROFILES=$inference_profiles
PLEXA_INFERENCE_REQUIRED_BACKENDS=["primary"]

# Portal build-time config.
VITE_APP_ENV=production
VITE_API_BASE_URL=/api
TARGET_API_VERSION=v1
VITE_AUTH_MODE=dev
VITE_ENABLE_DEV_LOGIN=true
EOF

chmod 600 "$output"

if [ "$local_mode" = "true" ]; then
  first_step="Start Plexa:"
  second_step="Open:"
else
  first_step="Point DNS for $domain at this server, then start Plexa:"
  second_step="Open after DNS and certificate issuance complete:"
fi

cat <<EOF
Created $output

Next:
  1. $first_step
     deploy/start-production.sh $output
  2. $second_step
     $site_url

Temporary dev login is enabled for smoke testing. Replace it before real student use.
EOF
