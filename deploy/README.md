# Deploying Plexa

Plexa includes a Docker Compose stack for a single-host installation on a VPS
or institution-owned server. The same stack can run locally in production mode
for a realistic smoke test without replacing the normal development setup.

Choose the path that matches your goal:

| Goal | Entry point | Address |
| --- | --- | --- |
| Test the production stack locally | `deploy/smoke-local-prod.sh` | `http://localhost:8080` |
| Serve Plexa from an institutional domain | `deploy/deploy-production.sh` | `https://plexa.example.edu` |

## Architecture

```text
Student or instructor browser
  |
  +-- / --------> Caddy --------> React portal
  +-- /api/* ---> Caddy --------> Plexa server
                                      |
                                      +--> PostgreSQL
                                      +--> OpenAI-compatible inference
```

Caddy serves the built portal, proxies the API, and manages public TLS. The
inference endpoint is configured only on the server and is never sent to the
browser. It may run on the same host, on institutional compute, or on a separate
GPU VPS.

The Compose stack includes:

- `postgres` for application data;
- `plexa_migrate` to run Alembic before startup;
- `plexa_server` for the API and lesson runtime;
- `plexa_retention` for scheduled content cleanup; and
- `caddy` for the portal, reverse proxy, and TLS.

> [!IMPORTANT]
> This release supports one Plexa web worker. Do not add API workers or replicas;
> active-session coordination, stream ownership, rate limits, and disabled-log
> transcript state are process-local.

## Local Production Smoke Test

This is the fastest way to exercise the built portal, production runtime
validation, migrations, Caddy proxy, private Postgres network, and real
inference together. It can run beside the host-based development setup because
the API and PostgreSQL stay private to Compose while Caddy serves the portal on
port 8080.

### Requirements

- Docker Engine and Docker Compose
- Python 3 (`python3` is preferred; scripts fall back to `python`)
- A reachable OpenAI-compatible inference service
- A model already available through that service

For Ollama, pull the model first:

```bash
ollama pull llama3.1
```

Then run from the repository root:

```bash
deploy/smoke-local-prod.sh --model llama3.1
```

The script:

1. creates `deploy/local-production.env` and local secret files;
2. validates the generated Compose configuration;
3. builds and starts the stack;
4. seeds the maintained development courses and lessons; and
5. checks inference from the host, container, and `/api/ready`.

Open <http://localhost:8080>. Temporary username login is enabled in this mode;
the seeded dataset includes `tester` and `instructor`, and the generated admin
defaults to `admin`.

> [!NOTE]
> If `deploy/local-production.env` already exists, the script reuses it. New
> command-line model, timeout, or API-key values do not replace the existing
> file unless you pass `--force`.

Regenerate local configuration after changing inference settings:

```bash
deploy/smoke-local-prod.sh --model llama3.1 --force
```

Useful options:

```bash
deploy/smoke-local-prod.sh \
  --model llama3.1 \
  --fast-model qwen2.5:7b \
  --reasoning-model deepseek-r1:8b \
  --timeout 60 \
  --api-key /secure/path/inference-api-key
```

`--model` is the model identifier sent to the inference API. It populates all
three Plexa inference profiles unless `--fast-model` or `--reasoning-model`
overrides a profile. The deployment script cannot discover which models your
inference service has loaded, so this value must be explicit.

To run the same flow one step at a time:

```bash
deploy/create-production-env.sh --local --model llama3.1
deploy/check-production.sh deploy/local-production.env --mode local --stage prestart
deploy/start-production.sh deploy/local-production.env
deploy/seed-local-prod.sh deploy/local-production.env
deploy/check-local-inference.sh deploy/local-production.env
```

### Reaching Host Inference

Containers reach a host service through `host.docker.internal`; the production
Compose file maps that name through Docker's `host-gateway` on Linux. A host
inference URL therefore looks like:

```text
http://host.docker.internal:11434/v1
```

Ollama commonly listens only on `127.0.0.1`, which works for host `curl` but
refuses container connections. Check the active listener and systemd settings:

```bash
ss -ltnp 'sport = :11434'
systemctl cat ollama
systemctl show ollama -p FragmentPath -p DropInPaths -p Environment
```

The listener must use an address Docker can reach, such as `0.0.0.0:11434` or
`[::]:11434`. After changing the Ollama service environment, reload systemd,
restart Ollama, and check the listener again:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
ss -ltnp 'sport = :11434'
```

> [!WARNING]
> Binding inference to all interfaces can expose it beyond Docker. Use the host
> firewall and network policy to prevent public access to the inference port.

## Institutional Domain Deployment

The normal production path serves one origin such as
`https://plexa.example.edu`, uses institutional OIDC, and obtains certificates
through Caddy.

