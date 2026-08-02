# Plexa

[![CI](https://github.com/kjgb001/Plexa/actions/workflows/ci.yml/badge.svg)](https://github.com/kjgb001/Plexa/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-read-2f6f59?logo=readthedocs&logoColor=white)](https://kjgb001.github.io/Plexa/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2f6f59)](LICENSE)
[![Python 3.12 | 3.13](https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![PostgreSQL 17](https://img.shields.io/badge/postgresql-17-4169E1?logo=postgresql&logoColor=white)](deploy/README.md)
[![Citation: CFF](https://img.shields.io/badge/citation-CFF-2f6f59?logo=googlescholar&logoColor=white)](CITATION.cff)

Plexa is an open-source platform for instructor-authored, AI-supported lessons
in higher education. Instructors define the goal, model behavior, turn limits,
reflection points, and completion rules; students work through that lesson in
a focused conversation.

> Plexa is a framework for guided AI interaction.

Plexa is designed to sit between an institution and an OpenAI-compatible
inference service. It keeps lesson authoring, policy enforcement, model access,
and student-facing interaction in separate parts of the system.

## What Plexa Provides

- A student portal for courses, lessons, streaming conversations, reflections,
  and work submission.
- An instructor portal for course setup, lesson authoring, timelines, rosters,
  analytics, and submitted-session review.
- A FastAPI runtime that enforces lesson constraints and session state instead
  of relying on prompts alone.
- PostgreSQL persistence with Alembic migrations, encrypted retained logs, and
  configurable content retention.
- Development-header authentication for local work and OIDC/JWT authentication
  for institutional deployments.
- OpenAI-compatible inference routing, including local Ollama or vLLM and
  separately hosted inference services.

Plexa is not intended to be a general-purpose chatbot, prompt playground,
grading system, or replacement for instructors.

## Architecture

```text
Browser
  |
  +-- / --------> React portal
  +-- /api/* ---> FastAPI server ---> PostgreSQL
                         |
                         +----------> OpenAI-compatible inference
```

The production stack uses Caddy to serve the portal, reverse-proxy `/api`, and
manage HTTPS. The server owns authorization and never exposes lesson system
prompts through student APIs.

> [!IMPORTANT]
> The supported production topology currently uses one Plexa web worker.
> Session coordination, stream ownership, concurrency limits, and disabled-log
> transcript state are process-local. Do not add workers or replicas until
> those responsibilities have shared, atomic coordination.

## Quick Start

The local development setup uses PostgreSQL in Docker while the server and
portal run on the host.

### Requirements

- Python 3.12 or 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 and npm
- Docker with the Compose plugin
- An OpenAI-compatible inference endpoint for real conversations

From the repository root, install the Python environment and initialize the
databases:

```bash
uv sync --frozen
docker compose -f plexa_server/docker-compose.yml up -d
uv run python -m plexa_server.bootstrap --init-dev --init-test
uv run python -m plexa_server.utils.seed_dev_data --target dev
```

The bootstrap command creates `plexa_server/.env` when needed. Its inference
profiles are examples for local Ollama and vLLM endpoints; edit them to match
the models and services available on your machine.

Start the API:

```bash
uv run python -m plexa_server.api.main
```

In another terminal, start the portal:

```bash
cd plexa_portal
cp -n src/.env.example src/.env
npm ci
npm run dev
```

Open <http://localhost:5173>. The seeded data includes `tester` as a student and
`instructor` as a course owner. `admin` is the default local global admin.

> [!TIP]
> Use `GET http://localhost:8000/api/ready` to check storage and inference
> readiness. If inference is unavailable, review the generated
> `PLEXA_INFERENCE_BACKENDS`, `PLEXA_INFERENCE_PROFILES`, and
> `PLEXA_INFERENCE_REQUIRED_BACKENDS` values in `plexa_server/.env`.

For component-specific setup and configuration, see the
[server guide](plexa_server/README.md) and [portal guide](plexa_portal/README.md).

## Testing

Run the server suite against both storage implementations:

```bash
uv run --frozen pytest -q plexa_server/tests --storage-backend=both
```

Check the portal:

```bash
npm --prefix plexa_portal run lint
npm --prefix plexa_portal run build
```

The repository maintenance runner combines these checks with lockfile, CI
policy, migration, and disposable-PostgreSQL validation:

```bash
maintenance/run-ci-local.sh --quick
maintenance/run-ci-local.sh
```

The full runner downloads dependencies and a PostgreSQL image. See the
[maintenance guide](maintenance/README.md) before using it.

## Deployment

Plexa ships with a Docker Compose and Caddy deployment for either:

- a local production-mode smoke test at `http://localhost:8080`; or
- a domain-backed installation such as `https://plexa.example.edu`.

Start with the [production deployment guide](deploy/README.md). It covers DNS,
OIDC registration, inference connectivity, generated secrets, validation,
backups, restoration, and upgrades.

## Repository Guide

| Path | Purpose |
| --- | --- |
| [`plexa_server/`](plexa_server/) | FastAPI application, lesson runtime, storage, auth, migrations, and tests |
| [`plexa_portal/`](plexa_portal/) | React student and instructor portal |
| [`deploy/`](deploy/) | Production configuration, deployment, checks, backup, and restore tooling |
| [`maintenance/`](maintenance/) | Local CI, dependency, and repository-security maintenance tooling |
| [`docs/`](docs/) | Authored guides and reproducible API-documentation tooling |

The files under `docs/source/generated/` are ignored build products. Update
their source code or documentation comments, then use the
[documentation build](docs/README.md) instead of editing generated pages.
