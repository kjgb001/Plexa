# Plexa Server

`plexa_server` is the lesson runtime and policy engine for Plexa.

It is responsible for:
- validating lesson artifacts
- enforcing lesson constraints
- managing session lifecycle
- orchestrating inference backends
- persisting lessons, courses, sessions, and logs

The server now supports both:
- a legacy filesystem storage backend
- a PostgreSQL storage backend using SQLAlchemy, Alembic, and `asyncpg`

## Layout

Key directories:

```text
plexa_server/
├── api/         # FastAPI app and route modules
├── auth/        # Auth helpers and request ownership checks
├── core/        # Session and lesson runtime logic
├── data/        # Legacy filesystem-backed development data
├── db/          # Database config, models, sessions, and DB bootstrap helpers
├── inference/   # Inference abstraction and stub backend
├── models/      # Pydantic domain models
├── storage/     # Filesystem and Postgres storage implementations
├── tests/       # Backend-aware test suite
├── utils/       # Import and supporting utilities
├── alembic/     # Database migrations
└── docker-compose.yml
```

## Local Development

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the server dependencies into that environment. At minimum, the database path requires:

```bash
python3 -m pip install sqlalchemy alembic asyncpg pytest cryptography
```

If `pytest` resolves to a system binary on your machine, prefer:

```bash
python3 -m pytest
```

## PostgreSQL Setup

This repository includes a local Postgres service definition in [docker-compose.yml](docker-compose.yml).

Start the database:

```bash
docker compose up -d
```

If your machine uses the older standalone Compose binary, use:

```bash
docker-compose up -d
```

The server-local `.env` file defines the default development and test database URLs.

Important variables:
- `PLEXA_DATABASE_URL`
- `PLEXA_DATABASE_SYNC_URL`
- `PLEXA_BOOTSTRAP_DATABASE_URL`
- `PLEXA_BOOTSTRAP_DATABASE_SYNC_URL`
- `PLEXA_TEST_DATABASE_URL`
- `PLEXA_TEST_DATABASE_SYNC_URL`
- `PLEXA_TEST_STORAGE_BACKEND`
- `PLEXA_AUTH_MODE`
- `PLEXA_ADMIN_USER_IDS`
- `PLEXA_CORS_ALLOWED_ORIGINS`
- `PLEXA_INFERENCE_BACKENDS`
- `PLEXA_INFERENCE_PROFILES`
- `PLEXA_INFERENCE_REQUIRED_BACKENDS`

## Bootstrap

The application bootstrap entrypoint is [bootstrap.py](bootstrap.py).

It can:
- create `plexa_server/.env` when missing
- populate missing local defaults without overwriting existing values
- generate and persist the encrypted log key once
- seed explicit local auth defaults
- seed multi-backend inference defaults for local Ollama and vLLM targets
- wait for Postgres
- create the development and test databases
- run Alembic migrations
- optionally import the legacy filesystem dataset

The generated inference defaults are meant to be edited locally as needed. By default bootstrap writes:
- `PLEXA_AUTH_MODE=dev-header`
- `PLEXA_ADMIN_USER_IDS=["admin"]`
- `PLEXA_CORS_ALLOWED_ORIGINS=["http://localhost:5173"]`
- `PLEXA_INFERENCE_BACKENDS`
  - `ollama-local -> http://localhost:11434/v1`
  - `vllm-local -> http://localhost:8001/v1`
- `PLEXA_INFERENCE_PROFILES`
  - `default -> ollama-local / llama3.1`
  - `fast -> ollama-local / qwen2.5:7b`
  - `reasoning -> vllm-local / deepseek-r1-distill-qwen-7b`

Initialize both development and test databases:

```bash
python3 -m plexa_server.bootstrap --init-dev --init-test
```

Initialize both and import the filesystem dataset into each:

```bash
python3 -m plexa_server.bootstrap --init-dev --init-test --import-filesystem
```

Initialize only the development database:

```bash
python3 -m plexa_server.bootstrap --init-dev
```

Initialize only the test database:

```bash
python3 -m plexa_server.bootstrap --init-test
```

Write a production env template with placeholders only:

```bash
python3 -m plexa_server.bootstrap --write-prod-template
```

The lower-level Postgres-specific helpers remain in [db/bootstrap.py](db/bootstrap.py), but the intended user-facing entrypoint is the top-level bootstrap module.

Important boundary:
- bootstrap is local development and test tooling
- it is not the production provisioning contract
- production mode now refuses bootstrap by default unless `PLEXA_ALLOW_PRODUCTION_BOOTSTRAP=true` is set explicitly

## Migrations

Alembic is configured in:
- [alembic.ini](alembic.ini)
- [alembic/env.py](alembic/env.py)

Run all migrations:

```bash
alembic upgrade head
```

Create a new revision:

```bash
alembic revision -m "describe schema change"
```

