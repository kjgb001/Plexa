#!/usr/bin/env bash
set -euo pipefail

env_file="${1:-deploy/production.env}"
project_name="${PLEXA_COMPOSE_PROJECT:-plexa-prod}"
compose_env=(
  env
  -u ACME_EMAIL
  -u PLEXA_SITE_ADDRESS
  -u PLEXA_HTTP_PORT
  -u PLEXA_HTTPS_PORT
  -u POSTGRES_DB
  -u POSTGRES_USER
  -u POSTGRES_PASSWORD
  -u PLEXA_ENV
  -u PLEXA_DATABASE_URL
  -u PLEXA_DATABASE_SYNC_URL
  -u PLEXA_AUTH_MODE
  -u PLEXA_ENABLE_DEV_LOGIN
  -u PLEXA_ADMIN_USER_IDS
  -u PLEXA_CORS_ALLOWED_ORIGINS
  -u PLEXA_LOG_ENCRYPTION_KEY
  -u PLEXA_INFERENCE_BACKENDS
  -u PLEXA_INFERENCE_PROFILES
  -u PLEXA_INFERENCE_REQUIRED_BACKENDS
  -u VITE_APP_ENV
  -u VITE_API_BASE_URL
  -u TARGET_API_VERSION
  -u VITE_AUTH_MODE
  -u VITE_ENABLE_DEV_LOGIN
  PLEXA_DEPLOY_ENV_FILE="$env_file"
)

if [ ! -f "$env_file" ]; then
  cat >&2 <<EOF
Missing env file: $env_file

Create it first, for example:
  deploy/create-production-env.sh --domain plexa.example.edu --email admin@example.edu --inference-url https://inference.example.edu/v1 --model llama3.1
EOF
  exit 1
fi

"${compose_env[@]}" docker compose -p "$project_name" --env-file "$env_file" -f docker-compose.prod.yml up -d --build

"${compose_env[@]}" docker compose -p "$project_name" --env-file "$env_file" -f docker-compose.prod.yml ps
