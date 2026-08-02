#!/usr/bin/env python3
"""Classify changed repository paths into CI work categories."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

OUTPUT_NAMES = (
    "portal",
    "server",
    "deployment",
    "docs",
    "codeql_python",
    "codeql_javascript",
    "full",
)
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
JAVASCRIPT_SUFFIXES = {".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
PROSE_SUFFIXES = {".cff", ".md", ".rst"}
PROSE_NAMES = {
    "citation.cff",
    "code_of_conduct",
    "code_of_conduct.md",
    "contributing",
    "contributing.md",
    "license",
    "license.md",
    "notice",
    "notice.md",
    "readme",
    "readme.md",
    "security",
    "security.md",
}
SERVER_ROOT_INPUTS = {"conftest.py", "pyproject.toml", "requirements.lock", "uv.lock"}
DEPLOYMENT_ROOT_INPUTS = {".dockerignore", "docker-compose.prod.yml"}
SERVER_DEPLOYMENT_NAMES = {".env.production.example", "docker-compose.yml", "dockerfile"}


@dataclass
class Selection:
    portal: bool = False
    server: bool = False
    deployment: bool = False
    docs: bool = False
    codeql_python: bool = False
    codeql_javascript: bool = False
    full: bool = False

    @classmethod
    def all(cls) -> "Selection":
        return cls(**{name: True for name in OUTPUT_NAMES})

    def merge(self, other: "Selection") -> None:
        for name in OUTPUT_NAMES:
            setattr(self, name, getattr(self, name) or getattr(other, name))

    def github_outputs(self) -> str:
        return "".join(
            f"{name}={'true' if value else 'false'}\n"
            for name, value in asdict(self).items()
        )


def _is_prose(path: PurePosixPath) -> bool:
    return path.name.lower() in PROSE_NAMES or path.suffix.lower() in PROSE_SUFFIXES


def _classify_path(raw_path: str) -> Selection:
    normalized = raw_path.replace("\\", "/").removeprefix("./")
    path = PurePosixPath(normalized)
    if not normalized or normalized.startswith("/") or ".." in path.parts:
        return Selection.all()

    parts = path.parts
    top = parts[0]
    name = path.name.lower()
    suffix = path.suffix.lower()

    if top == "docs":
        return Selection(
            docs=True,
            codeql_python=suffix == ".py",
            codeql_javascript=suffix in JAVASCRIPT_SUFFIXES,
        )

    if _is_prose(path):
        return Selection()

    if top == ".github" or top == "maintenance":
        return Selection.all()

    language = Selection(
        codeql_python=suffix == ".py",
        codeql_javascript=suffix in JAVASCRIPT_SUFFIXES,
    )

    if top == "plexa_portal":
        language.portal = True
        language.docs = True
        return language

    if top == "plexa_server":
        language.server = True
        language.docs = True
        if name in SERVER_DEPLOYMENT_NAMES:
            language.deployment = True
        return language

    if top == "deploy":
        language.deployment = True
        return language

    if normalized in SERVER_ROOT_INPUTS:
        return Selection(server=True, deployment=True, docs=True, codeql_python=suffix == ".py")

    if normalized in DEPLOYMENT_ROOT_INPUTS:
        return Selection(deployment=True)

    return Selection.all()


def classify_paths(paths: Iterable[str]) -> Selection:
    selection = Selection()
    for path in paths:
        selection.merge(_classify_path(path))
    if selection.full:
        return Selection.all()
    return selection


def changed_paths(base: str, head: str) -> list[str]:
    if not SHA_PATTERN.fullmatch(base) or not SHA_PATTERN.fullmatch(head):
        raise ValueError("base and head must be 40- or 64-character hexadecimal Git object IDs")
    if set(base) == {"0"} or set(head) == {"0"}:
        raise ValueError("an all-zero Git object ID cannot be diffed")

    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", "--no-renames", f"{base}...{head}"],
        check=True,
        capture_output=True,
    )
    return [part.decode(errors="surrogateescape") for part in result.stdout.split(b"\0") if part]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--all", action="store_true", help="select every CI category")
    source.add_argument("--base", help="base Git object ID")
    parser.add_argument("--head", help="head Git object ID; required with --base")
    parser.add_argument("--github-output", type=Path, help="append outputs to this GitHub output file")
    parser.add_argument("--json", action="store_true", help="print the selection as JSON")
    args = parser.parse_args(argv)
    if args.base and not args.head:
        parser.error("--head is required with --base")
    if args.head and not args.base:
        parser.error("--head requires --base")
    if not args.github_output and not args.json:
        parser.error("at least one of --github-output or --json is required")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    paths: list[str] = []
    if args.all:
        selection = Selection.all()
    else:
        try:
            paths = changed_paths(args.base, args.head)
            selection = classify_paths(paths)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            print(f"warning: unable to classify Git diff; selecting full CI: {exc}", file=sys.stderr)
            selection = Selection.all()

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(selection.github_outputs())
    if args.json:
        print(json.dumps(asdict(selection), sort_keys=True))

    if paths:
        print("Changed paths:")
        for path in paths:
            print(f"- {path}")
    selected = [name for name, value in asdict(selection).items() if value]
    print(f"Selected CI categories: {', '.join(selected) if selected else 'lightweight checks only'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
