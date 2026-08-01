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
    --model llama3.1 \
    --oidc-authority https://login.example.edu \
    --oidc-client-id plexa \
    --oidc-audience plexa-api \
    --admin-user <initial-admin-subject> \
    --retention-days 365

  deploy/create-production-env.sh --local --model llama3.1

Options:
  --local                Create a localhost production-mode smoke-test env.
  --domain VALUE         Public Plexa hostname, for example plexa.example.edu.
  --email VALUE          ACME contact email for Caddy certificate issuance.
  --inference-url VALUE  OpenAI-compatible inference base URL ending in /v1.
  --allow-insecure-inference Allow HTTP inference only on a trusted private network.
  --api-key PATH         Optional file containing an inference bearer API key.
  --timeout VALUE        Optional inference timeout in seconds. Defaults to 30.0.
  --model VALUE          Model name for default, fast, and reasoning profiles.
  --fast-model VALUE     Optional model override for the fast profile.
  --reasoning-model VALUE Optional model override for the reasoning profile.
  --oidc-authority VALUE OIDC issuer/authority URL for a domain deployment.
  --oidc-discovery-url VALUE Optional discovery URL override.
  --oidc-client-id VALUE Public OIDC client identifier.
  --oidc-audience VALUE  Required access-token audience.
  --oidc-scope VALUE     Portal scopes. Defaults to "openid profile email".
  --user-id-claim VALUE  Access-token user id claim. Defaults to sub.
  --roles-claim VALUE    Optional access-token roles claim.
  --admin-role VALUE     Optional institutional role mapped to Plexa admin.
  --retention-days VALUE Required domain content retention period; local defaults to 30.
  --temporary-dev-login  Explicitly use unsafe dev login for a domain smoke test.
  --admin-user VALUE     Initial admin id; required for dev login and optional with OIDC role mapping.
  --output VALUE         Env file path. Defaults to deploy/production.env.
  --force                Overwrite the output file if it already exists.
  -h, --help             Show this help text.

Local mode uses development login. Domain mode requires OIDC unless the unsafe
--temporary-dev-login flag is explicitly supplied.
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
admin_user=""
output="deploy/production.env"
force="false"
local_mode="false"
temporary_dev_login="false"
allow_insecure_inference="false"
oidc_authority=""
oidc_discovery_url=""
oidc_client_id=""
oidc_audience=""
oidc_scope="openid profile email"
user_id_claim="sub"
roles_claim=""
admin_role=""
retention_days=""

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
    --allow-insecure-inference)
      allow_insecure_inference="true"
      shift
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
    --oidc-authority)
      oidc_authority="${2:-}"
      shift 2
      ;;
    --oidc-discovery-url)
      oidc_discovery_url="${2:-}"
      shift 2
      ;;
    --oidc-client-id)
      oidc_client_id="${2:-}"
      shift 2
      ;;
    --oidc-audience)
      oidc_audience="${2:-}"
      shift 2
      ;;
    --oidc-scope)
      oidc_scope="${2:-}"
      shift 2
      ;;
    --user-id-claim)
      user_id_claim="${2:-}"
      shift 2
      ;;
    --roles-claim)
      roles_claim="${2:-}"
      shift 2
      ;;
    --admin-role)
      admin_role="${2:-}"
      shift 2
      ;;
    --retention-days)
      retention_days="${2:-}"
      shift 2
      ;;
    --temporary-dev-login)
      temporary_dev_login="true"
      shift
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

if [ "$local_mode" = "true" ]; then
  retention_days="${retention_days:-30}"
  admin_user="${admin_user:-admin}"
  allow_insecure_inference="true"
elif [ "$temporary_dev_login" = "true" ]; then
  require_value "--admin-user" "$admin_user"
  require_value "--retention-days" "$retention_days"
else
  require_value "--oidc-authority" "$oidc_authority"
  require_value "--oidc-client-id" "$oidc_client_id"
  require_value "--oidc-audience" "$oidc_audience"
  require_value "--retention-days" "$retention_days"
  if [ -z "$admin_user" ] && { [ -z "$roles_claim" ] || [ -z "$admin_role" ]; }; then
    echo "OIDC setup requires --admin-user, or both --roles-claim and --admin-role, to bootstrap administration." >&2
    exit 2
  fi
  if { [ -n "$roles_claim" ] && [ -z "$admin_role" ]; } || { [ -z "$roles_claim" ] && [ -n "$admin_role" ]; }; then
    echo "--roles-claim and --admin-role must be supplied together." >&2
    exit 2
  fi
