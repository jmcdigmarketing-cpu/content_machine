import logging
import os
import sys

_CONFIGURED = False

_QUIET_LIBRARIES = (
    "googleapiclient",
    "googleapiclient.discovery_cache",
    "httpx",
    "httpcore",
    "urllib3",
    "google",
)


def setup_logging(level=None):
    global _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger("content_machine")

    if level is None:
        level_name = os.getenv("CONTENT_LOG_LEVEL", "WARNING").upper()
        level = getattr(logging, level_name, logging.WARNING)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    quiet = os.getenv("CONTENT_QUIET_LOGS", "true").lower() in ("1", "true", "yes")
    if quiet:
        for name in _QUIET_LIBRARIES:
            logging.getLogger(name).setLevel(logging.ERROR)

    logging.getLogger("content_machine").setLevel(level)
    _CONFIGURED = True
    return logging.getLogger("content_machine")


def get_logger(name=None):
    setup_logging()
    if name:
        return logging.getLogger(f"content_machine.{name}")
    return logging.getLogger("content_machine")
