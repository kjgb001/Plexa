# Plexa Repository Maintainence

This directory is the operator entry point for keeping Plexa's source,
dependencies, CI, and production deployment healthy. The directory intentionally
uses the requested `maintainence` spelling so these command paths remain stable.

## Commands

| Command | Purpose | Network or destructive behavior |
| --- | --- | --- |
| `maintainence/audit-ci.sh` | Enforce the repository's CI security invariants. | No network; does not modify files. |
| `maintainence/run-ci-local.sh --quick` | Run static policy, lock, portal lint, and portal build checks using installed dependencies. | No intentional network; does not modify tracked files. |
| `maintainence/run-ci-local.sh` | Recreate CI locally with clean installs and an isolated disposable PostgreSQL container. | Downloads dependencies/images; replaces `plexa_portal/node_modules`; deletes only its disposable container. |
| `maintainence/update-action-pin.sh OWNER/REPO TAG` | Resolve a reviewed action release tag to a full commit SHA and update existing workflow references. | Reads GitHub; modifies workflow files. |
| `maintainence/update-uv-pin.sh VERSION` | Fetch the official Astral manifest, download and verify the Linux artifact, and update the uv version/checksum pair. | Reads GitHub/Astral; modifies `ci.yml`. |
| `maintainence/update-postgres-pin.sh TAG` | Pull a selected official PostgreSQL image and update the CI tag/digest pair. | Reads Docker Hub; modifies `ci.yml`. |

All scripts can be called from any working directory. Update scripts refuse to
overwrite uncommitted changes in the files they manage.

## Prerequisites

- Bash, Git, Python 3, npm, and uv.
- Docker Engine for the full local CI check and PostgreSQL pin updates.
- The Node.js and uv versions currently pinned in `.github/workflows/ci.yml`.
- Permission to read public GitHub and package registry resources.

Do not work around npm peer dependency failures with `--force` or
`--legacy-peer-deps`. A clean `npm ci --ignore-scripts` failure means the
proposed manifest is not a supported dependency combination.

## Normal Schedule

### Every Dependabot Run

1. Read the upstream changelog and security notes before running code from the pull request.
2. Inspect changes to manifests, lockfiles, workflows, and resolved download URLs.
3. For a GitHub Action, confirm the full SHA in the diff belongs to the release tag shown in the comment.
4. Run `maintainence/run-ci-local.sh --quick` after checking out the PR.
5. Run `maintainence/run-ci-local.sh` before merging a major update or a coupled toolchain update.
6. Merge only after the protected GitHub checks pass. Do not enable unattended auto-merge for major updates.

Dependabot intentionally groups compatible minor and patch updates for the
ESLint, Vite, and TypeScript documentation toolchains. ESLint 10 is blocked
until `eslint`, `@eslint/js`, and the plugin set are upgraded and tested
together. Vite and its React plugin are both major-gated so neither side of
their peer contract can advance alone. TypeScript 7 is blocked until TypeDoc,
TypeScript ESLint, and the remaining tooling declare support. Security alerts
for these ecosystems must still be reviewed immediately; use a manual
compatibility upgrade if a fix requires a blocked major.

### Monthly

1. Run `maintainence/run-ci-local.sh` from a clean branch.
2. Review open Dependabot alerts and stale Dependabot PRs.
3. Check supported Node.js, Python, uv, PostgreSQL, and Ubuntu runner releases.
4. Apply patch/security releases with the pin helpers below.
5. Run `deploy/check-production.sh <env-file> --mode domain --stage prestart` for each maintained production configuration.
6. Confirm recent database backups exist and that the last scheduled restore drill succeeded.

### Quarterly

1. Recheck the GitHub repository settings in the manual checklist below.
2. Review `.github/CODEOWNERS` and remove users or teams that no longer require access.
3. Review all workflow permissions, triggers, third-party actions, runner types, and secrets.
4. Perform a restore drill with `deploy/restore-production.sh` in an isolated non-production stack.
5. Review log-retention policy, encrypted-log key rotation, OIDC configuration, and administrator membership.
6. Confirm production still runs one web worker; multiple workers require shared session coordination before they are supported.

