#!/bin/bash

if [[ "${CI:-}" == "" ]]; then
  . ./global_variables.sh
fi

rm -rf dist
uv run hatch build
