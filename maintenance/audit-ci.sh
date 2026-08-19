#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
maintenance_cd_repo_root

python_bin="$(maintenance_resolve_python)"
"$python_bin" -m unittest discover -s maintenance -p 'test_classify_ci_changes.py'
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
sha_pattern = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}$"
)
digest_pattern = re.compile(r"^.+@sha256:[0-9a-f]{64}$")

for path in workflow_paths:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(root)

    if re.search(r"^\s*(pull_request_target|workflow_run)\s*:", text, re.MULTILINE):
        errors.append(f"{relative}: privileged trigger requires a dedicated security review")
    trigger_text = text.split("\npermissions:", 1)[0]
    if re.search(r"^\s+paths(?:-ignore)?:\s*", trigger_text, re.MULTILINE):
        errors.append(f"{relative}: top-level path filters are forbidden for required workflows")
    if re.search(r"permissions\s*:\s*write-all", text):
        errors.append(f"{relative}: permissions: write-all is forbidden")
    deploy_job = None
    codeql_analysis_jobs: dict[str, re.Match[str]] = {}
    if relative.as_posix() == ".github/workflows/docs-pages.yml":
        deploy_job = re.search(
            r"(?ms)^  deploy:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
            text,
        )
        if deploy_job is None:
            errors.append(f"{relative}: expected a dedicated deploy job")
    if relative.as_posix() == ".github/workflows/codeql.yml":
        for job_name in ("analyze-python", "analyze-javascript"):
            match = re.search(
                rf"(?ms)^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
                text,
            )
            if match is None:
                errors.append(f"{relative}: expected {job_name} job")
            else:
                codeql_analysis_jobs[job_name] = match
    if relative.as_posix() in {
        ".github/workflows/ci.yml",
        ".github/workflows/codeql.yml",
    }:
        required_job = re.search(
            r"(?ms)^  required:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
            text,
        )
        if required_job is None:
            errors.append(f"{relative}: expected a required aggregate job")
        elif not re.search(r"^    if:\s*always\(\)\s*$", required_job.group("body"), re.MULTILINE):
            errors.append(f"{relative}: required aggregate job must use if: always()")

    allowed_pages_writes: set[str] = set()
    allowed_codeql_writes: set[str] = set()
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
        elif scope == "security-events" and relative.as_posix() == ".github/workflows/codeql.yml":
            containing_jobs = {
                name
                for name, job in codeql_analysis_jobs.items()
                if job.start("body") <= match.start() < job.end("body")
            }
            if len(containing_jobs) == 1:
                allowed_codeql_writes.update(containing_jobs)
            else:
                errors.append(f"{relative}: security-events write is outside an analysis job")
        else:
            errors.append(
                f"{relative}: write permission for {scope} requires an explicit audit policy update"
            )
    if deploy_job is not None and allowed_pages_writes != {"pages", "id-token"}:
        errors.append(
            f"{relative}: deploy job must request exactly pages: write and id-token: write"
        )
    if relative.as_posix() == ".github/workflows/codeql.yml" and allowed_codeql_writes != {
        "analyze-python",
        "analyze-javascript",
    }:
        errors.append(f"{relative}: both analysis jobs must request security-events: write")
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

    for image in re.findall(
        r"^\s*(?:image|PLEXA_CI_POSTGRES_IMAGE|PLEXA_CI_POSTGRES_FALLBACK_IMAGE):\s*([^\s#]+)",
        text,
        re.MULTILINE,
    ):
        if not digest_pattern.fullmatch(image):
            errors.append(f"{relative}: container image is not digest-pinned: {image}")

ci_text = (workflow_dir / "ci.yml").read_text(encoding="utf-8")
for required in (
    "npm ci --ignore-scripts",
    "uv sync --frozen",
    "uv run --frozen",
    "PLEXA_CI_POSTGRES_FALLBACK_IMAGE",
    '"$PLEXA_CI_POSTGRES_IMAGE"',
    '"$PLEXA_CI_POSTGRES_FALLBACK_IMAGE"',
    '"$MAINTENANCE_PULLED_IMAGE"',
    "docker rm --force plexa-ci-postgres",
    "maintenance/classify_ci_changes.py",
    "needs: [changes, portal, server, deployment]",
    "name: Plexa CI",
    'cron: "17 6 * * 1"',
    "workflow_dispatch:",
    "if: always()",
):
    if required not in ci_text:
        errors.append(f".github/workflows/ci.yml: missing reproducible command: {required}")

postgres_images = {
    name: re.search(rf"^\s*{name}:\s*([^\s#]+)", ci_text, re.MULTILINE)
    for name in ("PLEXA_CI_POSTGRES_IMAGE", "PLEXA_CI_POSTGRES_FALLBACK_IMAGE")
}
for name, match in postgres_images.items():
    if match is None:
        errors.append(f".github/workflows/ci.yml: missing {name}")
