# Plexa

**Plexa** is a lesson-centric AI orchestration system for higher education.

It is not a chatbot, and it is not a general-purpose AI wrapper. Plexa is a **pedagogical runtime**: a system for executing structured lessons with AI under explicit constraints, logging policies, and instructor intent.

The core idea is simple:

> **Students don’t “chat with an AI.”  
> They execute a lesson.**

Everything in Plexa flows from that premise.

---

## What Plexa Is (and Is Not)

### Plexa *is*:
- A lesson execution engine
- A policy and constraint enforcer
- A bridge between instructor intent and AI behavior
- A privacy-preserving logging system for educational analysis
- A backend-agnostic orchestration layer for AI inference

### Plexa is *not*:
- A generic chat UI
- A prompt playground
- A grading or surveillance tool
- A replacement for instructors
- A SaaS product designed around lock-in

---

## Architectural Philosophy

Plexa is designed around **discipline, separation of concerns, and explicit contracts**.

Key principles:

- **Lesson-first**: all interactions are scoped to a lesson artifact
- **Policy over freedom**: AI behavior is constrained by design, not hope
- **Server blindness**: sensitive data is encrypted at rest and unreadable without instructor authorization
- **Backend abstraction**: inference engines are swappable
- **Local-first development**: stubs enable laptop-only iteration
- **Institution-friendly**: deployable on university infrastructure, auditable, and ethically aligned

---

## Repository Structure (Monorepo)

This repository is a **development monorepo** containing multiple independently deployable packages.

```
plexa/
├── pyproject.toml
├── conftest.py
├── README.md
│
├── plexa_server/ # Lesson runtime & policy engine
├── plexa_client/ # Student-facing UI (web / desktop)
├── plexa_author/ # Instructor lesson authoring tool
```


Each package is designed to be built and distributed independently in production.

---

## Plexa-Server (Core)

The server is the semantic heart of Plexa.

Responsibilities:
- Validate lesson artifacts
- Enforce lesson constraints and policies
- Manage session lifecycle
- Orchestrate AI inference via abstract interfaces
- Encrypt and persist interaction logs
- Remain agnostic to UI and identity providers

The server does **not** render UI and does **not** allow free-form chats outside lesson context.

---

## Lessons as First-Class Artifacts

Lessons are structured JSON artifacts that encode:

- identity and provenance
- pedagogical intent
- execution parameters
- constraints and limits
- reflection and logging policies

They are:
- authored externally
- validated on upload
- immutable during execution
- reusable across courses and terms

The server treats lessons as **authoritative inputs**, not user prompts.  

Plexa-Author can be used to easily create lessons.

---

## Privacy and Ethics

Plexa is designed to minimize institutional risk and maximize student trust.

Key guarantees:
- All session logs are encrypted at rest
- Encryption keys are bound to lesson ownership
- Only the owning instructor(s) can decrypt logs
- The server cannot read student interactions by default
- Logging behavior is explicitly defined per lesson

Plexa operates as infrastructure, not a data custodian.

---

## Development Status

Plexa is under active development as an academic independent study project.

Current focus:
- Server-side lesson schema validation
- Session execution pipeline
- Inference abstraction layer
- Instructor upload and management APIs
- Stub-based development workflow

The architecture is intentionally over-specified early to support long-term stability.

---

## License and Philosophy

Plexa is open-source and community-led by design.

The goal is not to monetize classroom dependency, but to:
- provide institutions with ethical AI tooling
- empower instructors to shape AI use intentionally
- teach students how to engage critically and effectively with AI systems

[License](LICENSE) MIT License

---

## Status

This project is pre-release and evolving rapidly. Interfaces may change.

That said, architectural principles are considered **stable**.

Contributions, discussion, and critique are welcome; especially from educators, researchers, and students thinking seriously about AI in the classroom.
