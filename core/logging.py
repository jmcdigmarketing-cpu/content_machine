import contextvars
import logging
import os
import sys
from concurrent.futures import Executor

_CONFIGURED = False
_RUN_ID: contextvars.ContextVar[str] = contextvars.ContextVar("cm_run_id", default="")

_QUIET_LIBRARIES = (
    "googleapiclient",
    "googleapiclient.discovery_cache",
    "httpx",
    "httpcore",
    "urllib3",
    "google",
)


class _RunFormatter(logging.Formatter):
    """A bound run inserts ``run=<id> `` after the level. Unbound lines stay as they were."""

    def format(self, record: logging.LogRecord) -> str:
        run = _RUN_ID.get()
        record.run_prefix = f"run={run} " if run else ""
        return super().format(record)


def bind_run(run_id: int | str | None) -> contextvars.Token[str]:
    """Log lines on this context, and on work submitted via ``submit_in_run``, name the run."""
    text = "" if run_id in (None, "") else str(run_id)
    return _RUN_ID.set(text)


def clear_run(token: contextvars.Token[str] | None = None) -> None:
    if token is None:
        _RUN_ID.set("")
        return
    _RUN_ID.reset(token)


def submit_in_run(executor: Executor, fn, /, *args, **kwargs):
    """Submit ``fn`` with the caller's run id. This interpreter's pool does not copy it."""
    ctx = contextvars.copy_context()

    def _call(*a, **kw):
        return ctx.run(fn, *a, **kw)

    return executor.submit(_call, *args, **kwargs)


def setup_logging(level=None):
    global _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger("content_machine")

    if level is None:
        level_name = os.getenv("CONTENT_LOG_LEVEL", "WARNING").upper()
        level = getattr(logging, level_name, logging.WARNING)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(run_prefix)s%(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    console = _RunFormatter("%(asctime)s [%(levelname)s] %(run_prefix)s%(message)s", "%H:%M:%S")
    for handler in logging.getLogger().handlers:
        if type(handler) is logging.StreamHandler and handler.level == logging.NOTSET:
            handler.setFormatter(console)

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
        _RunFormatter(
            "%(asctime)s [%(levelname)s] %(run_prefix)s%(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
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


def tail_log(n: int = 40) -> dict:
    """Last ``n`` lines of the log file, and the WARNING lines among them (#990).

    A missing file, a blank ``CONTENT_LOG_FILE``, or an unreadable file is an empty
    result. Nothing is logged: an absent log is not a failed run.
    """
    path = log_file_path()
    empty = {"path": path or "", "lines": [], "warnings": []}
    if not path or not os.path.isfile(path):
        return empty
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return empty
    count = n if n and n > 0 else 40
    tail = lines[-count:]
    warnings = [line for line in tail if " [WARNING] " in line]
    return {"path": path, "lines": tail, "warnings": warnings}


def log_link_text(n: int = 40) -> str:
    """The Costs-page line: the log path and the latest warning, or none."""
    got = tail_log(n)
    path = got["path"] or "(log off)"
    if got["warnings"]:
        return f"{path} - {got['warnings'][-1]}"
    return f"{path} - no warnings in the log"


def detach_log_file() -> None:
    """Remove the log file handler (`ops test` runs the suite in-process: no data/ writes)."""
    app = logging.getLogger("content_machine")
    for handler in list(app.handlers):
        if getattr(handler, "_cm_log_file", False):
            app.removeHandler(handler)
            handler.close()
