# ADR-0007: Single-worker initial production topology

**Status:** Accepted constraint

## Context

Active-session locks, stream ownership, per-user inference limits, rate limits,
and disabled-logging transcripts are process-local. Multiple web workers or
replicas could therefore accept conflicting turns or route a request away from
the only process holding ephemeral transcript state.

## Decision

The supported initial production topology runs exactly one Plexa web worker.
Inference may scale independently or run on another host, but the web service
must not add workers or replicas yet.

Before horizontal web scaling, active-session coordination, stream ownership,
concurrency and rate limits, and cleanup leases must move to shared
infrastructure with atomic operations and explicit failure recovery. Disabled
transcript persistence must remain disabled; a future design must use either
encrypted expiring shared ephemeral state or explicit no-resume behavior.

## Consequences

- Operators scale the web application vertically and scale inference
  separately for the initial release.
- Deployment examples, health checks, and support guidance assume one worker.
- Enabling replicas is an architecture change that requires a superseding ADR,
  migration design, and integration tests rather than a deployment-only edit.
