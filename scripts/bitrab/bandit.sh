#!/bin/bash
set -euo pipefail


if [[ "${CI:-}" == "" ]]; then
  . ./global_variables.sh
fi

uv run bandit "$PACKAGE_DIR" -r --quiet
