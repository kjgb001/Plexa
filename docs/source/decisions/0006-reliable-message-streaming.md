# ADR-0006: Reliable message streaming

**Status:** Accepted

## Context

Streaming improves the student experience, but a dropped connection can leave
the browser uncertain whether a turn was committed. Retrying without an
idempotency boundary can duplicate user messages or consume an extra lesson
turn.

## Decision

The server streams provisional assistant text as server-sent `delta` events.
It commits the user and assistant messages once generation succeeds, then emits
a `complete` event containing the canonical message and session state.

Every turn has a stable client message ID. The non-streaming endpoint remains a
fallback and returns the existing canonical result when that ID was already
committed. Streaming errors explicitly state whether fallback is safe; partial
output is never treated as the canonical stored response.

## Consequences

- The portal may render deltas smoothly but must replace them with the complete
  event's canonical result.
- Retries must preserve the original message ID and content.
- Stream ownership is currently process-local and therefore contributes to the
  single-worker production constraint.
