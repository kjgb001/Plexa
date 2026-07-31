#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib/runtime.sh
source "$SCRIPT_DIR/lib/runtime.sh"
plexa_cd_repo_root

usage() {
  cat <<'EOF'
Create, start, and verify a domain-backed Plexa production stack.

Usage:
  deploy/deploy-production.sh --domain plexa.example.edu --email admin@example.edu --inference-url https://inference.example.edu/v1 --model llama3.1
  deploy/deploy-production.sh --env-file deploy/production.env

Options:
  --env-file PATH       Env file to use. Defaults to deploy/production.env.
  --domain VALUE        Public Plexa hostname, for example plexa.example.edu.
  --email VALUE         ACME contact email for Caddy certificate issuance.
  --inference-url VALUE OpenAI-compatible inference base URL ending in /v1.
  --api-key PATH        Optional file containing an inference bearer API key.
  --timeout VALUE       Optional inference timeout in seconds. Defaults to 30.0.
  --model VALUE         Model for all inference profiles.
  --fast-model VALUE    Optional model override for the fast profile.
  --reasoning-model VALUE
                       Optional model override for the reasoning profile.
  --admin-user VALUE    Temporary admin user id. Defaults to admin.
  --force               Regenerate the env file if it already exists.
  --skip-postcheck      Start the stack but skip external health/readiness checks.
  -h, --help            Show this help text.

Temporary dev login remains enabled by the generated env for smoke testing.
Replace it with institutional auth before serving real students.
EOF
}

env_file="deploy/production.env"
domain=""
email=""
inference_url=""
api_key_file=""
timeout_s="30.0"
model=""
fast_model=""
reasoning_model=""
admin_user="admin"
force="false"
skip_postcheck="false"
create_requested="false"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --env-file)
      env_file="${2:-}"
      shift 2
      ;;
    --domain)
      domain="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --email)
      email="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --inference-url)
      inference_url="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --api-key)
      api_key_file="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --timeout)
      timeout_s="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --model)
      model="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --fast-model)
      fast_model="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --reasoning-model)
      reasoning_model="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --admin-user)
      admin_user="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --force)
      force="true"
      shift
      ;;
    --skip-postcheck)
      skip_postcheck="true"
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

require_create_arg() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    plexa_die "$name is required when generating $env_file."
  fi
}

if [ -f "$env_file" ] && [ "$create_requested" = "true" ] && [ "$force" != "true" ]; then
  plexa_die "$env_file already exists. Pass --force to regenerate it, or run deploy/deploy-production.sh --env-file $env_file to reuse it."
fi

if [ ! -f "$env_file" ] || [ "$force" = "true" ]; then
  require_create_arg "--domain" "$domain"
  require_create_arg "--email" "$email"
  require_create_arg "--inference-url" "$inference_url"
  require_create_arg "--model" "$model"

  create_args=(
    --domain "$domain"
    --email "$email"
    --inference-url "$inference_url"
    --model "$model"
    --output "$env_file"
    --timeout "$timeout_s"
    --admin-user "$admin_user"
  )
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
  deploy/create-production-env.sh "${create_args[@]}"
else
  plexa_note "Using existing $env_file."
fi

deploy/check-production.sh "$env_file" --mode domain --stage prestart
deploy/start-production.sh "$env_file"

if [ "$skip_postcheck" != "true" ]; then
  deploy/check-production.sh "$env_file" --mode domain --stage poststart
else
  plexa_note "Skipping post-start checks. Run them later with:"
  plexa_note "  deploy/check-production.sh $env_file --mode domain --stage poststart"
fi

site_address="$(plexa_env_value "$env_file" PLEXA_SITE_ADDRESS)"
cat <<EOF

Domain production Plexa target:
  https://${site_address}

Temporary dev login is enabled for smoke testing unless you changed auth settings in $env_file.
EOF
