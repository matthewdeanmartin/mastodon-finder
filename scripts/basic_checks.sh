#!/usr/bin/env bash
set -euo pipefail

mastodon_finder --help
mastodon_finder analyze .
mastodon_finder analyze . --json
mastodon_finder validate .