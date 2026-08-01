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
Use HTTPS across hosts. For a trusted private network that intentionally uses
HTTP, pass `--allow-insecure-inference`; never use that override for a public
inference endpoint.

## Files

- [docker-compose.prod.yml](../docker-compose.prod.yml): production stack.
- [create-production-env.sh](create-production-env.sh): generates `deploy/production.env` from deployment inputs.
- [start-production.sh](start-production.sh): starts the production stack with the correct Compose flags.
- [check-production-config.sh](check-production-config.sh): renders the Compose config without starting services.
- [check-production.sh](check-production.sh): validates local or domain production setup before and after startup.
- [deploy-production.sh](deploy-production.sh): guided domain-backed production deploy flow.
- [smoke-local-prod.sh](smoke-local-prod.sh): guided local production-mode smoke-test flow.
- [seed-local-prod.sh](seed-local-prod.sh): seeds dev course data inside the local production stack.
- [check-local-inference.sh](check-local-inference.sh): verifies local inference from the container and `/api/ready`.
- [backup-production.sh](backup-production.sh): creates a checksummed Postgres dump.
- [restore-production.sh](restore-production.sh): restores a dump with application writers stopped.
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
- An institutional OIDC application registration for real student use.
- An explicit session-content retention period approved by the institution.

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

2. Generate, start, and verify the production stack:

```bash
deploy/deploy-production.sh \
  --domain plexa.<institution>.edu \
  --email admin@<institution>.edu \
  --inference-url https://inference.<institution>.edu/v1 \
  --model <model-name> \
  --oidc-authority https://login.<institution>.edu \
  --oidc-client-id plexa \
  --oidc-audience plexa-api \
  --admin-user <initial-admin-subject> \
  --retention-days 365
```

This creates `deploy/production.env`, validates the setup, starts the stack, and
checks `/api/health`, `/api/ready`, Caddy reachability, and inference reachability.
It also generates a random Postgres password and encrypted-log keyring, stores
inference credentials in Docker secret files, configures Caddy for the domain,
sets `VITE_API_BASE_URL=/api`, and configures verified OIDC/JWT authentication.

Before running it, register Plexa as a public Authorization Code + PKCE client
with the identity provider. Configure these exact browser return URLs:

```text
Redirect URI: https://plexa.<institution>.edu/auth/callback
Post-logout URI: https://plexa.<institution>.edu/login
```

The identity provider must issue access tokens whose `iss` matches its discovery
document, whose `aud` contains the value passed to `--oidc-audience`, and whose
subject claim identifies one stable institutional user. Use `--user-id-claim`
only when the institution intentionally uses a claim other than `sub`.
The scopes passed with `--oidc-scope` must cause the provider to issue an access
token for the Plexa API. Provider-specific API scopes or resource configuration
may be required; an ID token is not accepted as an API credential.

`--admin-user` must be the stable value of the configured user-id claim for the
person who will bootstrap the first courses. Instead of an individual bootstrap
admin, an institution can pass both `--roles-claim <claim>` and
`--admin-role <role-value>` to map an institutional role to Plexa administration.

If the inference endpoint requires a bearer token, put the token in a local file
that is not committed and pass the file path:

```bash
deploy/deploy-production.sh \
  --domain plexa.<institution>.edu \
  --email admin@<institution>.edu \
  --inference-url https://inference.<institution>.edu/v1 \
  --api-key /secure/path/inference-api-key \
  --model <model-name> \
  --oidc-authority https://login.<institution>.edu \
  --oidc-client-id plexa \
  --oidc-audience plexa-api \
  --admin-user <initial-admin-subject> \
  --retention-days 365
```

For an HTTP inference endpoint reachable only over a protected institutional
network, add `--allow-insecure-inference`. The generated server configuration
otherwise rejects non-HTTPS inference before startup.

If DNS or TLS propagation is not ready yet, start without post-start checks and
run them later:

```bash
deploy/deploy-production.sh --env-file deploy/production.env --skip-postcheck
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

3. Open:

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
- OIDC issuer, audience, JWKS, and portal client values
- encrypted-log keyring and inference API-key secret file paths
- `PLEXA_CONTENT_RETENTION_DAYS`
- `PLEXA_INFERENCE_BACKENDS`
- `PLEXA_INFERENCE_PROFILES`

For the bundled Postgres service, keep the database host as `postgres` in the database URLs.

For a managed or institution-owned external Postgres server:

- remove or ignore the compose `postgres` service only after adapting the stack
- point `PLEXA_DATABASE_URL` and `PLEXA_DATABASE_SYNC_URL` at the external database
- keep runtime credentials least-privilege where possible

## Temporary Dev Login

Domain production defaults to OIDC. Temporary username login must be requested
explicitly and is only for a private smoke test:

```bash
deploy/deploy-production.sh \
  --domain plexa.<institution>.edu \
  --email admin@<institution>.edu \
  --inference-url https://inference.<institution>.edu/v1 \
  --model <model-name> \
  --retention-days 30 \
  --temporary-dev-login \
  --admin-user admin
