"""The discovery deadline, visible to the code that spends money (#820).

#811 stops *waiting* for a straggler at the deadline; the worker kept running and its
Apify call still went out, so the budget bought the operator's time, not credit. This
Event is set by `register_signals._fetch_all` when the deadline fires and checked by
`apify_client.run_actor` before its POST. Free signals are not consulted: their late
`set_cache` write is what makes the next run fast, and it costs nothing.

A separate module so `apify_client` can import it without a cycle through the registry.
Reset per discovery and per test (core.process_state).
"""

from __future__ import annotations

import threading

from core import process_state

_cancelled = threading.Event()


def cancel() -> None:
    _cancelled.set()


def reset() -> None:
    _cancelled.clear()


def cancelled() -> bool:
    return _cancelled.is_set()


process_state.register_reset("apis.run_deadline", reset)
