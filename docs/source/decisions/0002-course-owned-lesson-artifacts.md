# ADR-0002: Course-owned lesson artifacts and session snapshots

**Status:** Accepted

## Context

Treating every lesson version as immutable made routine instructor edits and
student-data continuity unnecessarily complex. At the same time, changing an
artifact underneath an active student session would make behavior and retained
records difficult to explain.

## Decision

Lesson artifacts are owned by a course. Only the course owner may read private
authoring data, create or update artifacts, and bind them to the course;
delegated instructors do not inherit authoring access.

An artifact may be updated without changing its author-facing lesson version.
Writes use a monotonically increasing artifact revision and optimistic
concurrency. Every new session freezes the validated lesson document, artifact
revision, content digest, and resolved inference configuration. Existing
sessions continue using their snapshot after the artifact changes.

## Consequences

- A lesson version is a human-facing identity, not an immutable content hash.
- Editors must reload after a revision conflict rather than overwriting newer
  work.
- Reproducibility for a student session comes from its frozen snapshot and
  revision, while later sessions intentionally receive the latest artifact.
