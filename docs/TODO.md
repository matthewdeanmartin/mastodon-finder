# TODO

## Prefilters

- check for content flood
  - retweet flood (ok)
  - original content flood (many not okay), e.g. 50,000 posts
- check for foreign language
  - not using library?
  - LLM has to many questions in rubric and ignores language?

## Post filters

- Is sentiment negative to topic? If negative, don't follow. Neutral is fine. NOT DONE
- All politics - Sort of works via LLM filter
- Multiagent
  - One prompt for "language?", another prompt if "has topic 1?", another prompt if "has topic 2?", etc.


## Config
- Default keywords, etc really does not make any sense other than blank lists


## Usability
- Alternative UIs, terminal interactive, TUI, tkinter
- init command to create .toml config file
- multiple commands (clear cache, find, etc.)
- "doctor" to detect problems with API tokens

## LLM
- Allow editing rubric w/o editing source code