```

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

This trusts a browser-supplied username header. It is not institutional auth and
must never be exposed to real students.

To disable temporary dev login later:

```env
PLEXA_AUTH_MODE=bearer-jwt
PLEXA_ENABLE_DEV_LOGIN=false
VITE_AUTH_MODE=oidc
VITE_ENABLE_DEV_LOGIN=false
```

Regenerate the env with the normal OIDC flags rather than hand-switching only
these four values; issuer, audience, JWKS, redirect, and client settings are all
required together.

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

Recommended:

```bash
deploy/smoke-local-prod.sh --model llama3.1
```

This creates `deploy/local-production.env` if needed, checks local prerequisites,
builds and starts the production stack, seeds development course data, checks
container inference reachability, and verifies `/api/ready`.

If you need to regenerate the env file, pass `--force`:

```bash
deploy/smoke-local-prod.sh --model llama3.1 --force
```

Manual path:

```bash
deploy/create-production-env.sh --local --model llama3.1
deploy/check-production.sh deploy/local-production.env --mode local --stage prestart
deploy/start-production.sh deploy/local-production.env
deploy/seed-local-prod.sh
deploy/check-local-inference.sh
```

Open:

```text
http://localhost:8080
```

If your inference server runs on the host machine, use
`http://host.docker.internal:<port>/v1` from inside the container. On Linux this
is enabled by the production compose file through Docker's `host-gateway`.

For Ollama, the common failure mode is that the host can run
`curl http://localhost:11434/v1/models` but the container cannot connect because
Ollama is bound only to `127.0.0.1`. Check the listener:

```bash
ss -ltnp 'sport = :11434'
systemctl cat ollama
systemctl show ollama -p FragmentPath -p DropInPaths -p Environment
```

The listener must be on an address Docker can reach, such as `0.0.0.0:11434` or
`[::]:11434`, not only `127.0.0.1:11434`. Do not expose that port publicly
unless the host firewall and network policy make it safe.

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

For a guided post-start check:

```bash
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

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
bash -n deploy/*.sh deploy/lib/*.sh
deploy/create-production-env.sh --domain plexa.example.test --email ci@example.org --inference-url https://inference.example.test/v1 --model llama3.1 --timeout 30 --retention-days 30 --temporary-dev-login --admin-user ci-admin --output /tmp/plexa-production.env --force
deploy/create-production-env.sh --local --model llama3.1 --output /tmp/plexa-local-production.env --force
deploy/check-production-config.sh /tmp/plexa-production.env
deploy/check-production-config.sh /tmp/plexa-local-production.env
```

`deploy/check-production-config.sh` validates quietly by default. Pass `--show`
before the env-file argument only when you intentionally need the fully rendered
Compose config; that output can contain resolved secrets and must not be shared.

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

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` | Start Docker and give the current user socket access. On Linux/Pop!_OS: `sudo systemctl enable --now docker`, `sudo usermod -aG docker "$USER"`, then log out and back in. Verify with `docker ps`. |
| `python: command not found` | Use the deploy scripts after this repo change; they resolve `python3` first, then `python`, and fail clearly if neither exists. |
| Docker build fails at `npm ci` because no lockfile exists | Confirm `plexa_portal/package-lock.json` exists in the checkout. The production build intentionally uses `npm ci`, so the lockfile must be tracked. |
| `docker compose exec` says it needs at least two arguments | Use `deploy/seed-local-prod.sh` instead of manually typing the long seed command. |
| `/api/ready` reports inference unavailable | Run `deploy/check-local-inference.sh` for local-prod or `deploy/check-production.sh deploy/production.env --mode domain --stage poststart` for domain prod. |
| Host `curl localhost:11434/v1/models` works but Plexa cannot reach Ollama | Ollama is probably bound only to `127.0.0.1`. Bind it to an address Docker can reach and verify with `ss -ltnp 'sport = :11434'`. |
| Domain deployment cannot get HTTPS | Confirm DNS points at the server, ports `80` and `443` are reachable from the public internet, and `PLEXA_SITE_ADDRESS` is a hostname rather than a URL. |
| Generated env file still has old values | Regenerate with `--force`, or edit the env file directly and restart with `deploy/start-production.sh <env-file>`. |

## Update

Pull or deploy the new code, then rebuild and restart:

```bash
deploy/start-production.sh deploy/production.env
```

Run only migrations:

```bash
docker compose --env-file deploy/production.env -f docker-compose.prod.yml run --rm plexa_migrate
```

## Operational Notes

- Do not commit `deploy/production.env`.
- Keep the Postgres port private unless your institution explicitly manages database networking.
- Keep `PLEXA_WEB_CONCURRENCY=1`; process-local session locks, disabled transcripts, and rate limits are not coordinated across workers yet.
- `logging_policy=disabled` persists session metadata and reflections but no transcript messages. The transcript exists only in web-process memory and is lost on restart.
- Existing sessions keep a private snapshot of their lesson and inference config. Editing a lesson affects new sessions only.
- Retention cleanup removes transcript/reflection content and encrypted payloads after `PLEXA_CONTENT_RETENTION_DAYS`, while preserving content-free submission metadata.
- Run `deploy/backup-production.sh deploy/production.env` on an institutional schedule and test `deploy/restore-production.sh deploy/production.env <dump> --confirm` before release.
- Back up `deploy/production.env` and the files under `deploy/secrets/` separately from the database. Losing the encrypted-log keyring makes retained logs unreadable.
- Prefer network paths where only `plexa_server` can reach the inference endpoint.
- Caddy manages certificates automatically when `PLEXA_SITE_ADDRESS` is a real public domain and ports `80`/`443` are reachable.
