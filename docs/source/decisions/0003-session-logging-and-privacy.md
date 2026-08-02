# ADR-0003: Session logging and privacy modes

**Status:** Accepted

## Context

Institutions need explicit control over whether student conversation content is
retained. System prompts require stronger protection than reflection prompts or
the initial assistant message, which students encounter during normal use.

## Decision

Each lesson selects one of three logging policies:

- `default` stores an encrypted instructor log containing the student-visible
  transcript and reflection responses.
- `metadata_only` retains lifecycle metadata without transcript or reflection
  content.
- `disabled` persists no transcript content. The active transcript exists only
  in process memory, is not written to session storage or encrypted logs, and
  cannot resume after a server restart.

System prompts remain in private lesson artifacts and session snapshots. They
are prepended to inference requests on the server and are excluded from student
API projections and encrypted transcript payloads. Retained log access is
course-authorized, encrypted at rest, audited, and subject to a positive
retention period in production.

## Consequences

- Disabled logging is a functional no-resume mode, not merely a hidden log.
- Features must not reconstruct or persist disabled transcripts through a new
  cache, analytics path, or background job.
- Content expiration may preserve non-content metadata while making the former
  transcript unavailable.
