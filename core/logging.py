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

    # #986: the console shows `level` and up; the routine detail goes to the log file.
    for handler in logging.getLogger().handlers:
        if type(handler) is logging.StreamHandler and handler.level == logging.NOTSET:
            handler.setLevel(level)
    logging.getLogger("content_machine").setLevel(level)
    _CONFIGURED = True
    path = log_file_path()
    if path:
        try:
            attach_log_file(path)
        except OSError:
            pass  # a read-only folder costs the file, never the run
    return logging.getLogger("content_machine")


def log_file_path() -> str | None:
    """#986: `CONTENT_LOG_FILE`, default data/logs/content_machine.log; blank = no file."""
    raw = os.environ.get("CONTENT_LOG_FILE")
    if raw is None:
        from config.paths import DATA_DIR

        return os.path.join(DATA_DIR, "logs", "content_machine.log")
    return raw.strip() or None


def attach_log_file(path: str) -> logging.Handler:
    """INFO and up from the app's loggers to a rotating file (1 MB x 3)."""
    from logging.handlers import RotatingFileHandler

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=3, encoding="utf-8", delay=True
    )
    handler._cm_log_file = True  # type: ignore[attr-defined]
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    app = logging.getLogger("content_machine")
    app.addHandler(handler)
    if app.level == logging.NOTSET or app.level > logging.INFO:
        app.setLevel(logging.INFO)
    return handler


def get_logger(name=None):
    setup_logging()
    if name:
        return logging.getLogger(f"content_machine.{name}")
    return logging.getLogger("content_machine")


def detach_log_file() -> None:
    """Remove the log file handler (`ops test` runs the suite in-process: no data/ writes)."""
    app = logging.getLogger("content_machine")
    for handler in list(app.handlers):
        if getattr(handler, "_cm_log_file", False):
            app.removeHandler(handler)
            handler.close()
