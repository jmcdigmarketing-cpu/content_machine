"""One reset point for process-global state (#827).

Modules that keep state at module level — a probe result, a client cache, a
session breaker, a "last value" marker — register a reset here at import time.
The test suite calls :func:`reset_all` before every test (``tests/__init__.py``),
so what one test caches cannot decide what the next test sees.

Before this existed, `tests/test_run69_fixes.py` passed 13/13 alone and failed
5 under full discovery: `core.llm_router._ollama_probe_cache` had been warmed by
an earlier test with `requests` mocked to fail, and the five tests guarding the
run-70 outage went inert (docs/audit_2026-09.md §1.3). Three test files reset
that one global by hand; some thirty other module-level mutables had no reset
path at all.

Rules for what to register:

* **State, not resources.** A cached probe, token, client or breaker resets. A
  loaded model, a font, or a configured logger does not — those are expensive to
  rebuild and their staleness is not what leaks between tests.
* **IO-free.** `reset_all()` runs thousands of times per suite. A reset that
  writes a file belongs in the module's own `reset_*` helper for CLI use, not
  here — register the in-memory part only.
* **Idempotent by name.** Registering the same name again replaces the callable,
  so a module reloaded by a test does not stack resets.

This module imports nothing from the rest of the package, so any module can
import it at load time without a cycle.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

_lock = threading.Lock()
_resets: dict[str, Callable[[], None]] = {}


def register_reset(name: str, fn: Callable[[], None]) -> None:
    """Register (or replace) the reset for the state owned by ``name``.

    ``name`` is the owning module's dotted path by convention (``"core.tts"``),
    so a failure in :func:`reset_all` names where to look.
    """
    with _lock:
        _resets[name] = fn


def unregister_reset(name: str) -> None:
    """Forget a registration. Missing names are ignored (test cleanup)."""
    with _lock:
        _resets.pop(name, None)


def registered() -> list[str]:
    """Registered owner names, sorted — for the audit and for `ops` introspection."""
    with _lock:
        return sorted(_resets)


def reset_all() -> None:
    """Run every registered reset.

    Failures propagate, prefixed with the owner's name: a reset that raises is a
    bug in that module, and swallowing it would put the suite back where it
    started — reporting green while a guard is inert.
    """
    with _lock:
        items = list(_resets.items())
    for name, fn in items:
        try:
            fn()
        except Exception as exc:
            raise RuntimeError(f"process_state reset failed for {name}: {exc}") from exc
