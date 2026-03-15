#!/usr/bin/env bash

set -e

echo "Generating server API docs"
sphinx-apidoc -o docs/source/generated/server_api plexa_server

echo "Generating client API docs"
cd plexa_client
npx typedoc --out ../docs/source/generated/client_api src
cd ..

echo "Building Sphinx site"
cd docs
make html
