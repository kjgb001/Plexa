# ADR-0001: Server-authoritative lesson runtime

**Status:** Accepted

## Context

A general chat interface cannot reliably enforce lesson limits, reflection
requirements, completion state, or authorization through prompting alone.
Model output is probabilistic and the browser is controlled by the user.

## Decision

The FastAPI server is authoritative for lesson execution and session state.
It validates lesson documents, resolves the authenticated identity, checks
course access, counts turns, triggers reflection hooks, controls completion and
turn-in, and commits canonical messages.

System prompts guide model behavior but do not replace runtime policy. The
portal renders server state and may optimistically display provisional output,
but it cannot authorize or finalize a state transition by itself.

## Consequences

- Student and instructor clients receive role-appropriate projections rather
  than raw storage objects.
- Reflection, completion, and turn-limit behavior must be tested at the server
  boundary even when the portal also prevents invalid actions.
- New lesson constraints belong in the validated lesson model and session state
  machine, not only in prompt text or client controls.
