# Plexa Server

`plexa_server` is Plexa's FastAPI application and lesson runtime. It validates
lesson artifacts, authorizes course access, orchestrates inference, enforces
session rules, and persists course and session state.

## Responsibilities

- Course, lesson, session, message, and reflection domain models
- Course-scoped lesson authoring with optimistic revisions
- Per-session lesson and inference snapshots
- Turn limits, completion gates, reflection hooks, and idempotent message IDs
- Streaming responses with an explicit non-streaming fallback path
- Development-header and bearer-JWT authentication
- PostgreSQL persistence, Alembic migrations, and encrypted retained logs
- A validated, one-way importer for legacy filesystem datasets
- Health, readiness, retention, and structured request logging

Student-facing lesson responses intentionally omit private execution details,
including system prompts.

## Local Development

### Requirements

- Python 3.12 or 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker with the Compose plugin
- An OpenAI-compatible inference endpoint for real model responses

Run the following commands from the repository root:

```bash
uv sync --frozen
docker compose -f plexa_server/docker-compose.yml up -d
uv run python -m plexa_server.bootstrap --init-dev --init-test
uv run python -m plexa_server.utils.seed_dev_data --target dev
```

Bootstrap creates the development and test databases, runs migrations, and
creates `plexa_server/.env` with safe local defaults when it does not exist.
Existing values are preserved.

> [!CAUTION]
> `--init-test` resets the configured test schema. It never targets the
> development database unless the test database URLs have been misconfigured,
> so review custom database URLs before running it.

Start the API:

```bash
uv run python -m plexa_server.api.main
```

The server listens on `http://localhost:8000`. Useful checks are:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/ready
curl http://localhost:8000/api/debug/inference
```

`/api/health` reports process liveness. `/api/ready` also checks storage and
required inference backends. `/api/debug/inference` shows profile resolution in
development and returns 404 in production.

FastAPI serves the runtime OpenAPI schema at `/openapi.json` and interactive
Swagger UI at `/docs`. The schema advertises the configured development-header
or bearer-JWT authentication mode. The maintained static API guide is published
with the [Plexa documentation](https://kjgb001.github.io/Plexa/http-api.html).

## Inference Setup

The generated local `.env` contains example backends for:

- Ollama at `http://localhost:11434/v1`
- vLLM at `http://localhost:8001/v1`

It also defines `default`, `fast`, and `reasoning` profiles. These are examples,
not bundled models. Update the backend URLs, model names, and
`PLEXA_INFERENCE_REQUIRED_BACKENDS` to match the services your environment
actually runs. A backend listed as required must pass its health check before
`/api/ready` returns 200.

The main variables are:

| Variable | Purpose |
| --- | --- |
| `PLEXA_INFERENCE_BACKENDS` | Named OpenAI-compatible backend definitions |
| `PLEXA_INFERENCE_PROFILES` | Lesson profile to backend/model mappings |
| `PLEXA_INFERENCE_REQUIRED_BACKENDS` | Backends required for readiness |

Each backend definition may include an `api_key_file` path. The deployment
helpers set that field to the mounted inference Docker secret when `--api-key`
is supplied.

Production cannot use the stub backend or silently fall back to it. The
[deployment helper](../deploy/README.md) generates validated inference settings
and mounts API keys as Docker secrets.

## Development Data

Seed the maintained example courses and lessons into the development database:

```bash
uv run python -m plexa_server.utils.seed_dev_data --target dev
```

Seed the disposable test database explicitly when needed:

```bash
uv run python -m plexa_server.utils.seed_dev_data --target test
```

### Legacy Filesystem Migration

Filesystem storage is deprecated in `0.1.x` and will be removed in `0.2.0`.
It is no longer selected by the application and cannot be used as a seed target.
Use the one-way importer only to move an existing dataset into PostgreSQL.

Back up the source directory and prepare a PostgreSQL target that is empty and
migrated to the current Alembic head. Validate the complete operation first:

```bash
uv run python -m plexa_server.utils.import_filesystem_to_postgres \
  --data-dir /path/to/legacy-data \
  --target dev \
  --dry-run
```

Then run the import:

```bash
uv run python -m plexa_server.utils.import_filesystem_to_postgres \
  --data-dir /path/to/legacy-data \
  --target dev
```

Add `--json` for a machine-readable report. The importer validates all source
relationships and encrypted-log hashes before writing, then imports courses,
lessons, sessions, frozen inference configs, encrypted logs and metadata,
access audits, and workspace recency state. It verifies identities, content,
timestamps, relationships, counts, and encrypted bytes afterward. Optimistic
revision counters restart in PostgreSQL.

