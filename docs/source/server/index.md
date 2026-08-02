# Server internals

`plexa_server` is a FastAPI application that owns lesson execution, session
state, authorization, persistence, encrypted logs, and inference routing.

## Package map

| Package | Responsibility |
| --- | --- |
| `api` | Application assembly, routes, request/response schemas, and OpenAPI metadata |
| `auth` | Development-header and bearer-JWT identity verification |
| `core` | Lesson validation, sessions, reflections, policy, rate limits, and logs |
| `inference` | Backend contracts, OpenAI-compatible transport, and profile routing |
| `models` | Course, lesson, session, message, workspace, and log data models |
| `storage` | PostgreSQL runtime storage and deprecated filesystem migration readers |
| `db` | SQLAlchemy configuration, models, sessions, and bootstrap helpers |
| `utils` | Retention, key rotation, import, locking, and operational commands |

## Design rules

- Route handlers authenticate and authorize before loading user-scoped data.
- `SessionManager` is the authoritative state machine for turns, reflections,
  completion, and idempotent message commits.
- PostgreSQL is the only automatic runtime backend. Filesystem storage is kept
  only as a deprecated `0.1.x` migration reader and is removed in `0.2.0`.
- Inference profiles resolve server-side; model names and credentials are not
  accepted from portal requests.
- Lessons with logging disabled must not persist transcript content.

See the [server README](https://github.com/kjgb001/Plexa/blob/main/plexa_server/README.md)
for environment variables, migrations, seeding, and test commands.

## Python reference

The reference below is regenerated from public modules and docstrings. Tests,
migrations, process startup, and development seed internals are excluded.

```{toctree}
:maxdepth: 2

../generated/server_api/plexa_server
```
