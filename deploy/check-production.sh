#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

usage() {
  cat <<'EOF'
Check a Plexa production deployment configuration.

Usage:
  deploy/check-production.sh [env-file] --mode local|domain --stage prestart|poststart|all

Defaults:
  env-file: deploy/production.env
  mode:     auto-detected from PLEXA_SITE_ADDRESS
  stage:    prestart

Use --mode local for localhost production-mode smoke tests.
Use --mode domain for real domain-backed production deployments.
EOF
}

env_file=""
mode="auto"
stage="prestart"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      mode="${2:-}"
      shift 2
      ;;
    --stage)
      stage="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      plexa_die "Unknown option: $1"
      ;;
    *)
      if [ -n "$env_file" ]; then
        plexa_die "Unexpected argument: $1"
      fi
      env_file="$1"
      shift
      ;;
  esac
done

env_file="${env_file:-deploy/production.env}"
plexa_require_env_file "$env_file"
python_bin="$(plexa_resolve_python)"

failures=0
warnings=0
inference_base_url=""
inference_api_key=""
inference_api_key_present="false"
inference_models=""

ok() {
  printf 'OK: %s\n' "$*"
}

warn_check() {
  printf 'WARN: %s\n' "$*" >&2
  warnings=$((warnings + 1))
}

fail_check() {
  printf 'FAIL: %s\n' "$*" >&2
  failures=$((failures + 1))
}

env_value() {
  plexa_env_value "$env_file" "$1"
}

is_placeholder_value() {
  local value="$1"
  case "$value" in
    ""|replace-with*|*replace-with-*|*"<model-name>"*)
      return 0
      ;;
  esac
  return 1
}

require_env_value() {
  local key="$1"
  local value

  value="$(env_value "$key")"
  if is_placeholder_value "$value"; then
    fail_check "$key is missing or still contains a placeholder."
    return
  fi
  ok "$key is set."
}

validate_json_env() {
  local key="$1"
  local value

  value="$(env_value "$key")"
  if [ -z "$value" ]; then
    fail_check "$key is missing."
    return
  fi

  if "$python_bin" - "$key" "$value" <<'PY'
import json
import sys

key = sys.argv[1]
value = sys.argv[2]

try:
    parsed = json.loads(value)
except json.JSONDecodeError as exc:
    print(f"{key} is not valid JSON: {exc}", file=sys.stderr)
    raise SystemExit(1)

if key in {"PLEXA_INFERENCE_BACKENDS", "PLEXA_INFERENCE_PROFILES"} and not isinstance(parsed, dict):
    print(f"{key} must be a JSON object.", file=sys.stderr)
    raise SystemExit(1)
if key in {"PLEXA_INFERENCE_REQUIRED_BACKENDS", "PLEXA_ADMIN_USER_IDS", "PLEXA_CORS_ALLOWED_ORIGINS"} and not isinstance(parsed, list):
    print(f"{key} must be a JSON array.", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    ok "$key contains valid JSON."
  else
    fail_check "$key contains invalid JSON."
  fi
}

infer_mode() {
  local site_address

  site_address="$(env_value PLEXA_SITE_ADDRESS)"
  if [ "$mode" != "auto" ]; then
    return
  fi

  case "$site_address" in
    :*|localhost|localhost:*|127.*)
      mode="local"
      ;;
    *)
      mode="domain"
      ;;
  esac
}

check_required_files() {
  local required_files=(
    docker-compose.prod.yml
    deploy/Caddyfile
    deploy/caddy.Dockerfile
    plexa_portal/package.json
    plexa_portal/package-lock.json
    plexa_portal/tsconfig.json
    plexa_portal/tsconfig.app.json
    plexa_portal/tsconfig.node.json
  )
  local path

  for path in "${required_files[@]}"; do
    if [ -f "$path" ]; then
      ok "$path exists."
    else
      fail_check "$path is missing. Production Docker builds will fail."
    fi
  done

  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    for path in plexa_portal/package.json plexa_portal/package-lock.json plexa_portal/tsconfig.json plexa_portal/tsconfig.app.json plexa_portal/tsconfig.node.json; do
      if git check-ignore -q "$path"; then
        fail_check "$path is ignored by git. Remote production checkouts may miss it and npm ci will fail."
      else
        ok "$path is not ignored by git."
      fi
    done
  else
    warn_check "Not inside a git worktree; skipped git ignore checks."
  fi
}

