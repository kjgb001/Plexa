# ADR-0004: Institutional authentication boundary

**Status:** Accepted

## Context

Plexa must support institution-managed identity without trusting user IDs or
roles supplied by the browser. Development still needs a low-friction login
while institutional integration is configured and tested.

## Decision

Production uses institution-issued bearer JWTs obtained through the portal's
OIDC flow. The server validates issuer, audience, signature, algorithm, and
claims, then returns the authoritative identity and portal capabilities from
`/auth/me`.

The development identity header remains available only for local development
and temporary deployment validation. Authorization is checked on every request:
global administrators, course owners, delegated instructors, and enrolled
students have distinct capabilities. Removing a student from a course revokes
access to existing course sessions.

Student-facing course and lesson projections omit rosters, ownership metadata,
constraints, inference configuration, and system prompts. Private resources
use not-found responses where revealing their existence would cross an access
boundary.

## Consequences

- Institutions must provide a stable subject identifier and correctly scoped
  OIDC registration.
- Client-side route guards are usability controls, not authorization controls.
- Development-header mode must not remain enabled on a student-facing
  production installation.