fi

python_bin="$(plexa_resolve_python)"

if ! "$python_bin" - "$inference_url" "$allow_insecure_inference" <<'PY'
import sys
from urllib.parse import urlsplit

url = sys.argv[1]
allow_insecure = sys.argv[2] == "true"
parsed = urlsplit(url)
if parsed.scheme not in {"http", "https"} or not parsed.hostname:
    print("--inference-url must be an absolute HTTP(S) URL.", file=sys.stderr)
    raise SystemExit(1)
if parsed.username or parsed.password or parsed.query or parsed.fragment:
    print("--inference-url must not contain credentials, a query, or a fragment.", file=sys.stderr)
    raise SystemExit(1)
if parsed.path.rstrip("/").endswith("/v1") is False:
    print("--inference-url must end in /v1.", file=sys.stderr)
    raise SystemExit(1)
if parsed.scheme != "https" and not allow_insecure:
    print(
        "HTTP inference requires --allow-insecure-inference and a trusted private network.",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
then
  exit 2
fi

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
  "admin_user:$admin_user" \
  "oidc_authority:$oidc_authority" \
  "oidc_discovery_url:$oidc_discovery_url" \
  "oidc_client_id:$oidc_client_id" \
  "oidc_audience:$oidc_audience" \
  "oidc_scope:$oidc_scope" \
  "user_id_claim:$user_id_claim" \
  "roles_claim:$roles_claim" \
  "admin_role:$admin_role" \
  "retention_days:$retention_days"
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

if ! "$python_bin" - "$retention_days" <<'PY'
import sys

try:
    days = int(sys.argv[1])
except ValueError:
    print("--retention-days must be a positive integer.", file=sys.stderr)
    raise SystemExit(1)
if days <= 0:
    print("--retention-days must be a positive integer.", file=sys.stderr)
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
inference_backends="$("$python_bin" - "$inference_url" "$timeout_s" <<'PY'
import json
import sys

base_url = sys.argv[1]
timeout_s = float(sys.argv[2])

backend = {
    "type": "openai-compatible",
    "base_url": base_url,
    "timeout_s": timeout_s,
}
backend["api_key_file"] = "/run/secrets/inference_api_key"

print(json.dumps({"primary": backend}, separators=(",", ":")))
PY
)"

oidc_issuer=""
oidc_jwks_url=""
if [ "$local_mode" != "true" ] && [ "$temporary_dev_login" != "true" ]; then
  if [ -z "$oidc_discovery_url" ]; then
    oidc_discovery_url="${oidc_authority%/}/.well-known/openid-configuration"
  fi
  oidc_values="$("$python_bin" - "$oidc_authority" "$oidc_discovery_url" <<'PY'
import json
import sys
import urllib.request
from urllib.parse import urlsplit

authority, url = sys.argv[1:3]

def require_secure_url(label, value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        print(f"{label} must be an absolute HTTPS URL without credentials or a fragment.", file=sys.stderr)
        raise SystemExit(1)

require_secure_url("--oidc-authority", authority)
require_secure_url("OIDC discovery URL", url)
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        if urlsplit(response.geturl()).scheme != "https":
            print("OIDC discovery may not redirect to an insecure transport.", file=sys.stderr)
            raise SystemExit(1)
        document = json.load(response)
except Exception as exc:
    print(f"Unable to load OIDC discovery document {url}: {exc}", file=sys.stderr)
    raise SystemExit(1)
issuer = document.get("issuer")
jwks_uri = document.get("jwks_uri")
if not isinstance(issuer, str) or not issuer or not isinstance(jwks_uri, str) or not jwks_uri:
    print("OIDC discovery document must provide issuer and jwks_uri.", file=sys.stderr)
    raise SystemExit(1)
require_secure_url("OIDC issuer", issuer)
require_secure_url("OIDC jwks_uri", jwks_uri)
if issuer.rstrip("/") != authority.rstrip("/"):
    print(
        "OIDC discovery issuer must match --oidc-authority.",
        file=sys.stderr,
    )
    raise SystemExit(1)
print(issuer)
print(jwks_uri)
PY
)"
  oidc_issuer="$(printf '%s\n' "$oidc_values" | sed -n '1p')"
  oidc_jwks_url="$(printf '%s\n' "$oidc_values" | sed -n '2p')"
