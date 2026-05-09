# Plexa Client

`plexa_client` is the student-facing web client for Plexa.

It is a React + TypeScript + Vite application that provides the browser UI for:
- logging in with the current development auth flow
- browsing courses
- browsing lessons within a course
- creating and resuming lesson sessions
- chatting inside a lesson-scoped session

This README is intentionally scoped to the client package itself. It documents the frontend application, its local development workflow, and its package layout.

## Current Scope

The client is not just a raw Vite scaffold anymore. It already contains:
- route parsing and navigation helpers
- a development auth flow using `localStorage`
- API client modules for courses and sessions
- state modules for course, lesson, and session UI
- a student shell and lesson chat screen
- theme support and shared styling

The client still depends on a running Plexa server API. It does not contain its own backend.

## Package Layout

Key files and directories:

```text
plexa_client/
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
│   ├── screens/
│   ├── state/
│   └── theme/
└── public/
```

### Source Structure

- `src/api/`
  HTTP client code, DTOs, API interfaces, mappers, and provider wiring.

- `src/app/`
  App shell, router, boot screen, and auth callback screen.

- `src/auth/`
  Authentication context and the current development auth service.

- `src/screens/`
  Screen-level UI for login, courses, lessons, and chat.

- `src/state/`
  Client-side state helpers for course, lesson, and session flows.

- `src/theme/`
  Theme context and provider logic.

## Requirements

- Node.js
- npm

This package already contains a `package-lock.json`, so `npm` is the expected package manager here.

## Install Dependencies

From the `plexa_client` directory:

```bash
npm install
```

## Development Server

Start the Vite development server:

```bash
npm run dev
```

Build the client:

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

The client currently reads its local API configuration from [src/.env](/home/kellan/projects/school/plexa/plexa_client/src/.env).

Current variables:

```env
VITE_API_BASE_URL=http://localhost:8000
TARGET_API_VERSION=v1
```

These are consumed in [src/api/config.ts](/home/kellan/projects/school/plexa/plexa_client/src/api/config.ts).

Important note:
- `VITE_API_BASE_URL` should point at the server base path expected by the client
- the fallback in code is `http://localhost:8000/api`

If you change the server host, port, or mounted API prefix, update the client config accordingly.

## Authentication Model

The current client package uses a development auth flow implemented in [src/auth/devAuth.ts](/home/kellan/projects/school/plexa/plexa_client/src/auth/devAuth.ts).

What it does:
- stores the active user id in `localStorage`
- sends that value as `X-User-Id`
- restores the user on refresh if the local storage value exists

This is appropriate for local development. It is not a production identity solution.

## Routing

Top-level routing is handled inside:
- [src/App.tsx](/home/kellan/projects/school/plexa/plexa_client/src/App.tsx)
- [src/app/router.ts](/home/kellan/projects/school/plexa/plexa_client/src/app/router.ts)

Current route flow is centered on:
- login
- course list
- lesson list for a selected course
- lesson chat/session screen

## Styling And Theme

Global styles live in [src/styles.css](/home/kellan/projects/school/plexa/plexa_client/src/styles.css).

The client already has:
- a light and dark theme variable system
- a structured app shell
- screen-level layout styling

Theme wiring lives under:
- [src/theme/ThemeProvider.tsx](/home/kellan/projects/school/plexa/plexa_client/src/theme/ThemeProvider.tsx)
- [src/theme/ThemeContext.ts](/home/kellan/projects/school/plexa/plexa_client/src/theme/ThemeContext.ts)

## Current Development Posture

The client is implemented enough to be a real frontend package, but it is still narrower in maturity than the server.

Practical summary:
- it has real application structure
- it has real API integration code
- it has a real student flow
- it still needs product-level polish and broader documentation over time

That is the current scope of `plexa_client`.