check_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    fail_check "Docker CLI is not installed or is not on PATH."
    return
  fi
  ok "Docker CLI is installed."

  if docker compose version >/dev/null 2>&1; then
    ok "Docker Compose plugin is available."
  else
    fail_check "Docker Compose plugin is unavailable. Install the Docker Compose v2 plugin so 'docker compose' works."
  fi

  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable by the current user."
  else
    fail_check "Docker daemon is not reachable by this user. On Linux/Pop!_OS, start Docker and add the user to the docker group, then log out and back in."
  fi
}

check_compose_config() {
  if plexa_compose "$env_file" "${PLEXA_COMPOSE_PROJECT:-plexa-prod-check}" config >/dev/null; then
    ok "Docker Compose config renders successfully."
  else
    fail_check "Docker Compose config failed to render for $env_file."
  fi
}

check_env_basics() {
  local key
  local required_keys=(
    PLEXA_DEPLOY_ENV_FILE
    PLEXA_SITE_ADDRESS
    ACME_EMAIL
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

  for key in "${required_keys[@]}"; do
    require_env_value "$key"
  done

  for key in PLEXA_ADMIN_USER_IDS PLEXA_CORS_ALLOWED_ORIGINS PLEXA_INFERENCE_BACKENDS PLEXA_INFERENCE_PROFILES PLEXA_INFERENCE_REQUIRED_BACKENDS; do
    validate_json_env "$key"
  done

  if [ "$(env_value PLEXA_ENV)" != "production" ]; then
    fail_check "PLEXA_ENV must be production for this deployment stack."
  fi

  if [ "$(env_value PLEXA_AUTH_MODE)" = "dev-header" ] || [ "$(env_value VITE_AUTH_MODE)" = "dev" ]; then
    warn_check "Temporary dev login is enabled. This is acceptable for smoke testing only, not real student use."
  fi
}

check_mode_config() {
  local site_address
  local cors_origins
  local http_port
  local https_port
  local acme_email

  site_address="$(env_value PLEXA_SITE_ADDRESS)"
  cors_origins="$(env_value PLEXA_CORS_ALLOWED_ORIGINS)"
  http_port="$(env_value PLEXA_HTTP_PORT)"
  https_port="$(env_value PLEXA_HTTPS_PORT)"
  acme_email="$(env_value ACME_EMAIL)"

  case "$mode" in
    local)
      if [ "$site_address" != ":80" ]; then
        warn_check "Local mode usually expects PLEXA_SITE_ADDRESS=:80 for Caddy's internal listener."
      fi
      if [[ "$cors_origins" == *"http://localhost:${http_port}"* ]]; then
        ok "Local CORS includes http://localhost:${http_port}."
      else
        fail_check "Local CORS should include http://localhost:${http_port}."
      fi
      ;;
    domain)
      case "$site_address" in
        http://*|https://*|*/*|:*)
          fail_check "Domain mode PLEXA_SITE_ADDRESS must be a hostname only, for example plexa.example.edu."
          ;;
        *)
          ok "Domain mode site address is hostname-shaped."
          ;;
      esac
      if [[ "$cors_origins" == *"https://${site_address}"* ]]; then
        ok "Domain CORS includes https://${site_address}."
      else
        fail_check "Domain CORS should include https://${site_address}."
      fi
      if [ "$http_port" != "80" ] || [ "$https_port" != "443" ]; then
        warn_check "Domain mode normally needs PLEXA_HTTP_PORT=80 and PLEXA_HTTPS_PORT=443 for Caddy automatic HTTPS."
      fi
      if [ "$acme_email" = "admin@example.invalid" ] || [[ "$acme_email" == *@example.* ]]; then
        fail_check "Domain mode ACME_EMAIL must be a real contact email for certificate issuance."
      fi
      ;;
    *)
      plexa_die "--mode must be local, domain, or auto."
      ;;
  esac
}

check_port_availability() {
  local label="$1"
  local port="$2"
  local listeners

  if ! command -v ss >/dev/null 2>&1; then
    warn_check "ss is not available; skipped host port check for $label port $port."
    return
  fi

  listeners="$(ss -ltn "sport = :$port" 2>/dev/null | sed '1d' || true)"
  if [ -n "$listeners" ]; then
    warn_check "$label port $port already has a listener. This is fine only if it is the existing Plexa stack."
  else
    ok "$label port $port has no current listener."
  fi
}