For schema updates driven from models, use autogeneration carefully:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Migrations are the authoritative schema workflow. The application should not rely on ad hoc table creation at startup.

## Importing Legacy Filesystem Data

The one-way importer lives at [utils/import_filesystem_to_postgres.py](utils/import_filesystem_to_postgres.py).

Import the filesystem dataset into the development database:

```bash
python3 -m plexa_server.utils.import_filesystem_to_postgres --target dev
```

Import it into the test database:

```bash
python3 -m plexa_server.utils.import_filesystem_to_postgres --target test
```

In normal local setup, it is simpler to let the bootstrap command handle this with `--import-filesystem`.

## Storage Backends

The active persistence implementations live under [storage](storage):

- [filesystem.py](storage/filesystem.py)
- [postgres.py](storage/postgres.py)
- [storage_interface.py](storage/storage_interface.py)

The application depends on the storage interfaces. Concrete backend selection happens in the composition root, not inside core session logic.

## Production Runtime

Plexa now distinguishes between local/dev behavior and production runtime behavior.

Set:

```env
PLEXA_ENV=production
```

In production, startup fails closed when critical configuration is missing or unsafe. At minimum you should provide:
- `PLEXA_DATABASE_URL` or `PLEXA_DATABASE_SYNC_URL`
- `PLEXA_AUTH_MODE`
  - `dev-header` is rejected unless `PLEXA_ENABLE_DEV_LOGIN=true`
- `PLEXA_CORS_ALLOWED_ORIGINS`
- `PLEXA_LOG_ENCRYPTION_KEY`
- real inference configuration
  - production cannot fall back to stub inference

Production startup should run the ASGI app with explicit environment injection. For example:

```bash
uvicorn plexa_server.api.main:app --host 0.0.0.0 --port 8000
```

Reload is disabled by default. Only enable it intentionally with:

```env
PLEXA_UVICORN_RELOAD=true
```

The repository does not currently prescribe one deployment stack or process manager beyond that. The important requirement is that production config be injected explicitly rather than relying on bootstrap-generated local defaults.

### Production Database Configuration

For deployed environments, treat database values as explicit infrastructure configuration rather than bootstrap output.

Runtime variables:
- `PLEXA_DATABASE_URL`
  - async SQLAlchemy URL used by the application at runtime
- `PLEXA_DATABASE_SYNC_URL`
  - sync SQLAlchemy URL used by Alembic and any sync-only tooling

Typical values:

```env
PLEXA_DATABASE_URL=postgresql+asyncpg://app_user:app_password@db.example.com:5432/plexa
PLEXA_DATABASE_SYNC_URL=postgresql://app_user:app_password@db.example.com:5432/plexa
```

Field meanings:
- `app_user`
  - the database role the application uses during normal runtime
- `app_password`
  - that role's password, injected securely by your deployment system
- `db.example.com`
  - the real database host or service name for the deployment
- `5432`
  - the Postgres port, unless your environment uses a different one
- `plexa`
  - the production application database name

Operational recommendation:
- production runtime credentials should usually be least-privilege application credentials, not a superuser account

Optional bootstrap-only variables:
- `PLEXA_BOOTSTRAP_DATABASE_URL`
- `PLEXA_BOOTSTRAP_DATABASE_SYNC_URL`

Use those only when database creation or migration orchestration needs a different privileged connection than normal runtime. For example:

```env
PLEXA_BOOTSTRAP_DATABASE_URL=postgresql+asyncpg://bootstrap_user:bootstrap_password@db.example.com:5432/postgres
PLEXA_BOOTSTRAP_DATABASE_SYNC_URL=postgresql://bootstrap_user:bootstrap_password@db.example.com:5432/postgres
```

If you do not set the bootstrap URLs, Plexa derives them from the runtime URLs by switching the database name to `postgres`. That is acceptable for local development, but explicit bootstrap credentials are usually clearer in non-dev environments.

Production runtime now rejects obvious development-only database values such as:
- `plexa_dev_password`
- the test database name `plexa_test`

Use [`.env.production.example`](.env.production.example) as the placeholder template, not as a source of real secrets.

## Mode Switching

Use these settings when switching between local development and production-like runtime behavior.

### Development mode

Typical local server settings:

```env
PLEXA_ENV=development
PLEXA_AUTH_MODE=dev-header
PLEXA_ADMIN_USER_IDS=["admin"]
PLEXA_CORS_ALLOWED_ORIGINS=["http://localhost:5173"]
PLEXA_DATABASE_URL=postgresql+asyncpg://plexa:plexa_dev_password@localhost:5432/plexa
PLEXA_DATABASE_SYNC_URL=postgresql://plexa:plexa_dev_password@localhost:5432/plexa
PLEXA_LOG_ENCRYPTION_KEY=...
PLEXA_INFERENCE_BACKENDS={"ollama-local":{"type":"openai-compatible","base_url":"http://localhost:11434/v1","timeout_s":30.0},"vllm-local":{"type":"openai-compatible","base_url":"http://localhost:8001/v1","timeout_s":30.0}}
PLEXA_INFERENCE_PROFILES={"default":{"backend_id":"ollama-local","model":"llama3.1"},"fast":{"backend_id":"ollama-local","model":"qwen2.5:7b"},"reasoning":{"backend_id":"vllm-local","model":"deepseek-r1-distill-qwen-7b"}}
```

