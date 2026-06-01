# Plexa Portal

`plexa_portal` is the web frontend for Plexa.

It now contains two parallel application surfaces built on the same frontend platform:
- the student portal
- the instructor portal

This package is a React + TypeScript + Vite application. It depends on a running Plexa server API and shares the same auth and API foundations across both surfaces.

## Current Scope

The portal currently provides:
- configurable client auth services for development and OIDC
- shared API client modules and DTO mappings
- a student portal for course browsing, lesson browsing, and session chat
- an instructor portal skeleton for:
  - course lookup
  - course overview
  - lesson timeline visibility
  - instructor roster management
  - learner request review
  - encrypted log review
- theme support and shared styling

The instructor side is intentionally a first slice, not a finished portal.

## Package Layout

```text
plexa_portal/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── styles.css
│   ├── api/
│   ├── app/
│   ├── auth/
│   ├── config/
│   ├── instructor/
│   ├── screens/
│   ├── student/
│   ├── theme/
│   └── types/
└── public/
```

### Source Structure

- `src/api/`
  HTTP client code, DTOs, API interfaces, mappers, and provider wiring.

- `src/app/`
  Top-level app composition, route parsing, boot screen, and auth callback handling.

- `src/auth/`
  Authentication context plus development and OIDC auth services.

- `src/student/`
  Student-specific app composition and shell wiring.

- `src/instructor/`
  Instructor-specific shell and screen composition.

- `src/screens/`
  Shared or student-oriented screen-level UI such as login, courses, lessons, and chat.

- `src/theme/`
  Theme context and provider logic.

## Requirements

- Node.js
- npm

`npm` is the expected package manager here because the package already includes `package-lock.json`.

## Install Dependencies

From the `plexa_portal` directory:

```bash
npm install
```

## Development Server

Start the Vite development server:

```bash
npm run dev
```

Build the portal:

```bash
npm run build
```

Preview the production build locally:

```bash
npm run preview
```

Run ESLint:

```bash
npm run lint
```

Generate TypeDoc output:

```bash
npm run docs
```

## Environment Configuration

The portal reads local configuration from [src/.env.example](src/.env.example) and your local `src/.env`.

Common variables:

```env
VITE_APP_ENV=development
VITE_API_BASE_URL=http://localhost:8000
TARGET_API_VERSION=v1
VITE_AUTH_MODE=dev
VITE_ENABLE_DEV_LOGIN=false
```

These are consumed in:
- [src/api/config.ts](src/api/config.ts)
- [src/auth/config.ts](src/auth/config.ts)
- [src/config/validate.ts](src/config/validate.ts)

Important note:
- `VITE_API_BASE_URL` should point at the server base path expected by the portal
- the current code fallback is `http://localhost:8000/api`

## Authentication Model

The portal supports:
- `VITE_AUTH_MODE=dev`
- `VITE_AUTH_MODE=oidc`

Development mode:
- uses the local dev login screen
- stores the active user id in `localStorage`
- sends `X-User-Id`

OIDC mode:
- starts an Authorization Code + PKCE flow
- exchanges the callback code for tokens
- stores the active bearer token locally
- sends `Authorization: Bearer ...`

Production deployments should use OIDC mode.

Temporary production dev login is available only for deployment smoke testing.
Production builds reject `VITE_AUTH_MODE=dev` unless
`VITE_ENABLE_DEV_LOGIN=true` is set explicitly.

## Mode Switching

### Development mode

Typical local portal settings:

```env
VITE_APP_ENV=development
VITE_API_BASE_URL=http://localhost:8000
TARGET_API_VERSION=v1
VITE_AUTH_MODE=dev
VITE_ENABLE_DEV_LOGIN=false
```

### Production-like mode

Typical production-oriented portal settings:

```env
VITE_APP_ENV=production
VITE_API_BASE_URL=/api
TARGET_API_VERSION=v1
VITE_AUTH_MODE=oidc
VITE_ENABLE_DEV_LOGIN=false
VITE_AUTH_AUTHORITY=https://idp.example.com
VITE_AUTH_CLIENT_ID=plexa-portal
VITE_AUTH_SCOPE=openid profile email
VITE_AUTH_REDIRECT_URI=https://portal.example.com/auth/callback
VITE_AUTH_LOGOUT_REDIRECT_URI=https://portal.example.com/login
VITE_AUTH_USER_ID_CLAIM=sub
```

In production mode the portal fails fast on missing required API or auth configuration.

## Routing

Top-level routing is handled in:
- [src/App.tsx](src/App.tsx)
- [src/app/router.ts](src/app/router.ts)

Current route groups:
- `/student/...`
- `/instructor/...`
- `/login`
- `/auth/callback`

Legacy `/app/...` student routes are still parsed as aliases during transition.

## Styling And Theme

Global styles live in [src/styles.css](src/styles.css).

The portal already has:
- light and dark theme variables
- a student shell
- a separate instructor shell
- shared visual tokens and interaction patterns

Theme wiring lives under:
- [src/theme/ThemeProvider.tsx](src/theme/ThemeProvider.tsx)
- [src/theme/ThemeContext.ts](src/theme/ThemeContext.ts)

## Current Development Posture

The student portal is materially more complete than the instructor portal.

Practical summary:
- the shared platform layer is real
- the student side is functional
- the instructor side now has a real web foothold
- the instructor portal still needs additional workflow depth and UI refinement
