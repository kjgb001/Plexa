# Architecture decisions

These records preserve the major technical and product boundaries behind the
current implementation. They describe intent, not just code structure.

Accepted records remain historical documents. If a boundary changes, add a new
record that names the decision it supersedes and update this index.

| Record | Decision | Status |
| --- | --- | --- |
| [ADR-0001](0001-server-authoritative-runtime.md) | Server-authoritative lesson runtime | Accepted |
| [ADR-0002](0002-course-owned-lesson-artifacts.md) | Course-owned mutable lesson artifacts and session snapshots | Accepted |
| [ADR-0003](0003-session-logging-and-privacy.md) | Explicit session logging and privacy modes | Accepted |
| [ADR-0004](0004-institutional-auth-boundary.md) | Institutional authentication and protected authoring data | Accepted |
| [ADR-0005](0005-inference-service-boundary.md) | Server-side OpenAI-compatible inference boundary | Accepted |
| [ADR-0006](0006-reliable-message-streaming.md) | Canonical commits with idempotent streaming fallback | Accepted |
| [ADR-0007](0007-single-worker-production.md) | Single-worker initial production topology | Accepted constraint |
| [ADR-0008](0008-postgresql-only-runtime.md) | PostgreSQL-only runtime and filesystem deprecation | Accepted |

```{toctree}
:hidden:
:maxdepth: 1

0001-server-authoritative-runtime
0002-course-owned-lesson-artifacts
0003-session-logging-and-privacy
0004-institutional-auth-boundary
0005-inference-service-boundary
0006-reliable-message-streaming
0007-single-worker-production
0008-postgresql-only-runtime
```
