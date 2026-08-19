# Plexa Repository Maintenance

This directory contains the repeatable checks and update helpers used to keep
Plexa's dependencies, CI workflows, and production setup healthy.

## Start Here

Run the quick check while developing:

```bash
maintenance/run-ci-local.sh --quick
```

Run the full CI-equivalent check before merging dependency, migration,
workflow, or deployment changes:

```bash
maintenance/run-ci-local.sh
```

The full check downloads dependencies and a PostgreSQL image, replaces
`plexa_portal/node_modules` with a clean install, and creates a disposable
database container. It does not use or remove development or production data.

## Commands

| Command | What it does | Side effects |
| --- | --- | --- |
| `maintenance/audit-ci.sh` | Enforces workflow security and pinning rules | Offline; read-only |
| `maintenance/classify_ci_changes.py --base SHA --head SHA --json` | Shows which CI categories a commit range selects | Offline; read-only |
| `maintenance/run-ci-local.sh --quick` | Checks CI policy, shell syntax, locks, portal lint, and portal build | Uses installed dependencies; read-only for tracked files |
| `maintenance/run-ci-local.sh` | Recreates CI with clean installs, migrations, tests, and disposable PostgreSQL | Downloads packages/images and replaces `node_modules` |
| `maintenance/update-action-pin.sh OWNER/REPO TAG` | Resolves a reviewed action tag to its commit and updates workflow pins | Uses GitHub and edits workflows |
| `maintenance/update-uv-pin.sh VERSION` | Downloads and verifies the official uv artifact, then updates its CI pin | Uses GitHub/Astral and edits `ci.yml` |
| `maintenance/update-postgres-pin.sh TAG` | Pulls PostgreSQL and records the resolved CI image digest | Uses Docker Hub and edits `ci.yml` |
| `docs/build_docs.sh --install` | Installs locked portal dependencies and builds the strict documentation site | Downloads packages and replaces `node_modules` |

All scripts can be called from any working directory. Pin-update helpers refuse
to overwrite uncommitted changes in files they manage.

## Requirements

- Bash, Git, Python 3, Node.js, npm, and uv
- Docker Engine for the full check and PostgreSQL image updates
- Network access to GitHub, Python and npm registries, and Docker Hub
- The exact Node.js and uv versions pinned in [CI](../.github/workflows/ci.yml)
  when running the full check

Quick mode warns about local Node.js or uv version drift. Full mode fails on
drift so its result remains comparable to GitHub Actions.

## What the Full Check Covers

`maintenance/run-ci-local.sh` performs these steps in order:

1. Audit workflow security policy and validate deployment and maintenance Bash.
2. Check `uv.lock` and install portal dependencies with lifecycle scripts disabled.
3. Audit high-severity npm vulnerabilities, then lint and build the portal.
4. Build the authored guides, TypeScript reference, Python reference, and OpenAPI schema.
5. Synchronize the frozen Python environment.
6. Pull PostgreSQL with bounded retries and an ECR Public fallback, then start
   the exact image digest pinned in CI.
7. Exercise the migration downgrade and hardening-upgrade path with data checks.
8. Run the PostgreSQL-backed server suite, including focused legacy-import tests.
9. Remove the disposable database container on exit.

If the script is interrupted, remove only a leftover container whose name
starts with `plexa-maintenance-postgres-` after confirming it is the disposable
CI database.

## Path-Aware CI

Pull requests and pushes to `main` always produce the same three required
status checks, but only the relevant work runs behind them:

| Changed files | CI work selected |
| --- | --- |
| Root and component prose, such as `README.md`, `CITATION.cff`, and `LICENSE` | Classification and aggregate checks only |
| `docs/**` | Documentation build; CodeQL only for Python or JavaScript documentation tooling |
| `plexa_portal/**` | Portal lint/build, documentation build, and JavaScript/TypeScript CodeQL |
| `plexa_server/**` | Server tests, documentation build, and Python CodeQL |
| `deploy/**` or root deployment configuration | Deployment validation |
| Workflow, maintenance, or unrecognized files | Full CI, documentation, and both CodeQL languages |

Some shared inputs select more than one category. For example, Python lockfiles
run server, deployment, and documentation checks. The classifier fails closed:
if it cannot resolve a Git diff, it selects every category rather than skipping
work. Renames are treated as a deletion plus an addition so both the old and new
locations select checks.

The required checks are `Plexa CI`, `Plexa Documentation`, and `Plexa CodeQL`.
Individual jobs may be skipped by design and must not be
configured as required checks. Scheduled runs execute full CI every Monday at
06:17 UTC and both CodeQL analyses at 06:47 UTC. A maintainer can also run
either workflow manually from the Actions page to force every category.

## Routine Schedule

### For Every Dependency PR

1. Read the upstream release notes and security advisories.
2. Inspect manifest, lockfile, workflow, and resolved-download changes.
3. For a GitHub Action, verify that the pinned commit belongs to the release tag
   named in the workflow comment.
