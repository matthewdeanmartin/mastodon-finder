"""
Logging configuration.
"""

from __future__ import annotations

import os
from typing import Any

try:
    import colorlog  # noqa

    # This is only here so that I can see if colorlog is installed
    # and to keep autofixers from removing an "unused import"
    if False:  # pylint: disable=using-constant-test
        assert colorlog  # noqa # nosec
    colorlog_available = True
except ImportError:  # no qa
    colorlog_available = False


def generate_config(level: str = "DEBUG") -> dict[str, Any]:
    """
    Generate a logging configuration.
    Args:
        level: The logging level.

    Returns:
        dict: The logging configuration.
    """
    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "[%(levelname)s] %(name)s: %(message)s"},
            "colored": {
                "()": "colorlog.ColoredFormatter",
                "format": "%(log_color)s%(levelname)-8s%(reset)s %(green)s%(message)s",
            },
        },
        "handlers": {
            "default": {
                "level": level,
                "formatter": "colored",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",  # Default is stderr
            },
        },
        "loggers": {
            "bash2gitlab": {
                "handlers": ["default"],
                "level": level,
                "propagate": False,
            }
        },
    }
    if not colorlog_available:
        del config["formatters"]["colored"]
        config["handlers"]["default"]["formatter"] = "standard"

    if os.environ.get("NO_COLOR") or os.environ.get("CI"):
        config["handlers"]["default"]["formatter"] = "standard"

    return config
