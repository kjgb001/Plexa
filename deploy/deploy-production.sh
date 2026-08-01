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
  deploy/deploy-production.sh --domain plexa.example.edu --email admin@example.edu --inference-url https://inference.example.edu/v1 --model llama3.1 --oidc-authority https://login.example.edu --oidc-client-id plexa --oidc-audience plexa-api --admin-user <initial-admin-subject> --retention-days 365
  deploy/deploy-production.sh --env-file deploy/production.env

Options:
  --env-file PATH       Env file to use. Defaults to deploy/production.env.
  --domain VALUE        Public Plexa hostname, for example plexa.example.edu.
  --email VALUE         ACME contact email for Caddy certificate issuance.
  --inference-url VALUE OpenAI-compatible inference base URL ending in /v1.
  --allow-insecure-inference Allow HTTP inference only on a trusted private network.
  --api-key PATH        Optional file containing an inference bearer API key.
  --timeout VALUE       Optional inference timeout in seconds. Defaults to 30.0.
  --model VALUE         Model for all inference profiles.
  --fast-model VALUE    Optional model override for the fast profile.
  --reasoning-model VALUE
                       Optional model override for the reasoning profile.
  --oidc-authority VALUE OIDC issuer/authority URL.
  --oidc-discovery-url VALUE Optional OIDC discovery URL override.
  --oidc-client-id VALUE Public portal OIDC client identifier.
  --oidc-audience VALUE Required API access-token audience.
  --oidc-scope VALUE    Portal scopes. Defaults to "openid profile email".
  --user-id-claim VALUE Access-token user id claim. Defaults to sub.
  --roles-claim VALUE   Optional access-token roles claim.
  --admin-role VALUE    Optional institutional role mapped to Plexa admin.
  --retention-days VALUE Required session-content retention period.
  --temporary-dev-login Explicitly use unsafe dev login for a domain smoke test.
  --admin-user VALUE    Initial admin id; required for dev login and optional with OIDC role mapping.
  --force               Regenerate the env file if it already exists.
  --skip-postcheck      Start the stack but skip external health/readiness checks.
  -h, --help            Show this help text.

Normal domain deployments require institutional OIDC. Temporary dev login is
available only when --temporary-dev-login is supplied explicitly.
EOF
}

env_file="deploy/production.env"
domain=""
email=""
inference_url=""
allow_insecure_inference="false"
api_key_file=""
timeout_s="30.0"
model=""
fast_model=""
reasoning_model=""
oidc_authority=""
oidc_discovery_url=""
oidc_client_id=""
oidc_audience=""
oidc_scope="openid profile email"
user_id_claim="sub"
roles_claim=""
admin_role=""
retention_days=""
temporary_dev_login="false"
admin_user=""
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
    --allow-insecure-inference)
      allow_insecure_inference="true"
      create_requested="true"
      shift
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
    --oidc-authority)
      oidc_authority="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --oidc-discovery-url)
      oidc_discovery_url="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --oidc-client-id)
      oidc_client_id="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --oidc-audience)
      oidc_audience="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --oidc-scope)
      oidc_scope="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --user-id-claim)
      user_id_claim="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --roles-claim)
      roles_claim="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --admin-role)
      admin_role="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --retention-days)
      retention_days="${2:-}"
      create_requested="true"
      shift 2
      ;;
    --temporary-dev-login)
      temporary_dev_login="true"
      create_requested="true"
      shift
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
  require_create_arg "--retention-days" "$retention_days"
  if [ "$temporary_dev_login" = "true" ]; then
    require_create_arg "--admin-user" "$admin_user"
  else
    require_create_arg "--oidc-authority" "$oidc_authority"
    require_create_arg "--oidc-client-id" "$oidc_client_id"
    require_create_arg "--oidc-audience" "$oidc_audience"
    if [ -z "$admin_user" ] && { [ -z "$roles_claim" ] || [ -z "$admin_role" ]; }; then
      plexa_die "OIDC setup requires --admin-user, or both --roles-claim and --admin-role."
    fi
    if { [ -n "$roles_claim" ] && [ -z "$admin_role" ]; } || { [ -z "$roles_claim" ] && [ -n "$admin_role" ]; }; then
      plexa_die "--roles-claim and --admin-role must be supplied together."
    fi
  fi

  create_args=(
    --domain "$domain"
    --email "$email"
    --inference-url "$inference_url"
    --model "$model"
    --output "$env_file"
    --timeout "$timeout_s"
    --retention-days "$retention_days"
  )
  if [ "$temporary_dev_login" = "true" ]; then
    create_args+=(--temporary-dev-login --admin-user "$admin_user")
  else
    create_args+=(
      --oidc-authority "$oidc_authority"
      --oidc-client-id "$oidc_client_id"
      --oidc-audience "$oidc_audience"
      --oidc-scope "$oidc_scope"
      --user-id-claim "$user_id_claim"
    )
    if [ -n "$admin_user" ]; then
      create_args+=(--admin-user "$admin_user")
    fi
    if [ -n "$oidc_discovery_url" ]; then
      create_args+=(--oidc-discovery-url "$oidc_discovery_url")
    fi
    if [ -n "$roles_claim" ]; then
      create_args+=(--roles-claim "$roles_claim")
    fi
    if [ -n "$admin_role" ]; then
      create_args+=(--admin-role "$admin_role")
    fi
  fi
  if [ -n "$fast_model" ]; then
    create_args+=(--fast-model "$fast_model")
  fi
  if [ -n "$reasoning_model" ]; then
    create_args+=(--reasoning-model "$reasoning_model")
  fi
  if [ -n "$api_key_file" ]; then
    create_args+=(--api-key "$api_key_file")
  fi
  if [ "$allow_insecure_inference" = "true" ]; then
    create_args+=(--allow-insecure-inference)
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

Authentication is configured from $env_file. Do not serve students with temporary dev login.
EOF
