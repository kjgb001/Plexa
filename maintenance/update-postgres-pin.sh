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
docker pull "$image"
repo_digest="$(docker image inspect "$image" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep -E '(^|/)postgres@sha256:' | head -n 1)"
digest="${repo_digest##*@}"
if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  maintenance_die "Docker did not return a valid immutable digest for $image."
fi

PLEXA_POSTGRES_IMAGE="$image" PLEXA_POSTGRES_DIGEST="$digest" "$python_bin" - <<'PY'
import os
import re
from pathlib import Path

path = Path(".github/workflows/ci.yml")
image = os.environ["PLEXA_POSTGRES_IMAGE"]
digest = os.environ["PLEXA_POSTGRES_DIGEST"]
text = path.read_text(encoding="utf-8")
text, updates = re.subn(
    r"(?m)^(\s*image:\s*)postgres:[^\s@]+@sha256:[0-9a-f]{64}(\s*)$",
    rf"\g<1>{image}@{digest}\g<2>",
    text,
)
if updates != 1:
    raise SystemExit(f"Expected one PostgreSQL service image, found {updates}.")
path.write_text(text, encoding="utf-8")
print(f"Updated the CI PostgreSQL image to {image}@{digest}.")
PY

maintenance/audit-ci.sh
maintenance_show_changes .github/workflows/ci.yml
