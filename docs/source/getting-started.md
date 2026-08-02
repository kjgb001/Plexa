# Getting started

The normal development setup runs PostgreSQL in Docker and runs the server and
portal on the host. This keeps feedback fast while exercising the same database
and API boundaries used in production.

## Requirements

- Python 3.12 or 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 and npm
- Docker Engine with the Compose plugin
- An OpenAI-compatible inference service for real model responses

## Start the development environment

From the repository root:

```bash
uv sync --frozen
docker compose -f plexa_server/docker-compose.yml up -d
uv run python -m plexa_server.bootstrap --init-dev --init-test
uv run python -m plexa_server.utils.seed_dev_data --target dev
```

Start the server:

```bash
uv run python -m plexa_server.api.main
```

In another terminal, prepare and start the portal:

```bash
cp -n plexa_portal/src/.env.example plexa_portal/src/.env
npm --prefix plexa_portal ci
npm --prefix plexa_portal run dev
```

Open <http://localhost:5173>. The maintained seed data includes `tester` for
the student portal, `instructor` for the instructor portal, and `admin` as the
default local administrator.

```{tip}
Check <http://localhost:8000/api/ready> before debugging the portal. The
response separates storage readiness from inference readiness.
```

## Choose the next guide

- Use [Operations](operations.md) to exercise the production stack or deploy a
  domain-backed instance.
- Use [Server internals](server/index.md) before changing runtime behavior.
- Use [Portal internals](client/index.md) before changing student or instructor
  flows.
- Use the [repository README](https://github.com/kjgb001/Plexa) for the
  complete test and repository command reference.