### 1. Prepare the Host and Services

You need:

- a Linux host with Docker Engine and Docker Compose;
- an `A` record, and optionally `AAAA`, pointing the domain to the host;
- inbound ports 80 and 443 available to Caddy;
- an ACME contact email;
- an OpenAI-compatible inference URL ending in `/v1`;
- the model identifier or identifiers Plexa should request;
- an institutional OIDC client registration; and
- an institution-approved positive content-retention period.

Use HTTPS between Plexa and inference when they communicate over public or
untrusted networks. An HTTP inference URL is accepted only with
`--allow-insecure-inference`, which should be limited to a protected private
network.

For an internal-only domain, adapt [`Caddyfile`](Caddyfile) to the institution's
DNS and TLS policy instead of assuming public ACME issuance.

### 2. Register the OIDC Client

Register Plexa as a public Authorization Code with PKCE client. Configure these
browser return URLs exactly:

```text
Redirect URI: https://plexa.example.edu/auth/callback
Post-logout URI: https://plexa.example.edu/login
```

The identity provider must issue an API access token with:

- an `iss` matching the discovery document;
- an `aud` containing the configured Plexa API audience;
- a stable subject identifier, normally `sub`; and
- an expiration claim.

An ID token is not accepted as the API credential. Some providers require a
provider-specific API scope or resource setting in addition to
`openid profile email`.

Choose one administration bootstrap method:

- pass `--admin-user` with the stable subject of the initial Plexa admin; or
- pass `--roles-claim` and `--admin-role` to map an institutional role.

### 3. Create and Start the Stack

Replace the example values and run:

```bash
deploy/deploy-production.sh \
  --domain plexa.example.edu \
  --email admin@example.edu \
  --inference-url https://inference.example.edu/v1 \
  --model llama3.1 \
  --oidc-authority https://login.example.edu \
  --oidc-client-id plexa \
  --oidc-audience plexa-api \
  --admin-user initial-admin-subject \
  --retention-days 365
```

If inference requires a bearer token, place the token in a single-line file
outside the repository and add:

```bash
--api-key /secure/path/inference-api-key
```

The helper generates `deploy/production.env`, a random PostgreSQL password, and
an encrypted-log keyring. It stores inference credentials as Docker secret
files, validates the deployment, builds and starts the services, then checks
health, readiness, Caddy, and inference reachability.

Generated env and secret files are ignored by Git. Back them up separately from
the database; retained encrypted logs cannot be recovered without their keys.

If DNS or TLS is not ready, skip external post-start checks and run them later:

```bash
deploy/deploy-production.sh --env-file deploy/production.env --skip-postcheck
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

### 4. Verify the Deployment

Run the guided check:

```bash
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

Then verify the public endpoints:

```bash
curl https://plexa.example.edu/api/health
curl https://plexa.example.edu/api/ready
```

Open `https://plexa.example.edu`, complete OIDC sign-in, confirm the expected
student or instructor role, and send a real lesson message. Automated checks do
not prove browser redirects, provider-specific token claims, or actual model
quality.

## Reusing or Editing Configuration

Start or rebuild from an existing env file:

```bash
deploy/start-production.sh deploy/production.env
```

The helper clears conflicting ambient deployment variables before invoking
Compose. The equivalent explicit command is:

```bash
PLEXA_DEPLOY_ENV_FILE=deploy/production.env \
  docker compose -p plexa-prod \
  --env-file deploy/production.env \
  -f docker-compose.prod.yml \
  up -d --build
```

To generate a replacement env file, rerun `deploy/deploy-production.sh` with the
full argument set and `--force`. To customize unsupported infrastructure, start
from [`production.env.example`](production.env.example), but keep the env-file
path synchronized with `PLEXA_DEPLOY_ENV_FILE`.

The bundled database URLs use `postgres` as the host name. Adopting an external
or managed PostgreSQL service requires adapting the Compose stack and setting
both the async runtime URL and sync Alembic URL. Use least-privilege application
credentials wherever the surrounding provisioning system permits it.

## Temporary Domain Dev Login

A domain deployment can explicitly enable username login for a private smoke
test:

```bash
deploy/deploy-production.sh \
  --domain plexa.example.edu \
  --email admin@example.edu \
  --inference-url https://inference.example.edu/v1 \
  --model llama3.1 \
  --retention-days 30 \
  --temporary-dev-login \
  --admin-user admin
```

