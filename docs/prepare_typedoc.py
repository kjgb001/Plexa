"""Prepare TypeDoc Markdown for inclusion in Sphinx."""

from __future__ import annotations

import sys
from pathlib import Path


ORPHAN_FRONT_MATTER = "---\norphan: true\n---\n\n"
STALE_MARKERS = ("plexa_client", "Vite + React", "v0.0.0")
REFERENCE_SECTIONS = frozenset(
    {"Classes", "Interfaces", "Type Aliases", "Variables", "Functions"}
)
OPEN_REFERENCE_SECTIONS = frozenset({"Type Aliases", "Variables", "Functions"})


def _collapse_reference_sections(content: str) -> str:
    """Turn TypeDoc category lists into compact interactive dropdowns."""
    lines = content.splitlines()
    prepared: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        heading = line.removeprefix("## ") if line.startswith("## ") else None
        if heading not in REFERENCE_SECTIONS:
            prepared.append(line)
            index += 1
            continue

        list_start = index + 1
        while list_start < len(lines) and not lines[list_start]:
            list_start += 1
        if list_start >= len(lines) or not lines[list_start].startswith("- "):
            raise ValueError(f"Expected a generated list below {line!r}")

        list_end = list_start
        while list_end < len(lines) and lines[list_end].startswith("- "):
            list_end += 1

        prepared.extend(
            [
                f":::{{dropdown}} {heading}",
                *([":open:"] if heading in OPEN_REFERENCE_SECTIONS else []),
                ":animate: fade-in-slide-down",
                ":class-container: api-reference-menu",
                "",
                *lines[list_start:list_end],
                ":::",
            ]
        )
        index = list_end

    return "\n".join(prepared) + "\n"


def main() -> None:
    """Validate and prepare generated TypeDoc pages for Sphinx."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prepare_typedoc.py <typedoc-output-directory>")

    output_dir = Path(sys.argv[1]).resolve()
    root_readme = output_dir / "README.md"
    if not root_readme.is_file():
        raise SystemExit(f"TypeDoc did not generate {root_readme}")

    module_readme = output_dir / "portal-api" / "README.md"
    if not module_readme.is_file():
        raise SystemExit(f"TypeDoc did not generate {module_readme}")

    for path in sorted(output_dir.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        if any(marker in content for marker in STALE_MARKERS):
            raise SystemExit(f"Stale TypeDoc marker found in {path}")
        if path == module_readme:
            content = _collapse_reference_sections(content)
        if not content.startswith(ORPHAN_FRONT_MATTER):
            content = ORPHAN_FRONT_MATTER + content
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