load_inference_info() {
  local backends
  local profiles
  local output

  backends="$(env_value PLEXA_INFERENCE_BACKENDS)"
  profiles="$(env_value PLEXA_INFERENCE_PROFILES)"

  if ! output="$("$python_bin" - "$backends" "$profiles" <<'PY' 2>&1
import json
import sys

backends = json.loads(sys.argv[1])
profiles = json.loads(sys.argv[2])

if not backends:
    print("No inference backends configured.", file=sys.stderr)
    raise SystemExit(1)

backend_id = "primary" if "primary" in backends else next(iter(backends))
spec = backends[backend_id]
if not isinstance(spec, dict):
    print(f"Inference backend {backend_id!r} must be an object.", file=sys.stderr)
    raise SystemExit(1)
if spec.get("type") != "openai-compatible":
    print(f"Inference backend {backend_id!r} must be openai-compatible in production.", file=sys.stderr)
    raise SystemExit(1)
base_url = spec.get("base_url")
if not isinstance(base_url, str) or not base_url.strip():
    print(f"Inference backend {backend_id!r} needs a base_url.", file=sys.stderr)
    raise SystemExit(1)

models = []
for profile in profiles.values():
    if isinstance(profile, dict) and profile.get("backend_id") == backend_id and profile.get("model"):
        models.append(str(profile["model"]))

print(f"base_url={base_url.rstrip('/')}")
print(f"api_key_present={'true' if spec.get('api_key') else 'false'}")
print(f"api_key={spec.get('api_key', '')}")
print(f"models={','.join(sorted(set(models)))}")
PY
  )"; then
    fail_check "Inference configuration is invalid: $output"
    return
  fi

  while IFS='=' read -r key value; do
    case "$key" in
      base_url)
        inference_base_url="$value"
        ;;
      api_key_present)
        inference_api_key_present="$value"
        ;;
      api_key)
        inference_api_key="$value"
        ;;
      models)
        inference_models="$value"
        ;;
    esac
  done <<< "$output"

  ok "Inference backend config resolves to $inference_base_url."
  if [ "$inference_api_key_present" = "true" ]; then
    ok "Inference backend API key is configured."
  fi
  if [ -n "$inference_models" ]; then
    ok "Inference profiles reference model(s): $inference_models."
  fi
}

inference_models_url_for_host() {
  local url="$1"
  case "$url" in
    http://host.docker.internal:*)
      printf '%s/models\n' "${url/host.docker.internal/localhost}"
      ;;
    *)
      printf '%s/models\n' "$url"
      ;;
  esac
}

url_host_port() {
  "$python_bin" - "$1" <<'PY'
from urllib.parse import urlsplit
import sys

parsed = urlsplit(sys.argv[1])
host = parsed.hostname or ""
port = parsed.port
if port is None:
    port = 443 if parsed.scheme == "https" else 80
print(host)
print(port)
PY
}

check_local_inference_listener() {
  local host
  local port
  local parsed
  local listeners

  if [ -z "$inference_base_url" ]; then
    return
  fi

  parsed="$(url_host_port "$inference_base_url")"
  host="$(printf '%s\n' "$parsed" | sed -n '1p')"
  port="$(printf '%s\n' "$parsed" | sed -n '2p')"

  case "$host" in
    host.docker.internal|localhost|127.*)
      ;;
    *)
      return
      ;;
  esac

  if ! command -v ss >/dev/null 2>&1; then
    warn_check "ss is not available; skipped local inference listener binding check."
    return
  fi

  listeners="$(ss -ltn "sport = :$port" 2>/dev/null | sed '1d' || true)"
  if [ -z "$listeners" ]; then
    fail_check "No host listener found on inference port $port."
    return
  fi

  if printf '%s\n' "$listeners" | grep -qE '(127\.0\.0\.1:|\[::1\]:|::1:)' \
    && ! printf '%s\n' "$listeners" | grep -qE '(0\.0\.0\.0:|\[::\]:|\*:)'
  then
    fail_check "Inference on port $port appears bound only to loopback. Docker containers cannot reach that through host.docker.internal; bind the service to 0.0.0.0, [::], or another host address Docker can reach."
    return
  fi

  ok "Local inference listener on port $port appears reachable beyond host loopback."
}

check_inference_from_host() {
  local models_url
  local output
  local api_key="$inference_api_key"

  if [ -z "$inference_base_url" ]; then
    return
  fi

  models_url="$(inference_models_url_for_host "$inference_base_url")"
  if output="$(plexa_http_get "$models_url" 5 "$api_key" 2>&1)"; then
    if printf '%s\n' "$output" | grep -q '"data"'; then
      ok "Inference /models endpoint is reachable from the host at $models_url."
    else
      warn_check "Inference /models endpoint responded from the host but did not include a data array."
    fi
  else
    fail_check "Inference /models endpoint is not reachable from the host at $models_url. Detail: $output"
  fi
}

