#! /bin/bash
set -eou pipefail
# Smoke test  all the tests that don't necessarily change anything
# exercises the arg parser mostly.
set -eou pipefail
echo "help..."
mastodon_finder --help
echo "compile help..."
mastodon_finder run --help
echo "version..."
mastodon_finder --version
echo "dry run run"
mastodon_finder run --dry-run
echo "done"

