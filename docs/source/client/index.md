# Portal internals

`plexa_portal` is one React application with separate student and instructor
surfaces. Both use the same server-authoritative identity, API transport, domain
models, and runtime configuration.

## Structure

| Area | Responsibility |
| --- | --- |
| `api` | Authenticated HTTP transport, DTO mapping, streaming, and domain clients |
| `auth` | Development login, OIDC lifecycle, and server identity resolution |
| `app` | Portal selection, shared boot flow, and top-level routing |
| `student` and `screens` | Course, lesson, session, reflection, and turn-in experience |
| `instructor` | Course management, authoring, timelines, rosters, and log review |
| `state` | Current course, lesson, and session navigation state |
| `theme` | Shared light and dark appearance controls |

## Data flow

API DTOs mirror wire-format names. Mappers convert them into portal domain
interfaces before screens consume them. Session streaming emits provisional
text, then replaces it with the canonical committed result from the server.

Authentication services expose one shared contract. Development mode emits the
temporary identity header; institutional mode obtains an OIDC access token and
uses bearer authentication. The server's `/auth/me` response remains
authoritative for roles and instructor access.

See the [portal README](https://github.com/kjgb001/Plexa/blob/main/plexa_portal/README.md)
for environment configuration, linting, builds, and local startup.

## TypeScript reference

The generated reference intentionally covers transport clients, authentication
contracts, domain models, and lesson-authoring helpers. React screens and
application wiring are implementation details rather than a reusable API.

```{toctree}
:maxdepth: 2

../generated/client_api/README
```