4. Run the quick local check on the PR branch.
5. Run the full check for major releases, migration changes, or coupled
   JavaScript toolchain updates.
6. Require `Plexa CI`, `Plexa Documentation`, and `Plexa CodeQL` to pass.
7. Merge one lockfile-changing PR at a time, then let Dependabot rebase the
   remaining PRs before reviewing them again.

If a Dependabot PR is stale after another dependency merge, comment:

```text
@dependabot rebase
```

Dependabot updates always require manual review and merge. Do not enable
unattended auto-merge for dependency updates.

### Monthly

1. Run the full local check from a clean branch.
2. Review Dependabot alerts, open dependency PRs, and stale CI runs.
3. Check supported Node.js, Python, uv, PostgreSQL, and Ubuntu runner releases.
4. Apply reviewed patch and security releases using the pin helpers where applicable.
5. Run the production pre-start check for each maintained deployment configuration.
6. Confirm recent backups exist and the most recent scheduled restore drill succeeded.

### Quarterly

1. Recheck every GitHub setting in the repository checklist below.
2. Review `CODEOWNERS`, collaborators, deploy keys, Actions secrets, and environment access.
3. Review workflow permissions, triggers, actions, images, and runner types.
4. Restore a production backup into an isolated environment.
5. Review retention policy, encrypted-log keys, OIDC settings, and Plexa admins.
6. Confirm production still uses one web worker.

## Dependabot and Toolchain Updates

Dependabot checks npm, Python, and GitHub Actions dependencies weekly. Routine
minor and patch releases are consolidated into at most two open version-update
pull requests per ecosystem. Patch releases have a 7-day cooldown and minor
releases have a 14-day cooldown so newly published versions can stabilize
before Plexa adopts them. GitHub Actions does not support separate SemVer
cooldowns, so Actions updates use a uniform 7-day cooldown.

Npm updates are split into runtime and development groups. Python and GitHub
Actions updates each use one routine group. Major updates remain separate, and
major versions of peer-coupled JavaScript tools are gated in
[`.github/dependabot.yml`](../.github/dependabot.yml) until the complete
toolchain supports them. Security updates are not subject to the routine
version-update limit or cooldown and must be reviewed promptly as separate pull
requests.

For a grouped JavaScript update:

1. Confirm every plugin's peer range overlaps the proposed host-tool version.
2. Check out the PR and run `npm ci --ignore-scripts` without overrides.
3. Run lint and build; for TypeDoc updates, run `docs/build_docs.sh` and inspect
   the generated site. Generated Markdown is intentionally not committed.
4. Run the full maintenance check before removing a major-version gate.

> [!WARNING]
> Never use `npm install --force` or `--legacy-peer-deps` to make a dependency PR
> appear green. A clean `npm ci --ignore-scripts` failure means the manifest is
> not a supported dependency combination.

When a new lint rule fails, review the source rather than disabling the rule by
default. In React code, remove derived-state effects or move updates to event and
request-completion paths when that better matches the component's lifecycle.

Security alerts still require immediate review. If a fix needs a gated major
version, prepare a manual compatibility PR that upgrades the entire peer group.

## Updating Immutable Pins

The helpers verify mechanical details, but a maintainer must still choose and
approve the release.

### GitHub Actions

Read the release notes on the action's official repository, then run:

```bash
maintenance/update-action-pin.sh actions/checkout v7.0.1
```

Confirm that the diff changes only the expected action, retains a full
40-character commit SHA, and updates the human-readable tag comment. The helper
handles annotated tags and sub-actions such as `github/codeql-action/init`, but
only updates actions already present in the repo.

### uv

After reviewing an official uv release:

```bash
maintenance/update-uv-pin.sh 0.12.1
```

The helper reads Astral's release manifest, downloads the Linux x86-64 artifact
used by CI, verifies its SHA-256 digest, and updates the version and checksum
together. Run the full check afterward.

### PostgreSQL CI Image

After reviewing the PostgreSQL and official image release notes:

```bash
maintenance/update-postgres-pin.sh 17.10-bookworm
```

Preserve the Debian image variant unless changing the base image is deliberate.
Confirm that CI records both the selected tag and immutable digest.

This helper updates only CI. A production PostgreSQL upgrade requires a backup,
tested restore, migration review, and the separate procedure in
[`deploy/README.md`](../deploy/README.md).

## Production Maintenance

Use this sequence for a routine application deployment:

```bash
deploy/backup-production.sh deploy/production.env
deploy/check-production.sh deploy/production.env --mode domain --stage prestart
deploy/start-production.sh deploy/production.env
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

Manual checks are still required:

- Verify the backup checksum and off-host retention location before changing the stack.
- Read every new migration instead of relying only on successful test runs.
- Schedule downtime for restores, PostgreSQL major upgrades, OIDC changes, and encryption-key removal.
- Test restores away from production; an untested backup is not a verified backup.
- Keep old log-encryption keys until dependent records expire or are re-encrypted.
- Keep temporary development login disabled on student-facing installations.

## GitHub Repository Settings

Repository files cannot enforce all GitHub security controls. An administrator
should complete this checklist after creating the repository and review it
quarterly.

### Actions

1. Open **Settings > Actions > General**.
2. Under **Actions permissions**, allow actions created by GitHub and explicitly
   allow `astral-sh/setup-uv@*`; do not allow arbitrary third-party actions.
3. Under **Workflow permissions**, select read-only repository contents and
   packages.
4. Disable the option that allows GitHub Actions to create or approve pull requests.
5. Require approval before workflows from all outside collaborators can run.

### Default Branch Ruleset

1. Open **Settings > Rules > Rulesets** and create an active branch ruleset for
   the default branch.
2. Block branch deletion and force pushes.
3. Require changes through pull requests and require resolved conversations.
4. Require the branch to be up to date before merging.
5. Add `Plexa CI`, `Plexa Documentation`, and `Plexa CodeQL` from
   recent successful runs as required status checks.
6. Do not require component jobs or individual CodeQL analysis jobs. They are
   intentionally conditional and may be skipped for unrelated changes.
7. With two or more maintainers, require one Code Owner approval, dismiss stale
   approvals, and require approval of the latest push.
8. With one maintainer, add only a repository-administrator PR bypass so the
   sole Code Owner can merge reviewed, green changes. Remove it after adding a
   second maintainer.

### Security Features

1. Open **Settings > Security > Advanced Security**.
2. Enable the dependency graph, Dependabot alerts, and Dependabot security updates.
3. Enable secret scanning, push protection, and private vulnerability reporting.
4. Use the advanced CodeQL workflow in [`.github/workflows/codeql.yml`](../.github/workflows/codeql.yml),
   not GitHub's default CodeQL setup.
5. Do not enable the ruleset option **Require code scanning results**. Documentation-only
   changes intentionally skip language analysis, while `Plexa CodeQL`
   verifies that every selected analysis succeeded.

### Activating Path-Aware Checks

Use this procedure when configuring the repository for the first time or
changing an existing ruleset. Pause merges while required checks are being
changed.

1. Review the workflow files and prepare them for the default branch.
2. If GitHub's default CodeQL setup is enabled, use **Switch to advanced** in
   **Settings > Security > Advanced Security > Code scanning** before activating
   the advanced workflow. Default and advanced setup should not analyze the same
   languages concurrently.
3. Place the reviewed workflow files on the default branch.
4. Run the **CI**, **Documentation**, and **CodeQL** workflows manually against
   the default branch so GitHub registers their current check names.
5. Confirm the manual runs succeed. CodeQL should report successful Python and
   JavaScript/TypeScript analyses in addition to its aggregate check.
6. Configure the default branch ruleset to require `Plexa CI`,
   `Plexa Documentation`, and `Plexa CodeQL` with **GitHub Actions** selected as
   the source.
7. Remove component jobs, individual language analyses, and superseded checks
   from the required status-check list.
8. Leave **Require code scanning results** disabled because language analyses
   are conditional. The required CodeQL aggregate enforces the selected jobs.
9. Verify that a documentation-only pull request and a source-code pull request
   both receive all three aggregate checks before resuming normal merges.

> [!IMPORTANT]
> Replacing another CodeQL configuration creates a short transition between
> disabling the previous analysis and completing the first advanced run. Keep
> merges paused until the manual CodeQL run succeeds and its aggregate check is
> required by the ruleset.

### Secrets and Environments

1. Open **Settings > Secrets and variables > Actions** and remove unused values.
2. Do not add production credentials to ordinary CI jobs.
3. Put future deployment credentials in a protected `production` environment.
4. Require an appropriate reviewer before jobs can access that environment.
5. Review collaborators, deploy keys, and environment access at the same time.

### GitHub Pages

1. Open **Settings > Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Open **Settings > Environments > github-pages** after the first successful
   documentation build creates the environment.
4. Add a deployment branch rule that permits only the default branch.
5. Do not add repository or production secrets to the documentation workflow;
   it requires only the job-scoped Pages and OIDC permissions in the workflow.
6. Confirm <https://kjgb001.github.io/Plexa/> loads after a successful
   documentation deployment.

Record completion in the institution's operational system. Git history cannot
show whether out-of-repository settings remain enabled.

## Security Incident Procedure

If a workflow, action, package, or image may have been compromised:

1. Disable affected workflows while untrusted code could still run.
2. Revoke and rotate every credential available to those jobs.
3. Revert the dependency, image, or action to a reviewed immutable pin.
4. Inspect logs, artifacts, releases, packages, caches, and repository changes
   from the exposure window.
5. Remove untrusted artifacts and caches, then run the full check from a known-clean checkout.
6. Re-enable workflows only after review, protected CI, and credential rotation.
7. Publish a security advisory when downstream operators or student data could be affected.
