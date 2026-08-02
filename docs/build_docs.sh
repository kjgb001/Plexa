#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GENERATED_DIR="$SCRIPT_DIR/source/generated"
BUILD_DIR="$SCRIPT_DIR/build"

usage() {
    cat <<'EOF'
Usage: docs/build_docs.sh [--install] [--linkcheck]

  --install    Install the locked portal dependencies before building.
  --linkcheck  Check external links after the strict HTML build.
EOF
}

install_portal=false
run_linkcheck=false
while (($#)); do
    case "$1" in
        --install)
            install_portal=true
            ;;
        --linkcheck)
            run_linkcheck=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

command -v uv >/dev/null 2>&1 || {
    echo "uv is required to build the documentation: https://docs.astral.sh/uv/" >&2
    exit 1
}
command -v npm >/dev/null 2>&1 || {
    echo "npm is required to generate the portal reference." >&2
    exit 1
}

cd "$REPO_ROOT"

if [[ "$install_portal" == true ]]; then
    echo "Installing locked portal dependencies"
    npm --prefix plexa_portal ci --ignore-scripts
elif [[ ! -x plexa_portal/node_modules/.bin/typedoc ]]; then
    echo "Portal dependencies are missing. Run docs/build_docs.sh --install first." >&2
    exit 1
fi

echo "Cleaning generated documentation"
rm -rf "$GENERATED_DIR" "$BUILD_DIR"
mkdir -p "$GENERATED_DIR/server_api" "$GENERATED_DIR/openapi"

echo "Generating server API reference"
uv run --frozen --group docs sphinx-apidoc \
    --force \
    --separate \
    --module-first \
    --maxdepth 2 \
    --automodule-options members,show-inheritance \
    --output-dir "$GENERATED_DIR/server_api" \
    "$REPO_ROOT/plexa_server" \
    "$REPO_ROOT/plexa_server/alembic" \
    "$REPO_ROOT/plexa_server/tests" \
    "$REPO_ROOT/plexa_server/api/main.py" \
    "$REPO_ROOT/plexa_server/bootstrap.py" \
    "$REPO_ROOT/plexa_server/db" \
    "$REPO_ROOT/plexa_server/storage/postgres.py" \
    "$REPO_ROOT/plexa_server/utils/dev_seed_data.py" \
    "$REPO_ROOT/plexa_server/utils/seed_dev_data.py"

echo "Generating portal API reference"
npm --prefix plexa_portal run docs
uv run --frozen --group docs python "$SCRIPT_DIR/prepare_typedoc.py" \
    "$GENERATED_DIR/client_api"

echo "Generating OpenAPI schema"
uv run --frozen --group docs python "$SCRIPT_DIR/generate_openapi.py" \
    "$GENERATED_DIR/openapi/openapi.json"

echo "Building documentation with warnings treated as errors"
uv run --frozen --group docs sphinx-build \
    --quiet \
    --fresh-env \
    --nitpicky \
    --fail-on-warning \
    --builder html \
    "$SCRIPT_DIR/source" \
    "$BUILD_DIR/html"

if [[ "$run_linkcheck" == true ]]; then
    echo "Checking external links"
    uv run --frozen --group docs sphinx-build \
        --quiet \
        --fresh-env \
        --fail-on-warning \
        --builder linkcheck \
        "$SCRIPT_DIR/source" \
        "$BUILD_DIR/linkcheck"
fi

echo "Documentation built at $BUILD_DIR/html/index.html"
