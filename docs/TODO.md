# TODO

## Permission to start

- Get confirmation on plan, or we could waste a lot of API calls and tokens.

## Prefilters

- check for content flood
  - retweet flood (ok)
  - original content flood (many not okay), e.g. 50,000 posts
- check for "can't follow back", e.g. follows 5000
- check for "won't follow back", e.g. follows <500 and has >5000 followers
- check for self. Don't recommend self!
- check for bot account- DONE
- check for foreign language
  - not using library?
  - LLM has to many questions in rubric and ignores language?

## Post filters

- Is sentiment negative to topic? If negative, don't follow. Neutral is fine. NOT DONE
- All politics - Sort of works via LLM filter
- Only links - DONE?
- Multiagent
  - One prompt for "language?", another prompt if "has topic 1?", another prompt if "has topic 2?", etc.


## Config
- Default keywords, etc really does not make any sense other than blank lists


## Usability
- Alternative UIs, terminal interactive, TUI, tkinter
- init command to create .toml config file
- multiple commands (clear cache, find, etc.)
- "doctor" to detect problems with API tokens


## Cache
- implement time to live

## LLM
- Allow editing rubric w/o editing source code