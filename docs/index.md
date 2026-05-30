# mastodon-finder

Mastodon account discovery, enrichment, and LLM-based scoring tool.

For full documentation, see the [README](https://github.com/matthewdeanmartin/mastodon-finder/blob/main/README.md).

## Overview

This project automates the workflow:

1. Discover candidate accounts on Mastodon via keywords, hashtags, profile terms, and "follow what they follow" expansion.
2. Enrich each account into a uniform dossier (bio, fields, recent original posts, stats, discovery reasons).
3. Apply a stack of deterministic pre-LLM filters (language, activity, link-only, bots, etc.).
4. Optionally hand each dossier to an LLM for rubric-based FOLLOW / MAYBE / SKIP decisions.
5. Output a human-readable report to the terminal (rich) and optionally to CSV / Markdown.

## Installation

```bash
pipx install mastodon-finder
```

## Links

- [GitHub](https://github.com/matthewdeanmartin/mastodon-finder)
- [PyPI](https://pypi.org/project/mastodon-finder/)
