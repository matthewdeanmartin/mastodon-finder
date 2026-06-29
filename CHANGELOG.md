# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New "find nice people" evaluation workflow. Discovery and mechanical filters are
  unchanged, but the LLM rubric judges candidates on whether they are a real person
  (not an org/bot), have generally positive sentiment, and reply to others — instead
  of topic relevance. Select with `mastodon-finder find-nice`, `run --nice`,
  `run --mode nice`, or `[evaluation] mode = "nice"` in `finder.toml`. The original
  topic-based workflow remains the default. See `spec/find_nice_people.md`.

## [0.3.0] - 2025-11-11

### Added

- Add `llm-auth` command to guide users through setting an LLM API key interactively

## [0.2.0] - 2025-11-11

### Fixed

- Fix config loading to deserialize as dict instead of a strongly typed object

## [0.1.0] - 2025-11-10

### Added

- Search by keyword and hashtag for posts and account bios
- Search by account followers as a signal of interest, geography, or niche community
- Filter out already-followed accounts before presenting results
- Cache current-user info (friends list) to avoid redundant API calls
- Cache other API responses to support resuming a failed or interrupted run
- Detect language of posts using langdetect
- Filter candidates by minimum post count, post recency, original vs repost ratio, and original vs link-only ratio
- Apply LLM-based filtering using a static rubric for language, topic match, topic coverage, and freeform concerns

[0.3.0]: https://github.com/matthewdeanmartin/mastodon-finder/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/matthewdeanmartin/mastodon-finder/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/matthewdeanmartin/mastodon-finder/releases/tag/v0.1.0
