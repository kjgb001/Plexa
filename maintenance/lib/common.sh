#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Plexa maintenance scripts require bash." >&2
  exit 1
fi

PLEXA_MAINTENANCE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLEXA_MAINTENANCE_DIR="$(cd "$PLEXA_MAINTENANCE_LIB_DIR/.." && pwd)"
PLEXA_REPO_ROOT="$(cd "$PLEXA_MAINTENANCE_DIR/.." && pwd)"

maintenance_die() {
  echo "error: $*" >&2
  exit 1
}

maintenance_note() {
  echo "$*" >&2
}

maintenance_warn() {
  echo "warning: $*" >&2
}

maintenance_cd_repo_root() {
  cd "$PLEXA_REPO_ROOT" || maintenance_die "Unable to enter repository root: $PLEXA_REPO_ROOT"
}

maintenance_require_command() {
  local command_name="$1"
  local install_hint="${2:-}"

  if command -v "$command_name" >/dev/null 2>&1; then
    return 0
  fi

  if [ -n "$install_hint" ]; then
    maintenance_die "$command_name is required. $install_hint"
  fi
  maintenance_die "$command_name is required."
}

maintenance_resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi
  maintenance_die "Python 3 is required, but neither python3 nor python was found."
}

maintenance_require_clean_path() {
  local path="$1"

  if ! git diff --quiet -- "$path" || \
    ! git diff --cached --quiet -- "$path" || \
    [ -n "$(git ls-files --others --exclude-standard -- "$path")" ]; then
    maintenance_die "Refusing to overwrite uncommitted changes under $path."
  fi
}

maintenance_show_changes() {
  git diff -- "$@"
}
