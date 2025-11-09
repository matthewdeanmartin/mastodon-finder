#!/bin/bash

if [[ "${CI:-}" == "" ]]; then
  . ./global_variables.sh
fi

uv run pdoc "$PACKAGE_DIR" --html -o docs --force