## Local Verification

Use the quick check while editing:

```bash
maintainence/run-ci-local.sh --quick
```

Quick mode warns, but does not fail, when local Node.js or uv differs from CI.
Full mode requires exact version matches so its result is comparable to GitHub.

The quick mode deliberately does not prove that lockfiles install cleanly. Use
the full check before merging dependency, migration, workflow, or deployment
changes:

```bash
maintainence/run-ci-local.sh
```

Full mode performs the following automatically:

1. Audits workflow security policy and validates Bash syntax.
2. Checks `uv.lock`, runs a clean npm install with lifecycle scripts disabled, and audits high-severity npm vulnerabilities.
3. Lints and builds the portal.
4. Synchronizes the frozen Python environment.
5. Starts a disposable PostgreSQL container from the exact digest pinned in CI.
6. Runs the migration upgrade/downgrade compatibility sequence.
7. Runs the server tests against filesystem and PostgreSQL storage.
8. Stops and removes the disposable PostgreSQL container on exit.

The full script does not use, reset, or delete the development or production
database. If it is interrupted, remove only a leftover container whose name
starts with `plexa-maintainence-postgres-`.

## Updating Immutable Pins

Pin helpers automate resolution and verification, but choosing and approving a
release remains a manual security decision.

### GitHub Action

1. Read the action's release notes and security policy on its official repository.
2. Run the helper with the exact reviewed tag:

```bash
maintainence/update-action-pin.sh actions/checkout v7.0.1
```

3. Confirm the printed diff changes only the expected action and preserves a 40-character SHA.
4. Run `maintainence/run-ci-local.sh --quick`, commit the workflow update, and require normal PR review.

The helper handles annotated tags by selecting the tag's peeled commit. It only
updates actions already present in the repository; adding a new third-party
action requires a separate security review.

### uv

1. Read the official uv release notes and select a concrete version.
2. Run:

```bash
maintainence/update-uv-pin.sh 0.12.1
```

3. Confirm that both `version` and `checksum` changed together.
4. Run the full local CI check before merging.

The helper reads Astral's official release manifest, downloads the exact x86-64
Linux artifact used by the GitHub runner, verifies its SHA-256 checksum, and
then updates the workflow.

### PostgreSQL CI Image

1. Read the official image and PostgreSQL release notes. Preserve the Debian variant unless a base-image migration is intentional.
2. Run:

```bash
maintainence/update-postgres-pin.sh 17.10-bookworm
```

3. Confirm that the workflow contains both the selected tag and an immutable `sha256` digest.
4. Run the full local CI check before merging.

The production image and database upgrade procedure are separate from this CI
service-image pin. Back up production and follow `deploy/README.md` before any
production PostgreSQL upgrade.

## Handling Dependency Failures

### npm `ERESOLVE`

1. Read the error's `Found`, `Could not resolve dependency`, and peer range lines.
2. Identify the host tool and every plugin that declares a peer dependency on it.
3. Check whether compatible plugin releases exist. Upgrade the host and plugins together only when all peer ranges overlap.
4. If no compatible plugin exists, close the update PR and add or retain a documented temporary Dependabot major-version gate.
5. Never commit a lockfile generated with `--force` or `--legacy-peer-deps` merely to make CI pass.

The current gates are documented directly in `.github/dependabot.yml`. Remove a
gate only in the same PR that proves the complete toolchain works.

### New Lint Rules

Treat a newly enabled rule as a source review, not a reason to disable the rule.
Prefer removing derived state effects, moving state changes to user/request
completion paths, or synchronizing only with actual external systems. Disable a
rule only when its behavior is demonstrably incompatible with the application,
and document the smallest possible exception.

### Current Dependabot PR Cleanup

