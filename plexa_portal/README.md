# Plexa Portal

`plexa_portal` is the React and TypeScript frontend shared by Plexa's student
and instructor experiences. It talks to the Plexa API for identity, course
access, lesson state, session execution, and instructor operations.

## Features

Students can:

- browse their courses and available lessons;
- start, resume, complete, and submit lesson sessions;
- receive streamed model responses with a non-streaming fallback;
- answer, postpone, review, and save mid-session and post-session reflections;
- see lesson goals, behavioral focus, constraints, and current session state.

Instructors can:

- manage course lessons and availability timelines;
- author and update course-scoped lesson artifacts;
- manage instructors, enrollment requests, and learner rosters;
- browse logs by lesson or student and review submitted conversations;
- view course and lesson activity summaries.

Both surfaces use the same API client, auth provider, route parser, and visual
system.

## Getting Started

### Requirements

- Node.js 22
- npm
- A running [Plexa server](../plexa_server/README.md)

The lockfile is authoritative, so use npm rather than another package manager.

From this directory:

```bash
cp -n src/.env.example src/.env
npm ci
npm run dev
```

Open <http://localhost:5173>.

The example environment uses development login and expects the API at
`http://localhost:8000/api`. With the seeded dataset, `tester` has student data
and `instructor` owns the example courses.

If an existing ignored `src/.env` still uses `http://localhost:8000`, append
`/api` before starting Vite.

> [!NOTE]
> `VITE_API_BASE_URL` is the unversioned API base, not just the server origin.
> The client appends `TARGET_API_VERSION` to build requests such as
> `http://localhost:8000/api/v1/courses`.

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Vite development server |
| `npm run build` | Type-check and create the production bundle |
| `npm run preview` | Serve the production bundle locally |
| `npm run lint` | Run ESLint |
| `npm run docs` | Regenerate the TypeDoc Markdown under `docs/source/generated/client_api` |

CI installs dependencies with `npm ci --ignore-scripts`, then runs the audit,
lint, and build commands. Do not use `--force` or `--legacy-peer-deps` to hide a
dependency conflict; update peer-coupled packages together instead.

## Configuration

Local values live in the ignored `src/.env` file. Start from
[`src/.env.example`](src/.env.example).

| Variable | Purpose | Development default |
| --- | --- | --- |
| `VITE_APP_ENV` | Enables development or production validation | `development` |
| `VITE_API_BASE_URL` | Unversioned API base | `http://localhost:8000/api` |
| `TARGET_API_VERSION` | API version appended by the HTTP client | `v1` |
| `VITE_AUTH_MODE` | Selects `dev` or `oidc` authentication | `dev` |
| `VITE_ENABLE_DEV_LOGIN` | Explicitly permits dev login in a production build | `false` |
| `VITE_AUTH_AUTHORITY` | OIDC issuer/authority | empty |
| `VITE_AUTH_DISCOVERY_URL` | Optional OIDC discovery override | empty |
| `VITE_AUTH_CLIENT_ID` | Public OIDC client identifier | empty |
| `VITE_AUTH_SCOPE` | Requested OIDC scopes | `openid profile email` |
| `VITE_AUTH_REDIRECT_URI` | Sign-in callback | `<origin>/auth/callback` |
| `VITE_AUTH_LOGOUT_REDIRECT_URI` | Post-logout destination | `<origin>/login` |

Production builds fail fast when required API or authentication values are
missing.

### Authentication

`VITE_AUTH_MODE=dev` shows the local username form, stores the selected user in
the browser, and sends `X-User-Id`. The server still determines roles and course
capabilities through `/api/v1/auth/me`.

`VITE_AUTH_MODE=oidc` uses Authorization Code with PKCE through
`oidc-client-ts`, stores the OIDC session in `sessionStorage`, and sends the
access token as `Authorization: Bearer ...`. The UI does not grant application
permissions from unverified client-side claims.

> [!WARNING]
> Development login trusts a browser-supplied username. Never enable it for a
> student-facing deployment. The temporary production switch exists only for
> private smoke testing.

Use the [deployment guide](../deploy/README.md) to generate a matched portal and
server configuration for OIDC.

## Routing

Plexa uses a small browser-history router in [`src/app/router.ts`](src/app/router.ts).

| Route | Screen |
| --- | --- |
| `/login` | Portal selection and sign-in |
| `/auth/callback` | OIDC callback |
| `/student/courses` | Student course list |
| `/student/courses/:courseId/lessons` | Course lessons |
| `/student/courses/:courseId/lessons/:lessonId/:version` | New or active lesson session |
| `/instructor` | Instructor course list |
| `/instructor/courses/:courseId/:mode` | Course overview, lessons, builder, logs, analytics, or roster |
| `/instructor/courses/:courseId/logs/:sessionId` | Session review |

Legacy `/app/...` student URLs remain accepted as aliases.

## Source Map

```text
src/
├── api/          # HTTP transport, DTOs, mappers, and API services
├── app/          # App composition, routing, and shared shell
├── auth/         # Development and OIDC authentication
├── config/       # Runtime configuration validation
├── instructor/   # Instructor shell, screens, and lesson builder
├── screens/      # Login and student-facing screens
├── student/      # Student app composition
├── theme/        # Theme context and provider
├── App.tsx
├── main.tsx
└── styles.css
```

Global styles and component tokens live in [`src/styles.css`](src/styles.css).
The application supports light and dark themes through `src/theme/`.

## Production Build

The standalone build command writes to `dist/`:

```bash
npm ci
npm run build
```

The repository's production image performs this build in
[`deploy/caddy.Dockerfile`](../deploy/caddy.Dockerfile) and serves the result
through Caddy. Prefer the documented [production stack](../deploy/README.md)
over manually serving `dist/` unless you are integrating Plexa into existing
institutional infrastructure.
