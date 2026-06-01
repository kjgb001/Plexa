# Plexa

**Plexa** is a lesson-centric AI orchestration system for higher education.

It is not a chatbot, and it is not a general-purpose AI wrapper. Plexa is a **pedagogical runtime**: a system for executing structured lessons with AI under explicit constraints, session controls, and instructor intent.

The core idea is simple:

> **Students do not just chat with an AI.**  
> **They execute a lesson.**

Everything in Plexa follows from that premise.

## What Plexa Is

- A lesson execution engine
- A policy and constraint enforcement layer
- A bridge between instructor intent and model behavior
- A structured session runtime for educational AI workflows
- A system designed to keep inference, storage, and application concerns separated

## What Plexa Is Not

- A generic chat app
- A prompt playground
- A grading or surveillance system
- A replacement for instructors
- A thin wrapper around whatever model API is fashionable this month

## Repository Structure

This repository is a development monorepo with multiple packages:

```text
plexa/
├── README.md
├── pyproject.toml
├── conftest.py
├── docs/
├── plexa_server/
└── plexa_portal/
```

### Package Overview

- [plexa_server/README.md](plexa_server/README.md)
  The main implemented backend package. It contains the FastAPI server, lesson/session runtime, storage abstractions, PostgreSQL integration, Alembic migrations, bootstrap tooling, and the backend-aware test suite.

- [plexa_portal/README.md](plexa_portal/README.md)
  The shared web portal package for both student and instructor-facing browser workflows.

## Current State Of The Codebase

The server is the most mature part of the repository.

What is implemented in `plexa_server` now:
- lesson, course, session, and message domain models
- FastAPI routes for runtime and admin flows
- storage abstractions with both filesystem and PostgreSQL implementations
- PostgreSQL integration using SQLAlchemy, Alembic, and `asyncpg`
- database bootstrap and legacy filesystem import tooling
- backend-aware pytest support for `filesystem`, `postgres`, and `both`

The server is no longer just a schema experiment or runtime sketch. It has a working persistence layer, migration path, and testable backend selection model.

The portal now has a real student surface and an instructor skeleton, but still needs deeper instructor workflow development.

## Architectural Direction

Plexa is designed around explicit contracts and separation of concerns.

Current architectural principles reflected in the code:
- **Lesson-first runtime**: sessions are created from structured lesson artifacts
- **Backend abstraction**: storage and inference are behind interfaces
- **PostgreSQL as primary persistence**: the server supports full relational persistence
- **Filesystem retained as legacy/test backend**: useful for migration support and comparative testing
- **Mostly async server path**: runtime persistence and request handling are aligned with the async database stack

## Development Workflow

Most active development currently happens in `plexa_server`.

For local server work:
1. create and activate a virtual environment
2. start the Postgres container from `plexa_server/docker-compose.yml`
3. bootstrap the development and test databases
4. run tests through `python -m pytest`

The detailed server workflow is documented in:
- [plexa_server/README.md](plexa_server/README.md)

## Production Deployment

The initial production path targets VPS or institution-owned server deployments
with one public domain:

- the portal is served from `/`
- the API is reverse-proxied under `/api`
- Postgres provides persistence
- inference remains a backend-only endpoint configured on the server

See [deploy/README.md](deploy/README.md) for the Docker Compose and Caddy-based
deployment guide.

## Testing

The repository root has a pytest hook in [conftest.py](conftest.py) that:
- loads `plexa_server/.env`
- registers the `--storage-backend` option early enough for root-level test runs

Supported backend test modes:
- `filesystem`
- `postgres`
- `both`

Typical examples:

```bash
python -m pytest -q plexa_server/tests
python -m pytest -q plexa_server/tests --storage-backend=postgres
python -m pytest -q plexa_server/tests --storage-backend=both
```

## License

Plexa is open-source with a permissive license.

See [LICENSE](LICENSE).
