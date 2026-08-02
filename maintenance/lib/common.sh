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

maintenance_pull_image() {
  local max_attempts="${MAINTENANCE_IMAGE_PULL_ATTEMPTS:-3}"
  local image
  local attempt
  local delay

  maintenance_require_command docker
  if [ "$#" -eq 0 ]; then
    maintenance_die "At least one container image is required."
  fi
  if [[ ! "$max_attempts" =~ ^[1-9][0-9]*$ ]]; then
    maintenance_die "Image pull attempt count must be a positive integer."
  fi

  for image in "$@"; do
    for ((attempt = 1; attempt <= max_attempts; attempt++)); do
      if docker pull "$image"; then
        MAINTENANCE_PULLED_IMAGE="$image"
        return 0
      fi
      if [ "$attempt" -lt "$max_attempts" ]; then
        delay=$((attempt * 15))
        maintenance_warn "Image pull failed; retrying in ${delay}s ($attempt/$max_attempts): $image"
        sleep "$delay"
      fi
    done
    maintenance_warn "Image pull failed after $max_attempts attempts: $image"
  done

  maintenance_die "All configured container image registries failed."
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
