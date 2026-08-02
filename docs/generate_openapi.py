"""Generate Plexa's production-oriented OpenAPI schema without external services."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from plexa_server.api.app import build_app
from plexa_server.inference.stub import StubInference


def main() -> None:
    """Write a deterministic bearer-auth OpenAPI document to the requested path."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: generate_openapi.py <output-path>")

    output_path = Path(sys.argv[1]).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Existing environment values win over plexa_server/.env during app assembly.
    os.environ.update(
        {
            "PLEXA_AUTH_AUTHORIZATION_HEADER_NAME": "Authorization",
            "PLEXA_AUTH_MODE": "bearer-jwt",
            "PLEXA_AUTH_SHARED_SECRET": "documentation-build-only",
            "PLEXA_ENV": "development",
        }
    )

    with TemporaryDirectory(prefix="plexa-openapi-") as data_dir:
        schema = build_app(
            inference_backend=StubInference(),
            data_dir=Path(data_dir),
        ).openapi()

    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
