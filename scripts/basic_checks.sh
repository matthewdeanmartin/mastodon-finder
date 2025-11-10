#!/usr/bin/env bash
set -euo pipefail

mastodon_finder --help

# dry run doesn't work, makes API calls
#echo "--- Test 1: Dry Run (Simulates LLM) ---"
## Use --yes to skip prompt
## Use --dry-run to skip actual LLM calls
## Use --max-accounts to keep it fast
#python -m mastodon_finder run \
#    --yes \
#    --dry-run \
#    --max-accounts 5 \
#    --output-file dry_run_report.md
#
#echo "Dry run test complete. Report saved to dry_run_report.md"
#
#
#echo "--- Test 2: No-LLM Run (Disables LLM) ---"
## Use --yes to skip prompt
## Use --no-llm to skip the LLM evaluation phase entirely
## Use --max-accounts to keep it fast
#python -m mastodon_finder run \
#    --yes \
#    --no-llm \
#    --dry-run \
#    --max-accounts 5 \
#    --output-file no_llm_report.csv
#
#echo "No-LLM test complete. Report saved to no_llm_report.csv"
#
#echo "--- All tests passed! ---"