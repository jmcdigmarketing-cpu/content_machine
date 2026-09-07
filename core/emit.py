"""Stage 0 emit() seam: one module-level print sink.

Display helpers default print_fn to emit so a Qt pane can capture output later
without rewriting every call site. Terminal backend is stdout.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_sink: Callable[..., Any] = print


def emit(*args: Any, **kwargs: Any) -> None:
    _sink(*args, **kwargs)
    from core.pinned_status import refresh_pin

    refresh_pin()


def set_emit(fn: Callable[..., Any] | None) -> None:
    global _sink
    _sink = fn or print


def reset_emit() -> None:
    set_emit(print)
