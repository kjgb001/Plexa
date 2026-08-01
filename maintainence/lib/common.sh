#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Plexa maintainence scripts require bash." >&2
  exit 1
fi

PLEXA_MAINTAINENCE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLEXA_MAINTAINENCE_DIR="$(cd "$PLEXA_MAINTAINENCE_LIB_DIR/.." && pwd)"
PLEXA_REPO_ROOT="$(cd "$PLEXA_MAINTAINENCE_DIR/.." && pwd)"

maintainence_die() {
  echo "error: $*" >&2
  exit 1
}

maintainence_note() {
  echo "$*" >&2
}

maintainence_warn() {
  echo "warning: $*" >&2
}

maintainence_cd_repo_root() {
  cd "$PLEXA_REPO_ROOT" || maintainence_die "Unable to enter repository root: $PLEXA_REPO_ROOT"
}

maintainence_require_command() {
  local command_name="$1"
  local install_hint="${2:-}"

  if command -v "$command_name" >/dev/null 2>&1; then
    return 0
  fi

  if [ -n "$install_hint" ]; then
    maintainence_die "$command_name is required. $install_hint"
  fi
  maintainence_die "$command_name is required."
}

maintainence_resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi
  maintainence_die "Python 3 is required, but neither python3 nor python was found."
}

maintainence_require_clean_path() {
  local path="$1"

  if ! git diff --quiet -- "$path" || \
    ! git diff --cached --quiet -- "$path" || \
    [ -n "$(git ls-files --others --exclude-standard -- "$path")" ]; then
    maintainence_die "Refusing to overwrite uncommitted changes under $path."
  fi
}

maintainence_show_changes() {
  git diff -- "$@"
}