fi
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

secret_dir="deploy/secrets"
mkdir -p "$secret_dir"
secret_stem="$(basename "$output" | tr -c 'A-Za-z0-9._-' '_')"
inference_key_secret="$secret_dir/$secret_stem.inference-api-key"
log_key_secret="$secret_dir/$secret_stem.log-encryption-key"
printf '%s\n' "$api_key" > "$inference_key_secret"
printf '{"server-managed:v1":"%s"}\n' "$log_encryption_key" > "$log_key_secret"
chmod 600 "$inference_key_secret" "$log_key_secret"

if [ "$local_mode" = "true" ] || [ "$temporary_dev_login" = "true" ]; then
  server_auth="PLEXA_AUTH_MODE=dev-header
PLEXA_ENABLE_DEV_LOGIN=true
PLEXA_ADMIN_USER_IDS=[\"$admin_user\"]"
  portal_auth="VITE_AUTH_MODE=dev
VITE_ENABLE_DEV_LOGIN=true"
else
  server_auth="PLEXA_AUTH_MODE=bearer-jwt
PLEXA_ENABLE_DEV_LOGIN=false
PLEXA_ADMIN_USER_IDS=[\"$admin_user\"]
PLEXA_AUTH_ISSUER=$oidc_issuer
PLEXA_AUTH_AUDIENCE=$oidc_audience
PLEXA_AUTH_JWKS_URL=$oidc_jwks_url
PLEXA_AUTH_ALLOWED_ALGORITHMS=RS256
PLEXA_AUTH_REQUIRE_EXP=true
PLEXA_AUTH_USER_ID_CLAIM=$user_id_claim
PLEXA_AUTH_ROLES_CLAIM=$roles_claim
PLEXA_AUTH_ADMIN_ROLE_NAME=$admin_role"
  portal_auth="VITE_AUTH_MODE=oidc
VITE_ENABLE_DEV_LOGIN=false
VITE_AUTH_AUTHORITY=$oidc_authority
VITE_AUTH_DISCOVERY_URL=$oidc_discovery_url
VITE_AUTH_CLIENT_ID=$oidc_client_id
VITE_AUTH_SCOPE=$oidc_scope
VITE_AUTH_REDIRECT_URI=$site_url/auth/callback
VITE_AUTH_LOGOUT_REDIRECT_URI=$site_url/login"
fi

auth_label="OIDC"
if [ "$local_mode" = "true" ] || [ "$temporary_dev_login" = "true" ]; then
  auth_label="temporary dev login"
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
$server_auth
PLEXA_CORS_ALLOWED_ORIGINS=["$cors_origin"]
PLEXA_LOG_ENCRYPTION_KEYS_FILE=/run/secrets/log_encryption_key
PLEXA_LOG_ENCRYPTION_ACTIVE_KEY_ID=server-managed:v1
PLEXA_LOG_ENCRYPTION_KEY_HOST_FILE=$log_key_secret
PLEXA_CONTENT_RETENTION_DAYS=$retention_days
PLEXA_WEB_CONCURRENCY=1
PLEXA_LOG_FORMAT=json
PLEXA_ALLOW_INSECURE_INFERENCE=$allow_insecure_inference

# Backend-only inference target.
PLEXA_INFERENCE_BACKENDS=$inference_backends
PLEXA_INFERENCE_PROFILES=$inference_profiles
PLEXA_INFERENCE_REQUIRED_BACKENDS=["primary"]
PLEXA_INFERENCE_API_KEY_HOST_FILE=$inference_key_secret

# Portal build-time config.
VITE_APP_ENV=production
VITE_API_BASE_URL=/api
TARGET_API_VERSION=v1
$portal_auth
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

Authentication mode: $auth_label
EOF
