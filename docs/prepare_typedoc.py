"""Prepare TypeDoc Markdown for inclusion in Sphinx."""

from __future__ import annotations

import sys
from pathlib import Path


ORPHAN_FRONT_MATTER = "---\norphan: true\n---\n\n"
STALE_MARKERS = ("plexa_client", "Vite + React", "v0.0.0")


def main() -> None:
    """Mark linked TypeDoc children as intentional Sphinx orphans."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prepare_typedoc.py <typedoc-output-directory>")

    output_dir = Path(sys.argv[1]).resolve()
    root_readme = output_dir / "README.md"
    if not root_readme.is_file():
        raise SystemExit(f"TypeDoc did not generate {root_readme}")

    for path in sorted(output_dir.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        if any(marker in content for marker in STALE_MARKERS):
            raise SystemExit(f"Stale TypeDoc marker found in {path}")
        if path != root_readme and not content.startswith(ORPHAN_FRONT_MATTER):
            path.write_text(ORPHAN_FRONT_MATTER + content, encoding="utf-8")


if __name__ == "__main__":
    main()