> [!IMPORTANT]
> Encrypted log bytes are copied without decryption or re-encryption. Retain the
> encryption keys referenced by the imported `key_id` values.

> [!CAUTION]
> An unexpected database failure after writes begin can leave a partial import.
> Reset the target database, migrate it back to head, and rerun the importer;
> never merge into or force-import over a populated target.

For a new, empty local database, the deprecated
`bootstrap --init-dev --import-filesystem` alias remains available through
`0.1.x`. Prefer the explicit dry-run workflow above.

## Database Migrations

Alembic configuration lives in [`alembic.ini`](alembic.ini), with project
guidance in [`alembic/README`](alembic/README).

From the repository root:

```bash
uv run alembic -c plexa_server/alembic.ini upgrade head
```

Create a revision:

```bash
uv run alembic -c plexa_server/alembic.ini revision --autogenerate -m "describe the schema change"
```

Review autogenerated migrations by hand. They must account for existing data,
downgrades, constraints, indexes, and deployment-time locking.

## Testing

The application suite runs against PostgreSQL:

```bash
uv run --frozen pytest -q plexa_server/tests
```

Tests use `PLEXA_TEST_DATABASE_URL` and `PLEXA_TEST_DATABASE_SYNC_URL`.
Focused filesystem tests cover the deprecated reader and migration path without
treating it as an application backend.

Run a focused suite in the same way:

```bash
uv run --frozen pytest -q plexa_server/tests/api
```

CI also exercises a migration upgrade/downgrade/data-verification sequence
before the full suite.

## Authentication

The server selects authentication with `PLEXA_AUTH_MODE`:

- `dev-header` reads `X-User-Id` and is intended only for local development.
- `bearer-jwt` validates bearer-token signatures and registered claims, then
  maps the configured user ID and optional role claims into Plexa identity.

Application authorization remains server-side. Global admins come from
`PLEXA_ADMIN_USER_IDS` or a configured institutional admin role; course owners
and instructors receive course-scoped capabilities.

Production bearer authentication requires an HTTPS issuer and JWKS URL, the
expected audience, RS256, and token expiration. See
[`deploy/README.md`](../deploy/README.md) for the matching portal configuration
and OIDC callback requirements.

> [!WARNING]
> Production rejects `dev-header` unless `PLEXA_ENABLE_DEV_LOGIN=true` is set
> explicitly. That escape hatch is for private smoke tests, not real users.

## Persistence and Privacy

PostgreSQL is the only supported runtime backend. App startup fails when its
database configuration is missing instead of falling back to local files.
Filesystem classes remain only for `0.1.x` import compatibility and focused
migration tests; they are scheduled for removal in `0.2.0`.

Important data boundaries:

- Course owners and global admins can author or bind lessons; co-instructors
  cannot.
- Lessons are mutable, but every new session stores a private snapshot of its
  lesson and inference configuration. Editing a lesson does not rewrite an
  active or historical session.
- Removing a learner from a course immediately revokes access to that learner's
  existing sessions.
- Retained logs are encrypted, audited when accessed, and subject to the
  configured content-retention period.
- Retention cleanup removes transcript and reflection content while preserving
  content-free submission metadata.

> [!IMPORTANT]
> `logging_policy=disabled` means transcript messages are never persisted.
> Session metadata and reflection state may still be stored, while transcript
> messages exist only in the current web process and are lost on restart.

## Production Runtime

Setting `PLEXA_ENV=production` enables fail-closed validation for database,
authentication, CORS, encryption, retention, inference, and worker settings.
The initial supported deployment runs exactly one application worker:

```env
PLEXA_WEB_CONCURRENCY=1
```

Do not increase this value yet. Active-session locks, disabled-policy
transcripts, rate limits, stream ownership, and inference counters are not
coordinated across processes.

Use [`.env.production.example`](.env.production.example) only as a reference.
For a working Docker Compose configuration, secrets, Caddy proxy, OIDC setup,
and operational checks, follow the [production deployment guide](../deploy/README.md).

## Project Layout

```text
plexa_server/
├── alembic/       # Ordered database revisions
├── api/           # FastAPI composition, schemas, and routes
├── auth/          # Request authentication and identity mapping
├── core/          # Lesson, session, logging, and policy logic
├── db/            # SQLAlchemy models, sessions, and database configuration
├── inference/     # Backend adapters, routing, and streaming
├── models/        # Pydantic domain models
├── storage/       # PostgreSQL runtime and deprecated migration readers
├── tests/         # PostgreSQL server suite and focused migration coverage
├── utils/         # Seeding, import, retention, and cryptography tools
├── bootstrap.py
├── runtime.py
└── docker-compose.yml
```
