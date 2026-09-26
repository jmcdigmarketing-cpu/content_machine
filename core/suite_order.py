"""Run the unit suite in a chosen order — the proof that its verdict is order-free (#828).

`tests/test_run69_fixes.py` passed 13/13 alone and failed under full discovery
(docs/audit_2026-09.md §1.3). A suite whose result depends on the order tests happen
to load in can flip with no code change, and the only way to know it does not is to
run it in another order and get the same answer. `py -m scripts.ops test --order
reverse` and `--order shuffle --seed N` do that; CI runs the reversed leg.

Runs in-process so `tests/__init__.py` (the suite-wide isolation and the #827 reset
hook) is imported exactly as `discover -s tests -t .` would import it.
"""

from __future__ import annotations

import os
import random
import sys
import time
import unittest
from collections.abc import Iterable

from config.paths import ROOT_DIR

ORDERS = ("default", "reverse", "shuffle")


def flatten(suite: unittest.TestSuite | unittest.TestCase) -> list[unittest.TestCase]:
    """Every leaf test in a (nested) suite, in discovery order."""
    if isinstance(suite, unittest.TestCase):
        return [suite]
    out: list[unittest.TestCase] = []
    for item in suite:
        out.extend(flatten(item))
    return out


def reorder(tests: Iterable[unittest.TestCase], order: str, *, seed: int | None) -> list:
    """Pure: the same tests in the requested order. Shuffle is reproducible by seed."""
    items = list(tests)
    if order == "default":
        return items
    if order == "reverse":
        return items[::-1]
    if order == "shuffle":
        random.Random(seed).shuffle(items)
        return items
    raise ValueError(f"unknown order {order!r}; expected one of {ORDERS}")


def run_ordered(order: str, *, seed: int | None = None, verbosity: int = 1) -> int:
    """Discover like CI (`-s tests -t .`), reorder, run. 0 when green."""
    if order == "shuffle" and seed is None:
        seed = int(time.time()) % 100_000
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(ROOT_DIR, "tests"), top_level_dir=ROOT_DIR)
    if loader.errors:
        for err in loader.errors:
            print(err, file=sys.stderr)
    tests = reorder(flatten(suite), order, seed=seed)
    label = f"order={order}" + (f" seed={seed}" if order == "shuffle" else "")
    print(f">> {len(tests)} tests, {label}")
    result = unittest.TextTestRunner(verbosity=verbosity).run(unittest.TestSuite(tests))
    if not result.wasSuccessful() and order == "shuffle":
        print(f"reproduce with: py -m scripts.ops test --order shuffle --seed {seed}")
    return 0 if result.wasSuccessful() and not loader.errors else 1
