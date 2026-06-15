.EXPORT_ALL_VARIABLES:
# Get all python files
FILES := $(wildcard **/*.py)

# Get package directories under src
PACKAGES := $(shell find src -mindepth 1 -maxdepth 1 -type d -not -name "__pycache__")
# Get just the package names (e.g., "pkg1", "pkg2")
PACKAGE_NAMES := $(notdir $(PACKAGES))

# if you wrap everything in uv run, it runs slower.
ifeq ($(origin VIRTUAL_ENV),undefined)
	VENV := uv run
else
	VENV :=
endif

uv.lock: pyproject.toml
	@echo "Installing dependencies"
	@uv sync

clean-pyc:
	@echo "Removing compiled files"
	@find . -name "*.pyc" -exec rm -f {} +
	@find . -name "*.pyo" -exec rm -f {} +
	@find . -name "*~" -exec rm -f {} +
	@find . -name "__pycache__" -exec rm -rf {} +

clean-test:
	@echo "Removing coverage data"
	@rm -f .coverage || true
	@rm -f .coverage.* || true
	@rm -rf htmlcov || true
	@rm -f junit.xml || true

clean: clean-pyc clean-test

# tests can't be expected to pass if dependencies aren't installed.
# tests are often slow and linting is fast, so run tests on linted code.
test: clean uv.lock install_plugins
	@echo "Running unit tests"
	# Run doctests on all packages in src
	# $(VENV) pytest --doctest-modules $(PACKAGES)
	# Run unit tests and generate coverage for the entire src directory
	$(VENV) pytest test -vv -n 2 --cov=src --cov-report=html --cov-fail-under 5 --cov-branch --cov-report=xml --junitxml=junit.xml -o junit_family=legacy --timeout=5 --session-timeout=600
	$(VENV) bash ./scripts/basic_checks.sh
#   $(VENV) bash basic_test_with_logging.sh

# The finder's real Mastodon client driven against the local mastodon_mock
# server (no live instance, no API keys). Self-skips on Python <3.13 or if
# mastodon_mock isn't installed. See test_integration/README.md.
test-integration: uv.lock
	@echo "Running mastodon_mock-backed integration tests"
	$(VENV) pytest test_integration -vv --timeout=30


.build_history:
	@mkdir -p .build_history

.build_history/isort: .build_history $(FILES)
	@echo "Formatting imports"
	$(VENV) isort .
	@touch .build_history/isort

jiggle_version:
ifeq ($(CI),true)
	@echo "Running in CI mode"
	jiggle_version check
else
	@echo "Running locally"
	jiggle_version hash-all
	# jiggle_version bump --increment auto
endif

.PHONY: isort
isort: .build_history/isort

.build_history/black: .build_history .build_history/isort $(FILES) jiggle_version
	@echo "Formatting code"
	$(VENV) metametameta pep621
	# Format all code in src and test
	$(VENV) black src test # --exclude .venv
	# Generate a single SOURCE.md from all packages
	$(VENV) ./scripts/make_source.sh # git2md $(PACKAGES) --ignore __init__.py __pycache__ --output SOURCE.md
	@touch .build_history/black

.PHONY: black
black: .build_history/black

.build_history/pre-commit: .build_history .build_history/isort .build_history/black
	@echo "Pre-commit checks"
	$(VENV) pre-commit run --all-files
	@touch .build_history/pre-commit

.PHONY: pre-commit
pre-commit: .build_history/pre-commit

.build_history/bandit: .build_history $(FILES)
	@echo "Security checks"
	# Run bandit on the entire src directory
	$(VENV) bandit src -r --quiet
	@touch .build_history/bandit

.PHONY: bandit
bandit: .build_history/bandit

.PHONY: pylint
.build_history/pylint: .build_history .build_history/isort .build_history/black $(FILES)
	@echo "Linting with pylint"
	$(VENV) ruff --fix .
	# Run pylint on all packages in src and the test directory
	$(VENV) pylint $(PACKAGES) test --fail-under 9.8
	@touch .build_history/pylint

# for when using -j (jobs, run in parallel)
.NOTPARALLEL: .build_history/isort .build_history/black

check: mypy test pylint bandit update_dev_status dog_food

#.PHONY: publish_test
#publish_test:
#   rm -rf dist && poetry version minor && poetry build && twine upload -r testpypi dist/*

.PHONY: publish
publish: test
	rm -rf dist && hatch build

.PHONY: mypy
mypy:
	@echo "Running mypy on $(PACKAGES)"
	$(VENV) echo $$PYTHONPATH
	# Run mypy on all packages
	$(VENV) mypy $(PACKAGES) --ignore-missing-imports --check-untyped-defs


check_docs:
	# Run interrogate on the entire src directory
	$(VENV) interrogate src --verbose  --fail-under 70
	# Run pydoctest on the entire src directory
	$(VENV) pydoctest src --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse"

make_docs:
	# Generate pdoc for all packages
	@echo "Generating documentation for $(PACKAGES)"
	$(VENV) pdoc $(PACKAGES) --html -o docs --force

check_md:
	$(VENV) linkcheckMarkdown README.md
	$(VENV) markdownlint README.md --config .markdownlintrc
	$(VENV) mdformat README.md docs/*.md


check_spelling:
	# Run pylint spelling check on all packages
	$(VENV) pylint $(PACKAGES) --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) pylint docs --enable C0402 --rcfile=.pylintrc_spell
	$(VENV) codespell README.md --ignore-words=private_dictionary.txt
	# Run codespell on the entire src directory
	$(VENV) codespell src --ignore-words=private_dictionary.txt
	$(VENV) codespell docs --ignore-words=private_dictionary.txt

check_changelog:
	# pipx install keepachangelog-manager
	$(VENV) changelogmanager validate

check_all_docs: check_docs check_md check_spelling check_changelog

check_self:
	# Can it verify itself?
	$(VENV) ./scripts/dog_food.sh

#audit:
#   # This would need to be looped if re-enabled
#   @echo "Auditing packages"
#   @$(foreach pkg_name,$(PACKAGE_NAMES), $(VENV) tool_audit single $(pkg_name) --version=">=2.0.0";)

install_plugins:
	echo "N/A"

.PHONY: issues
issues:
	echo "N/A"

core_all_tests:
	# Loop over each package name for the exercise script
	@echo "Running core all tests for $(PACKAGE_NAMES)"
	@$(foreach pkg_name,$(PACKAGE_NAMES), ./scripts/exercise_core_all.sh $(pkg_name) "compile --in examples/compile/src --out examples/compile/out --dry-run";)
	uv sync

update_dev_status:
	troml-dev-status update .

dog_food:
	mastodon-finder validate .
	metametameta sync-check
	# mastodon-finder --totalhelp
	# bitrab
	# pycodetags <command?>
	# cli-tool-audit

# ── Dogfooding targets (independent, not wired into check) ───────────────────

.PHONY: version-check
version-check:
	@uv run jiggle_version check

.PHONY: dev-status
dev-status:
	@uv run troml-dev-status validate .

.PHONY: prerelease-check
prerelease-check: version-check dev-status
	@echo "Pre-release checks passed."

.PHONY: dont-be-lazy
dont-be-lazy:
	@uv run dont_be_lazy --root . --no-color summary
	@uv run dont_be_lazy --root . --no-color scan mastodon_finder --no-config-suppressions || true

.PHONY: pydoc-docs
pydoc-docs:
	@uv run pydoc_fork mastodon_finder -o ./pydoc/
