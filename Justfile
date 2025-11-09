# Use bash with strict flags
# set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := true

# ---- Variables ----
LOGS_DIR := ".justlogs"
JOBS := num_cpus()

# Determine runner prefix: if no virtualenv active, use `uv run`, otherwise nothing
venv := `if [ -z "${VIRTUAL_ENV-}" ]; then echo "uv run"; else echo ""; fi`

# Get package directories under src as a space-separated string
PACKAGES := `find src -mindepth 1 -maxdepth 1 -type d -not -name "__pycache__" | tr '\n' ' '`

# ---- Defaults ----
_default: check

# ---- Dependencies / Setup ----
uv-lock:
	@echo "Installing dependencies"
	{{venv}} uv sync --no-progress

clean-pyc:
	@echo "Removing compiled files"
	@find . -name "*.pyc" -exec rm -f {} +
	@find . -name "*.pyo" -exec rm -f {} +
	@find . -name "*~" -exec rm -f {} +
	@find . -name "__pycache__" -exec rm -rf {} +

clean-test:
	@echo "Removing coverage data"
	rm -f .coverage || true
	rm -f .coverage.* || true
	@rm -rf htmlcov || true
	@rm -f junit.xml || true

clean: clean-pyc clean-test

install-plugins:
	@echo "N/A"


# ---- Formatting / Linting (serial invariants) ----
isort: 	
	@echo "Formatting imports"
	{{venv}} isort .

black: isort 	
	@echo "Formatting code"
	{{venv}} metametameta pep621
	# Format all code in src and test
	{{venv}} black src test
	# Generate a single SOURCE.md from all packages
	# {{venv}} git2md {{PACKAGES}} --ignore __init__.py __pycache__ --output SOURCE.md
	./scripts/make_source.sh

pre-commit: black 	
	@echo "Pre-commit checks"
	{{venv}} pre-commit run --all-files

ruff-fix:
	{{venv}} ruff check --fix .

pylint: black ruff-fix 	
	@echo "Linting with pylint"
	# Run pylint on all packages in src and the test directory
	{{venv}} pylint {{PACKAGES}} test --fail-under 9.9 --rcfile=.pylintrc

bandit: 	
	@echo "Security checks"
	# Run bandit on the entire src directory
	{{venv}} bandit src -r --quiet

mypy:
	@echo "Running mypy on {{PACKAGES}}"
	# Run mypy on all packages
	{{venv}} mypy {{PACKAGES}} --ignore-missing-imports --check-untyped-defs

# ---- Tests ----
# tests can't be expected to pass if dependencies aren't installed.
# tests are often slow and linting is fast, so run tests on linted code.

test: clean uv-lock install-plugins
	@echo "Running unit tests"
	# Run doctests on all packages in src
	# {{venv}} pytest --doctest-modules {{PACKAGES}}
	# Run unit tests and generate coverage for the entire src directory
	{{venv}} py.test test -vv -n auto \
	  --cov=src --cov-report=html --cov-fail-under 12 --cov-branch \
	  --cov-report=xml --junitxml=junit.xml -o junit_family=legacy \
	  --timeout=5 --session-timeout=600
	{{venv}} bash ./scripts/basic_checks.sh

# =========================
# Normal mode (sequential, laptop-friendly)
# =========================
check: mypy test pylint bandit pre-commit

# =========================
# Fast mode (no `bash -c`, rely on Just's [parallel])
# - Each job writes to its own log and creates an .ok marker on success.
# - We always print logs afterward, and propagate failure if any .ok is missing.
# =========================

# Log-writing variants (no bash -c):

mypy-log:
	mkdir -p {{LOGS_DIR}}
	: > {{LOGS_DIR}}/mypy.log
	{{venv}} mypy {{PACKAGES}} --ignore-missing-imports --check-untyped-defs > {{LOGS_DIR}}/mypy.log 2>&1


bandit-log:
	mkdir -p {{LOGS_DIR}}
	: > {{LOGS_DIR}}/bandit.log
	{{venv}} bandit src -r --quiet > {{LOGS_DIR}}/bandit.log 2>&1

pylint-log:
	mkdir -p {{LOGS_DIR}}
	: > {{LOGS_DIR}}/pylint.log
	{{venv}} ruff check --fix . > {{LOGS_DIR}}/pylint.log 2>&1
	{{venv}} pylint {{PACKAGES}} --fail-under 5 >> {{LOGS_DIR}}/pylint.log 2>&1


pre-commit-log:
	mkdir -p {{LOGS_DIR}}
	: > {{LOGS_DIR}}/pre-commit.log
	{{venv}} pre-commit run --all-files > {{LOGS_DIR}}/pre-commit.log 2>&1


# Run parallel phase: mypy, bandit, pylint-chain, pre-commit-chain
[parallel]
fast-phase: mypy-log bandit-log pylint-log pre-commit-log

# Orchestrate: run the parallel phase; don't stop on error so we can print logs
check-fast: clean uv-lock install-plugins
	just fast-phase || true
	for f in pylint mypy bandit pre-commit; do \
	  if test -f {{LOGS_DIR}}/$$f.log; then \
		echo "\n===== $$f: BEGIN ====="; \
		cat {{LOGS_DIR}}/$$f.log; \
		echo "===== $$f: END =====\n"; \
	  fi; \
	done
	# If any .ok is missing, fail; else continue to tests
	for f in pylint mypy bandit pre-commit; do \
	  if ! test -f {{LOGS_DIR}}/$f.ok; then echo $f && missing=1; fi; \
	done; \
	if test "${missing-}" = "1"; then \
	  echo "One or more checks failed."; \
	  exit 1; \
	fi
	just test

# ---- Docs & Markdown / Spelling / Changelog ----
check-docs:
	# Run interrogate on the entire src directory
	{{venv}} interrogate src --verbose
	# Run pydoctest on the entire src directory
	{{venv}} pydoctest src --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse"

make-docs:
	# Generate pdoc for all packages
	@echo "Generating documentation for {{PACKAGES}}"
	pdoc {{PACKAGES}} --html -o docs --force

check-md:
	{{venv}} linkcheckMarkdown README.md
	{{venv}} markdownlint README.md --config .markdownlintrc
	{{venv}} mdformat README.md docs/*.md

check-spelling:
	# Run pylint spelling check on all packages
	{{venv}} pylint {{PACKAGES}} --enable C0402 --rcfile=.pylintrc_spell
	{{venv}} codespell README.md --ignore-words=private_dictionary.txt
	# Run codespell on the entire src directory
	{{venv}} codespell src --ignore-words=private_dictionary.txt
	{{venv}} codespell docs --ignore-words=private_dictionary.txt

check-changelog:
	{{venv}} changelogmanager validate

check-all-docs: check-docs check-md check-spelling check-changelog

check-own-ver:
	{{venv}} ./dog_food.sh

publish: test
	rm -rf dist && hatch build

issues:
	@echo "N/A"
