# Architecture

Plexa separates lesson policy, conversational state, user interfaces, and model
inference. The server is authoritative for identity, authorization, lesson
constraints, reflection state, and session completion.

```text
Browser
  |
  +-- / --------> React portal
  +-- /api/* ---> Caddy or development proxy
                         |
                         v
                    FastAPI server
                      |       |
                      |       +----> OpenAI-compatible inference
                      v
                  PostgreSQL
```

## Request flow

1. The portal obtains either a development identity or an institutional OIDC
   access token.
2. The server authenticates the request and derives the authoritative user and
   roles.
3. Course and session authorization is checked before storage is accessed.
4. The session manager applies lesson constraints and reflection gates before
   inference is requested.
5. Assistant output is streamed when available, then committed as one canonical
   result. The same client message ID can be retried through the fallback path.

## Data boundaries

PostgreSQL is the production storage backend. Filesystem storage remains useful
for tests and local tooling, and both implementations follow the same storage
interfaces.

Session transcripts are not student-facing server archives. Lessons with
logging disabled persist no transcript content. When logging is enabled,
retained instructor logs are encrypted and access-controlled separately from
active session state.

## Deployment boundary

The initial production release intentionally uses one web worker. Process-local
stream ownership, active-session coordination, rate limits, and disabled-log
state make multiple workers unsafe until shared atomic coordination exists.

Inference may run on the application host, institutional compute, or a separate
GPU service. Only the server receives inference credentials and model routing
configuration; the browser communicates exclusively with Plexa's API.