This mode allows:
- `dev-header` auth
- local bootstrap
- local DB and localhost inference endpoints

### Production-like mode

Typical production-oriented server settings:

```env
PLEXA_ENV=production
PLEXA_AUTH_MODE=bearer-jwt
PLEXA_ENABLE_DEV_LOGIN=false
PLEXA_ADMIN_USER_IDS=["instructor-admin-1"]
PLEXA_CORS_ALLOWED_ORIGINS=["https://app.example.com"]
PLEXA_DATABASE_URL=postgresql+asyncpg://...
PLEXA_DATABASE_SYNC_URL=postgresql://...
PLEXA_LOG_ENCRYPTION_KEY=...
PLEXA_INFERENCE_BACKENDS={"primary":{"type":"openai-compatible","base_url":"https://inference.example.com/v1","timeout_s":30.0}}
PLEXA_INFERENCE_PROFILES={"default":{"backend_id":"primary","model":"your-model-name"}}
PLEXA_INFERENCE_REQUIRED_BACKENDS=["primary"]
```

In this mode:
- startup rejects `PLEXA_AUTH_MODE=dev-header`
  - unless `PLEXA_ENABLE_DEV_LOGIN=true` is explicitly set for temporary smoke testing
- startup rejects missing CORS origins
- startup rejects missing encrypted-log key
- startup rejects stub inference and stub fallback
- bootstrap is refused unless `PLEXA_ALLOW_PRODUCTION_BOOTSTRAP=true` is set explicitly

## Authentication

The server now supports modular request authentication selected by `PLEXA_AUTH_MODE`.

Current modes:
- `dev-header`
- `bearer-jwt`

`dev-header`:
- local development only
- authenticates requests from `X-User-Id`

`bearer-jwt`:
- validates `Authorization: Bearer ...`
- verifies JWT signature and registered claims
- supports:
  - `HS256`
  - `RS256`
- can load verification material from:
  - shared secret
  - PEM public key
  - JWKS JSON/file/URL

Admin access is no longer based on a shared admin token. Plexa admin users are mapped through:
- `PLEXA_ADMIN_USER_IDS`

Useful bearer-JWT settings:
- `PLEXA_AUTH_ISSUER`
- `PLEXA_AUTH_AUDIENCE`
- `PLEXA_AUTH_USER_ID_CLAIM`
- `PLEXA_AUTH_ROLES_CLAIM`
- `PLEXA_AUTH_ALLOWED_ALGORITHMS`
- `PLEXA_AUTH_SHARED_SECRET`
- `PLEXA_AUTH_PUBLIC_KEY_PEM`
- `PLEXA_AUTH_PUBLIC_KEY_FILE`
- `PLEXA_AUTH_JWKS_JSON`
- `PLEXA_AUTH_JWKS_FILE`
- `PLEXA_AUTH_JWKS_URL`

At this point:
- PostgreSQL is the primary backend
- filesystem storage remains available for legacy compatibility and comparative testing

## Running Tests

The test suite is backend-aware.

The default backend selector is read from:
1. an exported environment variable
2. `plexa_server/.env`
3. the hard default `filesystem`

Set the backend in `.env`:

```env
PLEXA_TEST_STORAGE_BACKEND=filesystem
```

Supported values:
- `filesystem`
- `postgres`
- `both`

Run the full suite:

```bash
python3 -m pytest -q plexa_server/tests
```

Run backend-agnostic suites against both backends:

```bash
python3 -m pytest -q plexa_server/tests --storage-backend=both
```

Run only the Postgres-specific DB tests:

```bash
python3 -m pytest -q plexa_server/tests/storage/test_db_postgres_storage.py
```

Run only the API suite against Postgres:

```bash
python3 -m pytest -q plexa_server/tests/api --storage-backend=postgres
```

The backend-aware test wiring is centralized in [tests/conftest.py](tests/conftest.py).

## Running the API

The FastAPI app is constructed in [api/app.py](api/app.py).

You can interact with it over the terminal using `curl` once the server is running. Example:

```bash
curl http://127.0.0.1:8000/api/health
```

## Current Development Posture

The current intended development path is:
- PostgreSQL as the primary persistence layer
- Alembic migrations for schema changes
- `asyncpg` as the async driver under SQLAlchemy
- mostly full async runtime semantics
- filesystem storage retained only where it still provides value for testing or migration support
