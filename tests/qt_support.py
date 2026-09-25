"""#729: the one place that decides whether a Qt widget test may skip.

CI installs the `[app]` extra, yet every widget test there skipped as "PySide6 extra
not installed": the import was failing on the runner for a different reason, ten
files turned that into a skip whose message lied, and a green run carried no desktop
proof at all. Locally a missing extra still skips, now with the real error. Under
`CI=true` nothing skips, so a broken Qt install fails loudly where it can be fixed.
"""

from __future__ import annotations

import importlib
import os
import unittest

_QT_MODULES = ("PySide6.QtWidgets", "PySide6.QtMultimedia")


def qt_import_problem() -> str | None:
    """The first Qt import failure, verbatim, or None when Qt imports cleanly."""
    for name in _QT_MODULES:
        try:
            importlib.import_module(name)
        except ImportError as exc:
            return f"{name}: {exc}"
    return None


QT_IMPORT_ERROR: str | None = qt_import_problem()


def in_ci() -> bool:
    return os.getenv("CI", "").strip().lower() in ("1", "true", "yes")


def should_skip() -> bool:
    return QT_IMPORT_ERROR is not None and not in_ci()


def skip_reason() -> str:
    return f"Qt unavailable here ({QT_IMPORT_ERROR}); required under CI"


requires_qt = unittest.skipIf(should_skip(), skip_reason())
