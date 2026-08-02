#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
maintenance_cd_repo_root

action="${1:-}"
tag="${2:-}"
if [ "$#" -ne 2 ] || [[ ! "$action" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || [[ ! "$tag" =~ ^v?[0-9][A-Za-z0-9_.-]*$ ]]; then
  maintenance_die "Usage: maintenance/update-action-pin.sh OWNER/REPOSITORY RELEASE_TAG"
fi

maintenance_require_command git
maintenance_require_clean_path .github/workflows

if ! grep -R -E -q --include='*.yml' --include='*.yaml' \
  "uses:[[:space:]]*$action(/[A-Za-z0-9_.-]+)*@" .github/workflows; then
  maintenance_die "$action is not referenced by an existing workflow."
fi

remote="https://github.com/${action}.git"
refs="$(git ls-remote "$remote" "refs/tags/$tag" "refs/tags/$tag^{}")"
sha="$(printf '%s\n' "$refs" | awk '$2 ~ /\^\{\}$/ {print $1; found=1} END {if (!found) exit 1}')" || \
  sha="$(printf '%s\n' "$refs" | awk 'NR == 1 {print $1}')"

if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  maintenance_die "Unable to resolve $action tag $tag to a 40-character commit SHA."
fi

python_bin="$(maintenance_resolve_python)"
PLEXA_ACTION="$action" PLEXA_ACTION_TAG="$tag" PLEXA_ACTION_SHA="$sha" "$python_bin" - <<'PY'
import os
import re
from pathlib import Path

action = os.environ["PLEXA_ACTION"]
tag = os.environ["PLEXA_ACTION_TAG"]
sha = os.environ["PLEXA_ACTION_SHA"]
pattern = re.compile(
    rf"(?P<prefix>uses:\s*{re.escape(action)}(?:/[A-Za-z0-9_.-]+)*@)"
    rf"[0-9a-f]{{40}}(?:\s*#.*)?$"
)
updates = 0

for path in sorted([*Path(".github/workflows").glob("*.yml"), *Path(".github/workflows").glob("*.yaml")]):
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        ending = "\n" if line.endswith("\n") else ""
        body = line.removesuffix("\n")
        next_body, count = pattern.subn(rf"\g<prefix>{sha} # {tag}", body)
        updates += count
        lines.append(next_body + ending)
    path.write_text("".join(lines), encoding="utf-8")

if updates == 0:
    raise SystemExit(f"No full-SHA references to {action} were updated.")
print(f"Updated {updates} reference(s) to {action}@{sha} ({tag}).")
PY

maintenance/audit-ci.sh
maintenance_show_changes .github/workflows
