#!/bin/bash
set -euo pipefail

if [[ "${CI:-}" == "" ]]; then
  . ./global_variables.sh
fi

#uv run interrogate "$PACKAGE_DIR" --verbose --fail-under 70
## uv run pydoctest --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse"
## uv run linkcheckMarkdown README.md
## uv run mdformat README.md docs/*.md
#uv run codespell README.md "$PACKAGE_DIR" docs --ignore-words=private_dictionary.txt
## Spelling via pylint (non-fatal)
#uv run pylint "$PACKAGE_DIR" --enable C0402 --rcfile=.pylintrc_spell || true
#uv run pylint docs --enable C0402 --rcfile=.pylintrc_spell || true
#uv run changelogmanager validate || true
