# HTTP API

The portal and external tooling use the Plexa server through `/api`. Most
application routes are versioned under `/api/v1`; health probes remain
unversioned.

## Authentication

Plexa supports one server authentication mode at a time.

`dev-header`
: Trusts the configured user ID header, `X-User-Id` by default. This mode is for
  local development and temporary production validation only.

`bearer-jwt`
: Verifies an institution-issued access token supplied as
  `Authorization: Bearer <token>`. Production validates the configured issuer,
  audience, signature algorithm, and key source.

The server derives administrator and instructor permissions from the verified
identity. Supplying another user's resource identifier never grants access.

## Responses and request IDs

Errors use an HTTP status and a JSON `detail` field. Common statuses include:

| Status | Meaning |
| --- | --- |
| `401` | Identity is missing or invalid |
| `403` | The identity is valid but lacks a required global role |
| `404` | The resource does not exist or is intentionally hidden from this user |
| `409` | The request conflicts with session state or an optimistic revision |
| `413` | The request body exceeds the 1 MiB limit |

Every response includes `X-Request-Id`. Clients may provide the same header to
correlate portal, proxy, and server logs.

## Streaming messages

The streaming message endpoint uses server-sent events with `delta`, `complete`,
and `error` events. Deltas are provisional; the `complete` event contains the
canonical committed assistant message and session state.

Clients must assign a stable message ID. If streaming fails before a canonical
completion, the portal can retry that ID through the non-streaming endpoint
when the error marks fallback as safe. This prevents duplicate user turns.

## Health and interactive reference

- `GET /api/health` reports process liveness.
- `GET /api/ready` reports storage and inference readiness.
- `/docs` on a running server provides FastAPI's interactive Swagger UI.
- {download}`Download the generated OpenAPI schema
  <generated/openapi/openapi.json>` for code generation or offline inspection.

The static schema is generated in production-oriented bearer-JWT mode. A
development server's runtime schema instead advertises its configured user
header.