After this maintenance change reaches `main`:

1. Close the standalone ESLint 10 PR because it was generated against the old React Hooks peer tree and does not coordinate the `@eslint/js` major upgrade.
2. Close the standalone Vite 8 PR because `@vitejs/plugin-react` 5.1.4 supports Vite only through 7.x.
3. Close the React Hooks 7.1.1 PR after this change reaches `main`; the compatible dependency update and required source fixes are included here.
4. Close the standalone TypeScript 7 PR because TypeDoc 0.28 and TypeScript ESLint 8 do not support it.
5. Close the standalone `@vitejs/plugin-react` 6 PR because it requires the currently gated Vite 8 major.
6. Remove a major-version gate only in a dedicated compatibility PR that updates every peer-coupled package and passes `npm ci --ignore-scripts`, lint, build, and protected CI checks.

These GitHub PR operations are manual because repository scripts must not close
or merge remote pull requests without an explicit operator decision.

## Production Maintainence

Before a routine production deployment:

```bash
deploy/backup-production.sh deploy/production.env
deploy/check-production.sh deploy/production.env --mode domain --stage prestart
deploy/start-production.sh deploy/production.env
deploy/check-production.sh deploy/production.env --mode domain --stage poststart
```

Manual requirements:

- Verify the backup checksum and retention location before changing the stack.
- Read migration revisions before deploying them; do not rely only on successful test migrations.
- Schedule downtime for database restores, PostgreSQL major upgrades, OIDC changes, and encrypted-log key removal.
- Test restore procedures outside production. A backup that has never been restored is not considered verified.
- Never remove an old encrypted-log key until all retained records using it have expired or been re-encrypted.
- Keep temporary dev login disabled for student-facing deployments.

## GitHub Repository Settings

These settings cannot be enforced completely from files in the repository and
must be checked manually by an administrator.

1. Open **Settings > Actions > General**.
2. Under Actions permissions, allow actions created by GitHub and explicitly allow `astral-sh/setup-uv@*`; do not allow arbitrary actions.
3. Set workflow permissions to read repository contents and packages. Disable permission for Actions to create or approve pull requests.
4. Require approval for workflows submitted by all external contributors.
5. Open **Settings > Rules > Rulesets** and create an active branch ruleset targeting the default branch.
6. Restrict deletion and force pushes, and require pull requests with resolved conversations.
7. Require the `portal`, `server`, and `deployment` status checks from a recent successful CI run. Require the branch to be up to date.
8. With two or more trusted maintainers, require one Code Owner approval, dismiss stale approvals, require approval of the most recent push, and configure no routine bypass.
9. With only one maintainer, use a repository-administrator bypass limited to pull requests; otherwise the sole Code Owner cannot approve their own PR. Remove this bypass after adding a second maintainer.
10. Open **Settings > Security > Advanced Security** and enable the dependency graph, Dependabot alerts, Dependabot security updates, secret scanning, push protection, and private vulnerability reporting.
11. Enable default CodeQL analysis for Python and JavaScript/TypeScript. After its first successful run, require code-scanning results in the branch ruleset.
12. Open **Settings > Secrets and variables > Actions** and remove unused secrets. Put future deployment credentials in a protected `production` environment with required reviewers.

Record completion of this checklist in the institution's operational system;
Git history cannot prove that out-of-repository settings remain enabled.

## Security Incident Procedure

1. Disable affected workflows or Actions if untrusted code may still run.
2. Revoke and rotate every credential the workflow could access, including environment secrets and deployment tokens.
3. Revert the compromised dependency, image, or action to a reviewed immutable pin.
4. Inspect workflow logs, artifacts, releases, packages, caches, and repository changes made during the exposure window.
5. Remove untrusted artifacts and caches, then run the full local CI check from a known-clean checkout.
6. Re-enable workflows only after review, protected CI, and credential rotation are complete.
7. Publish a security advisory when downstream operators or student data could be affected.
