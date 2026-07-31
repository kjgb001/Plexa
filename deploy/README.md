# Plexa Production Deployment

This deployment path is intended for institutions running Plexa from a VPS or an owned internal server.

It preserves the local development workflow and adds a separate production stack:

```text
student browser -> https://plexa.example.edu
  /      -> Caddy static portal
  /api/* -> plexa_server FastAPI app

plexa_server -> Postgres
plexa_server -> OpenAI-compatible inference endpoint
```

The inference endpoint is server-side only. It can be an institutional GPU host, a GPU VPS, or another OpenAI-compatible runtime reachable from the Plexa server container.

## Files

- [docker-compose.prod.yml](../docker-compose.prod.yml): production stack.
- [create-production-env.sh](create-production-env.sh): generates `deploy/production.env` from deployment inputs.
- [start-production.sh](start-production.sh): starts the production stack with the correct Compose flags.
- [check-production-config.sh](check-production-config.sh): renders the Compose config without starting services.
- [production.env.example](production.env.example): copy this to `deploy/production.env`.
- [local-production.env.example](local-production.env.example): local production-mode smoke-test config.
- [Caddyfile](Caddyfile): single-domain static portal and `/api` reverse proxy.
- [caddy.Dockerfile](caddy.Dockerfile): builds the Vite portal and serves it with Caddy.
- [../plexa_server/Dockerfile](../plexa_server/Dockerfile): builds the FastAPI server image.

## Prerequisites

- Docker and Docker Compose.
- A DNS record pointing your domain to the deployment host.
- Ports `80` and `443` reachable from the public internet if using automatic HTTPS.
- A configured OpenAI-compatible inference endpoint.
- A long-lived encrypted log key.

For an internal-only institutional domain, adapt [Caddyfile](Caddyfile) to your
institutional TLS policy instead of relying on public Let's Encrypt issuance.

The automated setup script generates the encrypted log key for you. Generate one
manually only when you are not using the script:

```bash
python3 - <<'PY'
from plexa_server.utils.cryptography import generate_encryption_key
print(generate_encryption_key())
PY
```

## Domain Setup

For a normal institutional deployment at `https://plexa.<institution>.edu`:

1. Create DNS:

```text
Type: A
Name: plexa
Value: <server public IPv4>
```

Use an `AAAA` record as well if the server has public IPv6.

2. Generate the production env file:

```bash
deploy/create-production-env.sh \
  --domain plexa.<institution>.edu \
  --email admin@<institution>.edu \
  --inference-url https://inference.<institution>.edu/v1 \
  --model <model-name>
```

This creates `deploy/production.env`, generates a random Postgres password,
generates `PLEXA_LOG_ENCRYPTION_KEY`, configures Caddy for the domain, sets
`VITE_API_BASE_URL=/api`, and enables temporary dev login for smoke testing.

3. Start Plexa:

```bash
deploy/start-production.sh
```

4. Open:

```text
https://plexa.<institution>.edu
```

## Manual Configure

If you need to customize beyond the generated defaults, copy the example
environment file:

```bash
cp deploy/production.env.example deploy/production.env
```

Then edit `deploy/production.env`.

Minimum values to replace:

- `PLEXA_SITE_ADDRESS`
- `ACME_EMAIL`
- `POSTGRES_PASSWORD`
- `PLEXA_DATABASE_URL`
- `PLEXA_DATABASE_SYNC_URL`
- `PLEXA_CORS_ALLOWED_ORIGINS`
- `PLEXA_LOG_ENCRYPTION_KEY`
- `PLEXA_INFERENCE_BACKENDS`
- `PLEXA_INFERENCE_PROFILES`

For the bundled Postgres service, keep the database host as `postgres` in the database URLs.

For a managed or institution-owned external Postgres server:

- remove or ignore the compose `postgres` service only after adapting the stack
- point `PLEXA_DATABASE_URL` and `PLEXA_DATABASE_SYNC_URL` at the external database
- keep runtime credentials least-privilege where possible

## Temporary Dev Login

The initial production stack supports temporary username login for smoke testing.

Server settings:

```env
PLEXA_AUTH_MODE=dev-header
PLEXA_ENABLE_DEV_LOGIN=true
```

Portal settings:

```env
VITE_AUTH_MODE=dev
VITE_ENABLE_DEV_LOGIN=true
```

This is not institutional auth. Replace it before real student use. Future production deployments should move to institutional OIDC/SAML/LMS-backed identity.

To disable temporary dev login later:

```env
PLEXA_AUTH_MODE=bearer-jwt
PLEXA_ENABLE_DEV_LOGIN=false
VITE_AUTH_MODE=oidc
VITE_ENABLE_DEV_LOGIN=false
```

Then configure the corresponding JWT/OIDC values documented in the server and portal READMEs.

## Start

The automated start command is:

```bash
deploy/start-production.sh
```

Prefer the helper because it clears ambient shell variables before Compose
interpolates the env file. The equivalent explicit Compose command is:

```bash
PLEXA_DEPLOY_ENV_FILE=deploy/production.env \
  docker compose -p plexa-prod --env-file deploy/production.env -f docker-compose.prod.yml up -d --build
```

The `plexa_migrate` service runs Alembic migrations before `plexa_server` starts.
If you keep the env file somewhere else, set `PLEXA_DEPLOY_ENV_FILE` to that path
as well as passing it through `--env-file`.

## Local Production-Mode Smoke Test

To run the production stack beside the normal dev setup on your machine, use the
local env example. It keeps Postgres private inside Docker and exposes Caddy on
`http://localhost:8080` instead of ports `80`/`443`.

```bash
deploy/create-production-env.sh --local --model llama3.1
```

Start:

```bash
deploy/start-production.sh deploy/local-production.env
```

Open:

```text
http://localhost:8080
```

If your inference server runs on the host machine, use
`http://host.docker.internal:<port>/v1` from inside the container. On Linux this
is enabled by the production compose file through Docker's `host-gateway`.

If you need custom local values, copy [local-production.env.example](local-production.env.example)
to `deploy/local-production.env` and edit it manually.

Check status:

```bash
docker compose -p plexa-prod --env-file <env-file> -f docker-compose.prod.yml ps
```

View logs:

```bash
docker compose -p plexa-prod --env-file <env-file> -f docker-compose.prod.yml logs -f plexa_server
docker compose -p plexa-prod --env-file <env-file> -f docker-compose.prod.yml logs -f caddy
```

## Smoke Test

Check liveness:

```bash
curl https://plexa.<institution>.edu/api/health
```

Check dependency readiness:

```bash
curl https://plexa.<institution>.edu/api/ready
```

Then open the site in a browser and sign in with a temporary username if dev login is enabled.

## Verification Checklist

Use the backend test suite before relying on the deployment stack:

```bash
python3 -m plexa_server.bootstrap --init-dev --init-test --import-filesystem
python3 -m pytest -q plexa_server/tests --storage-backend=both
```

For a faster deployment-focused backend pass:

```bash
python3 -m pytest -q plexa_server/tests/api/test_main.py
python3 -m pytest -q plexa_server/tests/bootstrap
python3 -m pytest -q plexa_server/tests/auth
python3 -m pytest -q plexa_server/tests/inference
python3 -m pytest -q plexa_server/tests/storage/test_db_postgres_storage.py
```

Validate the deployment helpers without starting services:

```bash
bash -n deploy/create-production-env.sh deploy/start-production.sh deploy/check-production-config.sh
deploy/create-production-env.sh --domain plexa.example.edu --email admin@example.edu --inference-url https://inference.example.edu/v1 --model llama3.1 --output /tmp/plexa-production.env --force
deploy/check-production-config.sh /tmp/plexa-production.env
```

Validate the portal build:

```bash
cd plexa_portal
npm run build
```

The automated tests cover runtime validation, auth behavior, inference routing,
storage contracts, migrations/bootstrap orchestration, API behavior, and core
lesson/session logic. They do not prove DNS, public TLS issuance, browser
behavior, Docker image startup, Caddy proxying, or reachability of a real
inference endpoint. Cover those with the local production-mode smoke test and
the domain smoke test above.

## Update

Pull or deploy the new code, then rebuild and restart:

```bash
docker compose --env-file deploy/production.env -f docker-compose.prod.yml build
docker compose --env-file deploy/production.env -f docker-compose.prod.yml up -d
```

Run only migrations:

```bash
docker compose --env-file deploy/production.env -f docker-compose.prod.yml run --rm plexa_migrate
```

## Operational Notes

- Do not commit `deploy/production.env`.
- Keep the Postgres port private unless your institution explicitly manages database networking.
- Back up the Postgres volume or external database on an institutional schedule.
- Keep `PLEXA_LOG_ENCRYPTION_KEY` stable and backed up securely. Losing it makes encrypted session logs unreadable.
- Prefer network paths where only `plexa_server` can reach the inference endpoint.
- Caddy manages certificates automatically when `PLEXA_SITE_ADDRESS` is a real public domain and ports `80`/`443` are reachable.
