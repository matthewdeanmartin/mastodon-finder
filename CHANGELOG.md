# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- Added for new features.
- Changed for changes in existing functionality.
- Deprecated for soon-to-be removed features.
- Removed for now removed features.
- Fixed for any bug fixes.
- Security in case of vulnerabilities.

## [0.3.0] - 2025-11-11

### Added

- llm-auth command to step you through adding the API key for the LLM


## [0.2.0] - 2025-11-10

### Fixed

- Config loads as dict, instead of strongly typed

## [0.1.0] - 2025-11-10


### Added

- Search by keyword, hashtag for post, for account bio
- Search by "followers of an account" as signal of interest, geograph, etc.
- Filters out already followed
- Caching for info about self, e.g. current friends
- Caching for other API calls, e.g. for resuming a failed run
- langdetect for posts
- Filter 
  - by minimum number of posts
  - post recency
  - original vs retweet
  - original vs all links 
- LLM filter
  - By static rubric
