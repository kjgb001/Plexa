#!/usr/bin/env bash

set -e

echo "Generating server API docs"
rm -rf docs/source/generated/server_api
sphinx-apidoc -f -e -o docs/source/generated/server_api plexa_server

echo "Generating client API docs"
cd plexa_client
npx run docs
cd ..

echo "Building Sphinx site"
cd docs
make html