> [!CAUTION]
> This mode trusts a username supplied by the browser. Never expose it to real
> students or treat it as institutional authentication.

Do not switch to OIDC by editing only `PLEXA_AUTH_MODE`. Regenerate the env file
with the full OIDC arguments so issuer, audience, JWKS, portal client, redirect,
and logout settings change together.

## Validation Before Release

Run backend and portal checks from the repository root:

```bash
uv run --frozen pytest -q plexa_server/tests --storage-backend=both
npm --prefix plexa_portal run lint
npm --prefix plexa_portal run build
```

Validate shell syntax, CI policy, and generated Compose configuration:

```bash
bash -n deploy/*.sh deploy/lib/*.sh
maintainence/audit-ci.sh
deploy/create-production-env.sh \
  --domain plexa.example.test \
  --email ci@example.org \
  --inference-url https://inference.example.test/v1 \
  --model ci-model \
  --retention-days 30 \
  --temporary-dev-login \
  --admin-user ci-admin \
  --output /tmp/plexa-production.env \
  --force
deploy/check-production-config.sh /tmp/plexa-production.env
```

`check-production-config.sh` is quiet by default. Its `--show` option prints the
fully rendered Compose configuration, which can include resolved secrets; do
not share that output.

## Backups, Restores, and Updates

Create a checksummed PostgreSQL dump:

```bash
deploy/backup-production.sh deploy/production.env backups
```

Back up `deploy/production.env` and `deploy/secrets/` through a separate secure
channel. The database dump does not contain the files needed to decrypt retained
logs.

Restore only during a maintenance window, using a tested backup:

```bash
deploy/restore-production.sh \
  deploy/production.env \
  backups/plexa-YYYYMMDDTHHMMSSZ.dump \
  --confirm
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

The restore script verifies the checksum, stops application writers, replaces
database contents, reapplies migrations, and restarts the stack.

For a routine application update:

```bash
deploy/backup-production.sh deploy/production.env
deploy/check-production.sh deploy/production.env --mode domain --stage prestart
deploy/start-production.sh deploy/production.env
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

Read new migration files before deployment. Test restores outside production,
and never remove an encryption key while retained records still depend on it.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Docker reports permission denied for `/var/run/docker.sock` | Start Docker and grant the current user access. On Linux, add the user to the `docker` group, then log out and back in before running `docker ps`. |
| A script reports `python: command not found` | Pull the current scripts. They try `python3`, then `python`, and print a clear error if neither exists. |
| A Caddy image fails at `npm ci` | Confirm `plexa_portal/package-lock.json` is present and tracked. Production builds intentionally require the lockfile. |
| `docker compose exec` requires another argument | Use `deploy/seed-local-prod.sh`; `exec` requires both a service and a command. |
| `/api/ready` reports inference unavailable | Run `deploy/check-local-inference.sh` locally or the domain post-start check, then inspect the configured URL, model, API key, timeout, and required backends. |
| Host inference works but the container gets connection refused | The service is probably bound only to loopback. Check the listener and bind it to an address Docker can reach without exposing it publicly. |
| Domain HTTPS is unavailable | Confirm DNS points to the host, ports 80 and 443 are reachable, and `PLEXA_SITE_ADDRESS` contains a hostname rather than a URL. |
| New command-line values seem ignored | The env file already exists. Pass `--force` to regenerate it, or edit it deliberately and restart the stack. |

Inspect service status and logs with:

```bash
docker compose -p plexa-prod --env-file deploy/production.env -f docker-compose.prod.yml ps
docker compose -p plexa-prod --env-file deploy/production.env -f docker-compose.prod.yml logs -f plexa_server
docker compose -p plexa-prod --env-file deploy/production.env -f docker-compose.prod.yml logs -f caddy
```

Use `deploy/local-production.env` instead for the local smoke stack.

## Script Reference

| Script | Purpose |
| --- | --- |
| `smoke-local-prod.sh` | Generate, start, seed, and verify local production mode |
| `deploy-production.sh` | Generate, start, and verify a domain deployment |
| `create-production-env.sh` | Generate validated local or domain env and secret files |
| `start-production.sh` | Build and start from an existing env file |
| `check-production.sh` | Run pre-start or post-start deployment checks |
| `check-production-config.sh` | Render and validate Compose without starting services |
| `check-local-inference.sh` | Check local inference and API readiness |
| `seed-local-prod.sh` | Seed maintained development data inside local production mode |
| `backup-production.sh` | Create a checksummed PostgreSQL dump |
| `restore-production.sh` | Restore a checked dump with writers stopped |
