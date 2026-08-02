#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
maintenance_cd_repo_root

python_bin="$(maintenance_resolve_python)"
"$python_bin" - <<'PY'
from __future__ import annotations

import re
from pathlib import Path

root = Path.cwd()
workflow_dir = root / ".github" / "workflows"
workflow_paths = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
errors: list[str] = []

if not workflow_paths:
    errors.append("No GitHub Actions workflows were found.")

uses_pattern = re.compile(r"^\s*-\s+uses:\s+([^\s#]+)", re.MULTILINE)
sha_pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
digest_pattern = re.compile(r"^.+@sha256:[0-9a-f]{64}$")

for path in workflow_paths:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(root)

    if re.search(r"^\s*(pull_request_target|workflow_run)\s*:", text, re.MULTILINE):
        errors.append(f"{relative}: privileged trigger requires a dedicated security review")
    if re.search(r"permissions\s*:\s*write-all", text):
        errors.append(f"{relative}: permissions: write-all is forbidden")
    deploy_job = None
    if relative.as_posix() == ".github/workflows/docs-pages.yml":
        deploy_job = re.search(
            r"(?ms)^  deploy:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
            text,
        )
        if deploy_job is None:
            errors.append(f"{relative}: expected a dedicated deploy job")

    allowed_pages_writes: set[str] = set()
    for match in re.finditer(
        r"^\s+(?P<scope>[A-Za-z0-9_-]+):\s*write\s*$",
        text,
        re.MULTILINE,
    ):
        scope = match.group("scope")
        inside_pages_deploy = (
            deploy_job is not None
            and deploy_job.start("body") <= match.start() < deploy_job.end("body")
            and scope in {"pages", "id-token"}
        )
        if inside_pages_deploy:
            allowed_pages_writes.add(scope)
        else:
            errors.append(
                f"{relative}: write permission for {scope} requires an explicit audit policy update"
            )
    if deploy_job is not None and allowed_pages_writes != {"pages", "id-token"}:
        errors.append(
            f"{relative}: deploy job must request exactly pages: write and id-token: write"
        )
    if re.search(r"^\s*secrets:\s*inherit\s*$", text, re.MULTILINE):
        errors.append(f"{relative}: inherited secrets are forbidden")
    if "permissions:\n  contents: read" not in text:
        errors.append(f"{relative}: top-level contents: read permission is missing")
    for runner in re.findall(r"^\s*runs-on:\s*([^\s#]+)", text, re.MULTILINE):
        if runner != "ubuntu-24.04":
            errors.append(f"{relative}: unapproved runner: {runner}")
    if text.count("runs-on:") != text.count("timeout-minutes:"):
        errors.append(f"{relative}: every job must define timeout-minutes")
    if text.count("uses: actions/checkout@") != text.count("persist-credentials: false"):
        errors.append(f"{relative}: every checkout step must disable persisted credentials")
    if re.search(r"\bcurl\b[^\n|]*\|\s*(sh|bash)\b", text):
        errors.append(f"{relative}: downloading a script directly into a shell is forbidden")

    for reference in uses_pattern.findall(text):
        if reference.startswith("./"):
            continue
        if reference.startswith("docker://"):
            if not digest_pattern.fullmatch(reference):
                errors.append(f"{relative}: Docker action is not digest-pinned: {reference}")
            continue
        if not sha_pattern.fullmatch(reference):
            errors.append(f"{relative}: action is not pinned to a full commit SHA: {reference}")

    for image in re.findall(r"^\s*image:\s*([^\s#]+)", text, re.MULTILINE):
        if not digest_pattern.fullmatch(image):
            errors.append(f"{relative}: service image is not digest-pinned: {image}")

ci_text = (workflow_dir / "ci.yml").read_text(encoding="utf-8")
for required in ("npm ci --ignore-scripts", "uv sync --frozen", "uv run --frozen"):
    if required not in ci_text:
        errors.append(f".github/workflows/ci.yml: missing reproducible command: {required}")

docs_workflow = (workflow_dir / "docs-pages.yml").read_text(encoding="utf-8")
for required in (
    "if: github.event_name != 'pull_request'",
    "needs: build",
    "name: github-pages",
    "npm --prefix plexa_portal ci --ignore-scripts",
    "uv sync --frozen --group docs",
    "docs/build_docs.sh",
    "actions/configure-pages@",
    "actions/upload-pages-artifact@",
    "actions/deploy-pages@",
):
    if required not in docs_workflow:
        errors.append(f".github/workflows/docs-pages.yml: missing Pages safeguard: {required}")

dependabot = (root / ".github" / "dependabot.yml").read_text(encoding="utf-8")
for ecosystem in ("github-actions", "npm", "uv"):
    if f"package-ecosystem: {ecosystem}" not in dependabot:
        errors.append(f".github/dependabot.yml: missing {ecosystem} updates")

for dependency in ("eslint", "@eslint/js", "vite", "@vitejs/plugin-react", "typescript"):
    gate_pattern = re.compile(
        rf'- dependency-name: ["\']?{re.escape(dependency)}["\']?\n'
        rf'\s+update-types:\n\s+- version-update:semver-major'
    )
    if not gate_pattern.search(dependabot):
        errors.append(f".github/dependabot.yml: missing major-version gate for {dependency}")

codeowners = (root / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
for protected_path in ("/.github/", "/maintenance/", "/docs/"):
    if protected_path not in codeowners:
        errors.append(f".github/CODEOWNERS: missing protection for {protected_path}")

if errors:
    print("CI security audit failed:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(f"CI security audit passed for {len(workflow_paths)} workflow(s).")
PY
