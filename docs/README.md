# Plexa Documentation

The documentation site combines authored guides, Python autodoc output,
TypeDoc Markdown, and a generated OpenAPI schema. Generated sources and HTML are
ignored by Git; update the authored guides or source-code comments instead.

## Build Locally

The first build installs the exact portal dependencies from the lockfile:

```bash
docs/build_docs.sh --install
```

Later builds can reuse the installed portal dependencies:

```bash
docs/build_docs.sh
```

Open `docs/build/html/index.html` in a browser. The script can be called from
any directory and always performs a clean build with Sphinx warnings treated as
errors.

Before a release, also check external links:

```bash
docs/build_docs.sh --linkcheck
```

External link checking requires network access and is not part of pull-request
CI because upstream sites can fail independently of Plexa.

## Source Layout

| Path | Purpose |
| --- | --- |
| `source/*.md` | Authored overview, architecture, operations, and HTTP guides |
| `source/decisions/` | Architecture decision records for durable design rationale |
| `source/server/` | Server overview and generated Python reference entry point |
| `source/client/` | Portal overview and generated TypeScript reference entry point |
| `source/_static/` | Small Furo theme adjustments |
| `source/generated/` | Ignored output recreated by the build script |
| `generate_openapi.py` | Isolated production-oriented OpenAPI generator |
| `prepare_server_docs.py` | Python reference title and navigation cleanup |
| `prepare_typedoc.py` | TypeDoc validation and Sphinx integration cleanup |

The portal reference is intentionally limited by
`plexa_portal/src/documentation.ts`. Export only stable development contracts
from that file. React screens and application wiring should remain internal.

The Python reference excludes tests, migrations, process startup, database
implementation details, and development seed internals. Adjust the exclusions
in `build_docs.sh` when package responsibilities change.

## Publishing

Pull requests run a strict documentation build. Pushes to `main` build the same
site and deploy it through the protected `github-pages` environment.

One repository setting is required: open **Settings > Pages**, then set
**Build and deployment > Source** to **GitHub Actions**. The maintenance guide
documents the environment and branch-protection settings.
