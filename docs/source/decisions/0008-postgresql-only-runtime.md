# ADR-0008: PostgreSQL-only runtime and filesystem deprecation

**Status:** Accepted

## Context

Plexa originally kept filesystem and PostgreSQL implementations behind the same
storage interfaces. The filesystem backend was useful during early development,
but maintaining runtime parity doubled persistence testing and left behavior
that production deployments did not use. Its path-based records also lack the
relational integrity, migration controls, and operational tooling expected for
institutional student data.

The project has not reached its initial public release, so retaining automatic
filesystem fallback would create a compatibility promise without a practical
deployment benefit.

## Decision

PostgreSQL is the only supported automatic runtime backend. Application startup
fails clearly when database configuration is absent. Tests may inject all four
storage dependencies as a unit, but partial injection is rejected and injection
is not a supported storage-plugin API.

Filesystem storage is deprecated for all runtime and seeding use. During the
`0.1.x` series it remains as a read-only source for a one-way PostgreSQL importer
and as focused compatibility-test code. The importer:

- requires an empty target at the current Alembic head;
- validates the entire source before its first write;
- migrates courses, lessons, sessions, inference configs, encrypted logs,
  access audits, and workspace state;
- copies encrypted bytes and key identifiers without decrypting them;
- preserves user-visible state and timestamps while resetting optimistic
  revision counters; and
- verifies records and encrypted hashes after import.

Filesystem storage, its importer, and its focused compatibility tests are
scheduled for removal in `0.2.0`.

## Consequences

- Production, development, and the main server test suite share one persistence
  model and one set of relational invariants.
- A missing database can no longer cause an unnoticed change in persistence.
- Existing filesystem users have a bounded, documented migration window and
  must retain legacy encryption keys for imported logs.
- The import does not merge data. An unforeseen failure after writes begin may
  require resetting the target and rerunning from the unchanged source backup.
- CodeQL findings in the deprecated filesystem module remain visible through
  removal; accepted false positives are reviewed and dismissed individually
  rather than excluding the module from analysis.
