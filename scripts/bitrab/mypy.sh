#!/bin/bash
set -euo pipefail
if [[ "${CI:-}" == "" ]]; then
  . ./global_variables.sh
fi

uv run mypy "$PACKAGE_DIR" --ignore-missing-imports --check-untyped-defs
