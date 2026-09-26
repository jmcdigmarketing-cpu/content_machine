"""The one place that decides whether a test may skip on a *pinned* dependency.

Sibling of `qt_support.py` (#729). Pillow is a hard runtime dependency
(`pyproject.toml` pins it), yet two tests skipped with "Pillow not installed" —
so a broken Pillow would have skipped quietly in CI and the run still reported OK.
Locally a missing wheel skips, with the real import error in the reason. Under
`CI=true` nothing skips: the install is CI's responsibility and a failure there
is a defect to fix, not a test to step around.
"""

from __future__ import annotations

import importlib
import os
import unittest


def _import_problem(name: str) -> str | None:
    try:
        importlib.import_module(name)
    except ImportError as exc:
        return f"{name}: {exc}"
    return None


def in_ci() -> bool:
    return os.getenv("CI", "").strip().lower() in ("1", "true", "yes")


def requires(module: str):
    """Skip locally when `module` will not import; never skip under CI."""
    problem = _import_problem(module)
    return unittest.skipIf(
        problem is not None and not in_ci(),
        f"{module} unavailable here ({problem}); required under CI",
    )


requires_pillow = requires("PIL")