check_domain_dns() {
  local site_address

  site_address="$(env_value PLEXA_SITE_ADDRESS)"
  if ! command -v getent >/dev/null 2>&1; then
    warn_check "getent is not available; skipped DNS resolution check for $site_address."
    return
  fi

  if getent hosts "$site_address" >/dev/null 2>&1; then
    ok "DNS resolves for $site_address."
  else
    fail_check "DNS does not resolve for $site_address. Add the A/AAAA record before expecting Caddy TLS to work."
  fi
}

check_api_url() {
  local path="$1"
  local base_url
  local http_port
  local site_address
  local url
  local output

  if [ "$mode" = "local" ]; then
    http_port="$(env_value PLEXA_HTTP_PORT)"
    base_url="http://localhost:${http_port}"
  else
    site_address="$(env_value PLEXA_SITE_ADDRESS)"
    base_url="https://${site_address}"
  fi

  url="${base_url}${path}"
  if output="$(plexa_http_get "$url" 8 "" 2>&1)"; then
    ok "$path is reachable at $url."
    if [ "$path" = "/api/ready" ] && ! printf '%s\n' "$output" | grep -q '"status"[[:space:]]*:[[:space:]]*"ready"'; then
      fail_check "$path responded but did not report ready: $output"
    fi
  else
    fail_check "$path is not reachable at $url. Detail: $output"
  fi
}

check_container_inference() {
  if plexa_compose "$env_file" "$project_name" exec -T plexa_server python - <<'PY'
import json
import os
import sys
from urllib import error, request

backends = json.loads(os.environ["PLEXA_INFERENCE_BACKENDS"])
backend_id = "primary" if "primary" in backends else next(iter(backends))
spec = backends[backend_id]
url = spec["base_url"].rstrip("/") + "/models"
headers = {"Accept": "application/json"}
if spec.get("api_key"):
    headers["Authorization"] = f"Bearer {spec['api_key']}"

try:
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=min(float(spec.get("timeout_s", 30.0)), 5.0)) as response:
        payload = json.loads(response.read().decode("utf-8"))
except error.HTTPError as exc:
    detail = exc.read().decode("utf-8", errors="replace")
    print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
    raise SystemExit(1)
except Exception as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)

if not isinstance(payload.get("data"), list):
    print("Inference /models response did not include a data array.", file=sys.stderr)
    raise SystemExit(1)

print(f"container can reach {url}")
PY
  then
    ok "plexa_server can reach the configured inference /models endpoint."
  else
    fail_check "plexa_server cannot reach the configured inference /models endpoint."
  fi
}

run_prestart_checks() {
  local http_port
  local https_port

  check_required_files
  check_docker
  check_env_basics
  infer_mode
  check_mode_config
  load_inference_info
  check_compose_config

  http_port="$(env_value PLEXA_HTTP_PORT)"
  https_port="$(env_value PLEXA_HTTPS_PORT)"
  check_port_availability "HTTP" "$http_port"
  check_port_availability "HTTPS" "$https_port"

  if [ "$mode" = "local" ]; then
    check_local_inference_listener
    check_inference_from_host
  else
    check_domain_dns
    check_inference_from_host
  fi
}

run_poststart_checks() {
  infer_mode
  load_inference_info

  if plexa_compose "$env_file" "$project_name" ps >/dev/null; then
    ok "Docker Compose project is visible."
  else
    fail_check "Docker Compose project is not visible."
  fi

  check_container_inference
  check_api_url "/api/health"
  check_api_url "/api/ready"
}

case "$stage" in
  prestart|poststart|all)
    ;;
  *)
    plexa_die "--stage must be prestart, poststart, or all."
    ;;
esac

infer_mode
printf 'Checking Plexa %s production setup (%s): %s\n' "$mode" "$stage" "$env_file"

if [ "$stage" = "prestart" ] || [ "$stage" = "all" ]; then
  run_prestart_checks
fi

if [ "$stage" = "poststart" ] || [ "$stage" = "all" ]; then
  run_poststart_checks
fi

if [ "$failures" -gt 0 ]; then
  printf 'Production check failed with %s failure(s) and %s warning(s).\n' "$failures" "$warnings" >&2
  exit 1
fi

printf 'Production check passed with %s warning(s).\n' "$warnings"
