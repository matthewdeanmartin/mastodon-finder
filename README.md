# mastodon_finder

Find Mastodon Accounts.

## Installation

git clone until I can make a package

## Usage

1. Set up your mastodon and openrouter/openAI key `*`
2. edit config.py
3. OR set all the switches
4. run `mastodon-finder` at the terminal

`*` In the future I will implement an interface to AWS Mechanical Turk for people who don't want to use AI.

## Pipeline

1. Gets your current friend lists
2. Finds possible friends by keyword, hashtag, "follows special interest account"
3. Remove accounts with bad metrics (inactivity, no original content, etc)
4. Ask LLM to grade each candidate on a rubric
5. Display "FOLLOW", "MAYBE", "SKIP" report

## Features

- Search by keyword, hashtag for post, for account bio
- Search by "followers of an account" as signal of interest, geograph, etc.
- Filters out already followed
- Caching for info about self, e.g. current friends
- Caching for other API calls, e.g. for resuming a failed run
- langdetect for posts
- Filter
    - by minimum number of posts - is anyone one home
    - post recency - is anyone home now
    - original vs retweet - do they write their own content
    - original vs all links - is this an RSS feed cross posted to mastodon?
    - does the author ever reply to anyone?
- LLM filter
    - By static rubric
        - Is it the right language?
        - Is it the right topic?
        - Did it hit all the topics?
        - Is there some other unforeseen problem?

## Prior Art

Bad profile search and bad search has been touted as an intentional privacy feature

### Directories

- [Trunk](https://communitywiki.org/trunk)
- [Fedi.Directory](https://fedi.directory/)

Just a bunch of sheets https://researchbuzz.me/2022/11/05/a-big-list-of-mastodon-resources/