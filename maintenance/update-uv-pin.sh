#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
maintenance_cd_repo_root

version="${1:-}"
if [ "$#" -ne 1 ] || [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
  maintenance_die "Usage: maintenance/update-uv-pin.sh VERSION"
fi

maintenance_require_command curl
maintenance_require_command sha256sum
maintenance_require_clean_path .github/workflows/ci.yml
python_bin="$(maintenance_resolve_python)"

temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT INT TERM
manifest="$temporary_dir/uv.ndjson"
archive="$temporary_dir/uv.tar.gz"

maintenance_note "Fetching the official Astral release manifest..."
curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
  https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson \
  --output "$manifest"

release_data="$("$python_bin" - "$manifest" "$version" <<'PY'
import json
import sys

path, version = sys.argv[1:]
for line in open(path, encoding="utf-8"):
    release = json.loads(line)
    if release["version"] != version:
        continue
    for artifact in release["artifacts"]:
        if artifact["platform"] == "x86_64-unknown-linux-gnu" and artifact["variant"] == "default":
            print(f'{artifact["sha256"]}\t{artifact["url"]}')
            raise SystemExit(0)
    raise SystemExit("Release exists but has no x86_64 Linux default artifact.")
raise SystemExit(f"uv {version} was not found in the official Astral manifest.")
PY
)"
checksum="${release_data%%$'\t'*}"
url="${release_data#*$'\t'}"
if [[ ! "$checksum" =~ ^[0-9a-f]{64}$ ]] || [[ "$url" != https://* ]]; then
  maintenance_die "The uv release metadata was malformed."
fi

maintenance_note "Downloading and verifying the pinned uv artifact..."
curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location "$url" --output "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check --status || \
  maintenance_die "The downloaded uv artifact did not match the official checksum."

PLEXA_UV_VERSION="$version" PLEXA_UV_CHECKSUM="$checksum" "$python_bin" - <<'PY'
import os
import re
from pathlib import Path

path = Path(".github/workflows/ci.yml")
version = os.environ["PLEXA_UV_VERSION"]
checksum = os.environ["PLEXA_UV_CHECKSUM"]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
inside_setup_uv = False
version_updates = 0
checksum_updates = 0

for index, line in enumerate(lines):
    if re.match(r"^\s*-\s+uses:\s+astral-sh/setup-uv@", line):
        inside_setup_uv = True
        continue
    if inside_setup_uv and re.match(r"^\s*-\s+(uses|run|name):", line):
        inside_setup_uv = False
    if not inside_setup_uv:
        continue
    lines[index], count = re.subn(r'^(\s*version:\s*)"?[^"]+"?\s*$', rf'\g<1>"{version}"', line.rstrip("\n"))
    if count:
        lines[index] += "\n"
        version_updates += count
        continue
    lines[index], count = re.subn(r"^(\s*checksum:\s*)[0-9a-f]+\s*$", rf"\g<1>{checksum}", line.rstrip("\n"))
    if count:
        lines[index] += "\n"
        checksum_updates += count

if version_updates != 1 or checksum_updates != 1:
    raise SystemExit(f"Expected one uv version and checksum, found {version_updates} and {checksum_updates}.")
path.write_text("".join(lines), encoding="utf-8")
print(f"Updated the CI uv pin to {version} ({checksum}).")
PY

maintenance/audit-ci.sh
maintenance_show_changes .github/workflows/ci.yml