if all(match is not None for match in postgres_images.values()):
    digests = {match.group(1).rsplit("@", 1)[-1] for match in postgres_images.values()}
    if len(digests) != 1:
        errors.append(".github/workflows/ci.yml: PostgreSQL registry digests do not match")

docs_workflow = (workflow_dir / "docs-pages.yml").read_text(encoding="utf-8")
for required in (
    "maintenance/classify_ci_changes.py",
    "docs_changed: ${{ steps.classify.outputs.docs }}",
    "name: Plexa Documentation",
    "if: steps.classify.outputs.docs == 'true'",
    "if: github.event_name != 'pull_request' && needs.build.outputs.docs_changed == 'true'",
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

codeql_workflow = (workflow_dir / "codeql.yml").read_text(encoding="utf-8")
for required in (
    "maintenance/classify_ci_changes.py",
    "name: Plexa CodeQL",
    "languages: python",
    "languages: javascript-typescript",
    "build-mode: none",
    "needs: [changes, analyze-python, analyze-javascript]",
    'cron: "47 6 * * 1"',
    "workflow_dispatch:",
):
    if required not in codeql_workflow:
        errors.append(f".github/workflows/codeql.yml: missing CodeQL safeguard: {required}")

codeql_references = re.findall(
    r"github/codeql-action/(?:init|analyze)@([0-9a-f]{40})",
    codeql_workflow,
)
if len(codeql_references) != 4 or len(set(codeql_references)) != 1:
    errors.append(".github/workflows/codeql.yml: CodeQL init/analyze actions must share one full SHA")

dependabot = (root / ".github" / "dependabot.yml").read_text(encoding="utf-8")


def dependabot_update_block(ecosystem: str) -> str | None:
    match = re.search(
        rf"(?ms)^  - package-ecosystem: {re.escape(ecosystem)}\n"
        rf"(?P<body>.*?)(?=^  - package-ecosystem:|\Z)",
        dependabot,
    )
    return match.group("body") if match is not None else None


def dependabot_group_block(update_block: str, group: str) -> str | None:
    match = re.search(
        rf"(?ms)^      {re.escape(group)}:\n"
        rf"(?P<body>.*?)(?=^      [A-Za-z0-9_-]+:|^    [A-Za-z0-9_-]+:|\Z)",
        update_block,
    )
    return match.group("body") if match is not None else None


expected_groups = {
    "github-actions": {"actions-routine": None},
    "npm": {
        "npm-runtime": "production",
        "npm-development": "development",
    },
    "uv": {"python-routine": None},
}

expected_cooldowns = {
    "github-actions": "    cooldown:\n      default-days: 7",
    "npm": "    cooldown:\n      semver-patch-days: 7\n      semver-minor-days: 14",
    "uv": "    cooldown:\n      semver-patch-days: 7\n      semver-minor-days: 14",
}

for ecosystem, groups in expected_groups.items():
    update_block = dependabot_update_block(ecosystem)
    if update_block is None:
        errors.append(f".github/dependabot.yml: missing {ecosystem} updates")
        continue

    for required in (
        "    schedule:\n      interval: weekly",
        expected_cooldowns[ecosystem],
        "    open-pull-requests-limit: 2",
    ):
        if required not in update_block:
            errors.append(
                f".github/dependabot.yml: {ecosystem} is missing routine update policy: "
                f"{required.splitlines()[0].strip()}"
            )

    if ecosystem == "github-actions" and re.search(
        r"^      semver-(?:major|minor|patch)-days:",
        update_block,
        re.MULTILINE,
    ):
        errors.append(
            ".github/dependabot.yml: github-actions does not support SemVer cooldown fields"
        )

    for group, dependency_type in groups.items():
        group_block = dependabot_group_block(update_block, group)
        if group_block is None:
            errors.append(f".github/dependabot.yml: missing {ecosystem} group {group}")
            continue
        for required in (
            "        applies-to: version-updates",
            "        update-types:\n          - minor\n          - patch",
        ):
            if required not in group_block:
                errors.append(
                    f".github/dependabot.yml: {group} is missing policy: "
                    f"{required.splitlines()[0].strip()}"
                )
        if dependency_type is None:
            if '        patterns:\n          - "*"' not in group_block:
                errors.append(f".github/dependabot.yml: {group} must match all dependencies")
        elif f"        dependency-type: {dependency_type}" not in group_block:
            errors.append(
                f".github/dependabot.yml: {group} must select {dependency_type} dependencies"
            )

if "applies-to: security-updates" in dependabot:
    errors.append(".github/dependabot.yml: security updates must remain ungrouped")

for stale_group in ("eslint-toolchain", "vite-toolchain", "typescript-toolchain"):
    if f"{stale_group}:" in dependabot:
        errors.append(f".github/dependabot.yml: stale group remains: {stale_group}")

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
