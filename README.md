# mastodon_finder

Project inspired by troml to suggest a Development Status based solely on objective criteria.

A tool to objectively infer PyPI "Development Status" classifiers from code and release artifacts, based on the
[draft PEP ∞](https://github.com/matthewdeanmartin/mastodon_finder/blob/main/docs/PEP.md).

As far as I know, no python authority has given objective criteria for development status and the meaning is 
private to each user. Development status gets brief mention in PEP301.

Meanings

- Development Status :: 1 - Planning - Minimum score. All projects get at least Planning.
- Development Status :: 2 - Pre-Alpha - Few points awarded by grading rubric.
- Development Status :: 3 - Alpha - Many points awarded
- Development Status :: 4 - Beta - Even more points awarded
- Development Status :: 5 - Production/Stable - Perfect score
- Development Status :: 6 - Mature - Production and signs of upgrade help, e.g. Deprecation
- Development Status :: 7 - Inactive - Impossible to award. If you publish now, you are active.

In scope - easily graded metrics.

Out of scope - vibes, intentions, promises, support contracts, budget, staffing.

Also out of scope - linting, type annotations, code coverage in the sense of running third party tools at eval time.

Surprisingly out of scope - interface and API stability. Impossible to evaluate in Python (several noble attempts!),
depends on developer wishes, hopes, aspirations, vibes which require psychology tests, not build tools.

[![tests](https://github.com/matthewdeanmartin/mastodon_finder/actions/workflows/build.yml/badge.svg)
](https://github.com/matthewdeanmartin/mastodon_finder/actions/workflows/tests.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/matthewdeanmartin/mastodon_finder/main.svg)
](https://results.pre-commit.ci/latest/github/matthewdeanmartin/mastodon_finder/main)
[![Downloads](https://img.shields.io/pypi/dm/mastodon_finder)](https://pypistats.org/packages/mastodon_finder)
[![Python Version](https://img.shields.io/pypi/pyversions/mastodon_finder)
![Release](https://img.shields.io/pypi/v/mastodon_finder)
](https://pypi.org/project/mastodon-finder/)

## Installation

Should be safe to pipx install so as to not mix your dependencies with the tool's

```bash
pipx install mastodon-finder
````

## Usage

Run the tool against a local Git repository that has a `pyproject.toml` file.

```bash
# just display info
mastodon-finder analyze /path/to/your/project 

# fails if tool disagrees with your current development status
mastodon-finder verify /path/to/your/project 

# updates pyproject.toml with current status
mastodon-finder update /path/to/your/project 
```

The tool will analyze the project's PyPI releases, Git history, and source code to produce an evidence-based "
Development Status" classifier.

## README Rating and Completion Checking

These two features require LLMs. If no API key is found (see .env.example) these will be skipped.

## Output

The tool outputs a human-readable summary table and a machine-readable JSON report.

### Example Human-Readable Output

```text
                              Development Status Analysis for mastodon-finder                              
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID           ┃ Description                 ┃ Status ┃ Evidence                                           ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ C1           │ SECURITY.md Present         │   OK   │ Checked for security files                         │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C2           │ Trusted Publisher           │   OK   │ All files in most recent package are attested.     │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C3           │ Dependencies Pinned         │   X    │ Found 3 not strictly pinned somehow: textstat,     │
│              │                             │        │ llvm-diagnostics, semantic-version.                │
├──────────────┼─────────────────────────────┼────────┼────────────────────────────────────────────────────┤
│ C4           │ Reproducible Dev Env        │   OK   │ Found uv lockfile ('uv.lock').                     │
...

Final Inferred Classifier: Development Status :: 4 - Beta
Reason: EPS=13/18; version 0.2.0 < 1.0.0; recent release; S3 holds.

```

### Example JSON Output

The tool also prints a detailed JSON object containing the results of every check.

```json
{
  "inferred_classifier": "Development Status :: 4 - Beta",
  "evaluated_at": "2025-09-14T20:00:00.123456Z",
  "checks": {
    "R1": {
      "passed": true,
      "evidence": "Found 15 releases on PyPI for 'my-package'"
    },
    "...": {}
  },
  "metrics": {
    "eps_score": 16,
    "eps_total": 19
  }
}
```

## Project Health

| Metric      | Status                                                                                                                                                                                                                |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Coverage    | [![codecov](https://codecov.io/gh/matthewdeanmartin/mastodon_finder/branch/main/graph/badge.svg)](https://codecov.io/gh/matthewdeanmartin/mastodon_finder)                                                          |
| Docs        | [![Docs](https://mastodon-finder.readthedocs.org/projects/mastodon_finder/badge/?version=latest)](https://mastodon-finder.readthedocs.io/en/latest/)                                                               |
| PyPI        | [![PyPI](https://img.shields.io/pypi/v/mastodon_finder)](https://pypi.org/project/mastodon-finder/)                                                                                                                 |
| Downloads   | [![Downloads](https://static.pepy.tech/personalized-badge/mastodon-finder?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/mastodon_finder) |
| License     | [![License](https://img.shields.io/github/license/matthewdeanmartin/mastodon_finder)](https://github.com/matthewdeanmartin/mastodon_finder/blob/main/LICENSE)                                                       |
| Last Commit | ![Last Commit](https://img.shields.io/github/last-commit/matthewdeanmartin/mastodon_finder)                                                                                                                          |

## Library info pages

- [mastodon_finder](https://libraries.io/pypi/mastodon_finder)

## Snyk Security Pages

- [mastodon_finder](https://security.snyk.io/package/pip/mastodon_finder)

## Prior Art

Autofill/Suggest
- [troml](https://pypi.org/project/troml/)
- [check-python-versions](https://pypi.org/project/check-python-versions/)

Validate
- [classifier-checker](https://pypi.org/project/classifier-checker/)
- [pyroma](https://pypi.org/project/pyroma/) - Metadata completeness + 3 maintainers

Raw Data
- [trove-classifiers](https://pypi.org/project/trove-classifiers/)
- [trove-classifiers-cli](https://pypi.org/project/trove-classifiers-cli/)

UI/Initialization
- [trove-setup](https://pypi.org/project/trove-setup/)

License Tracking
- [pip-licenses](https://github.com/raimon49/pip-licenses)

## Similar hosted services

- [OpenSSF Best Practices](https://www.bestpractices.dev) - some machine validated criteria and many self asserted.
- Libraries.io SourceRank - 1/2 things you can control, 1/2 "popularity contest" metrics


## Contributing

See the [contributing](docs/contributing.md) file for how to contribute 

See the [development_setup](docs/development_setup.md) file for how to set up and to run a local build.
