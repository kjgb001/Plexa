#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
maintenance_cd_repo_root

tag="${1:-}"
if [ "$#" -ne 1 ] || [[ ! "$tag" =~ ^[0-9][A-Za-z0-9_.-]*$ ]]; then
  maintenance_die "Usage: maintenance/update-postgres-pin.sh POSTGRES_TAG"
fi

maintenance_require_command docker "Ensure Docker Engine is installed and the daemon is reachable."
maintenance_require_clean_path .github/workflows/ci.yml
python_bin="$(maintenance_resolve_python)"
image="postgres:$tag"

maintenance_note "Pulling the selected official PostgreSQL image..."
maintenance_pull_image "$image"
repo_digest="$(docker image inspect "$image" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep -E '(^|/)postgres@sha256:' | head -n 1)"
digest="${repo_digest##*@}"
if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  maintenance_die "Docker did not return a valid immutable digest for $image."
fi
fallback_image="public.ecr.aws/docker/library/postgres@$digest"
maintenance_note "Verifying the same manifest through the ECR Public mirror..."
maintenance_pull_image "$fallback_image"

PLEXA_POSTGRES_IMAGE="$image" \
PLEXA_POSTGRES_FALLBACK_IMAGE="$fallback_image" \
PLEXA_POSTGRES_DIGEST="$digest" \
  "$python_bin" - <<'PY'
import os
import re
from pathlib import Path

path = Path(".github/workflows/ci.yml")
image = os.environ["PLEXA_POSTGRES_IMAGE"]
fallback_image = os.environ["PLEXA_POSTGRES_FALLBACK_IMAGE"]
digest = os.environ["PLEXA_POSTGRES_DIGEST"]
text = path.read_text(encoding="utf-8")
text, primary_updates = re.subn(
    r"(?m)^(\s*PLEXA_CI_POSTGRES_IMAGE:\s*)postgres:[^\s@]+@sha256:[0-9a-f]{64}(\s*)$",
    rf"\g<1>{image}@{digest}\g<2>",
    text,
)
text, fallback_updates = re.subn(
    r"(?m)^(\s*PLEXA_CI_POSTGRES_FALLBACK_IMAGE:\s*)[^\s@]+@sha256:[0-9a-f]{64}(\s*)$",
    rf"\g<1>{fallback_image}\g<2>",
    text,
)
if primary_updates != 1 or fallback_updates != 1:
    raise SystemExit(
        "Expected one primary and one fallback PostgreSQL CI image, "
        f"found {primary_updates} and {fallback_updates}."
    )
path.write_text(text, encoding="utf-8")
print(f"Updated both CI PostgreSQL registry references to {digest}.")
PY

maintenance/audit-ci.sh
maintenance_show_changes .github/workflows/ci.yml
