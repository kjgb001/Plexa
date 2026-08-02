# ADR-0005: Inference service boundary

**Status:** Accepted

## Context

Institutions may have on-premises accelerators, a separate GPU host, or no local
inference capacity. Browser access to model credentials or arbitrary backend
selection would weaken deployment control and make lessons less reproducible.

## Decision

Plexa integrates with inference through server-configured OpenAI-compatible
backends and named profiles. Lessons reference a profile; the server resolves
the model, endpoint, credentials, parameters, timeout, and required readiness
checks. The browser communicates only with Plexa's `/api` surface.

The inference service may run on the application host, institutional compute,
or a separately secured VPS. This deployment separation does not move identity,
lesson policy, or student session authority out of the Plexa server.

## Consequences

- Model credentials and backend inventory never belong in portal bundles or
  student requests.
- Operators can change infrastructure behind a stable profile while lesson
  authors work with an institution-approved abstraction.
- Readiness distinguishes storage health from required inference availability.
