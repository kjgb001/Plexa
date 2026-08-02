"""Prepare sphinx-apidoc output for the Plexa documentation site."""

from __future__ import annotations

import sys
from pathlib import Path


TITLE_SUFFIXES = (" package", " module")
NAVIGATION_HEADINGS = frozenset({"Subpackages", "Submodules"})


def _normalize_title(lines: list[str]) -> None:
    """Remove redundant generated type suffixes from a document title."""
    if len(lines) < 2 or not lines[1] or set(lines[1]) != {"="}:
        return

    for suffix in TITLE_SUFFIXES:
        if lines[0].endswith(suffix):
            lines[0] = lines[0][: -len(suffix)]
            lines[1] = "=" * len(lines[0])
            return


def _collapse_navigation(
    lines: list[str],
    *,
    open_headings: frozenset[str] = frozenset(),
) -> list[str]:
    """Wrap generated package and module toctrees in collapsed dropdowns."""
    prepared: list[str] = []
    index = 0

    while index < len(lines):
        heading = lines[index]
        is_navigation_heading = (
            heading in NAVIGATION_HEADINGS
            and index + 2 < len(lines)
            and lines[index + 1]
            and set(lines[index + 1]) == {"-"}
        )
        if not is_navigation_heading:
            prepared.append(lines[index])
            index += 1
            continue

        directive_start = index + 2
        while directive_start < len(lines) and not lines[directive_start]:
            directive_start += 1
        if (
            directive_start >= len(lines)
            or lines[directive_start] != ".. toctree::"
        ):
            raise ValueError(f"Expected a toctree below {heading!r}")

        directive_end = directive_start + 1
        while directive_end < len(lines):
            line = lines[directive_end]
            if line and not line.startswith((" ", "\t")):
                break
            directive_end += 1

        prepared.append(f".. dropdown:: {heading}")
        if heading in open_headings:
            prepared.append("   :open:")
        prepared.extend(
            [
                "   :animate: fade-in-slide-down",
                "   :class-container: api-reference-menu",
                "",
            ]
        )
        prepared.extend(
            f"   {line}" if line else ""
            for line in lines[directive_start:directive_end]
        )
        index = directive_end

    return prepared


def main() -> None:
    """Normalize titles and navigation in a sphinx-apidoc output directory."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prepare_server_docs.py <sphinx-apidoc-output-directory>")

    output_dir = Path(sys.argv[1]).resolve()
    root_document = output_dir / "plexa_server.rst"
    if not root_document.is_file():
        raise SystemExit(f"sphinx-apidoc did not generate {root_document}")

    for path in sorted(output_dir.glob("*.rst")):
        lines = path.read_text(encoding="utf-8").splitlines()
        _normalize_title(lines)
        open_headings = (
            frozenset({"Submodules"})
            if path == root_document
            else frozenset()
        )
        lines = _collapse_navigation(lines, open_headings=open_headings)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
