"""`ops test --order reverse|shuffle` — the suite's verdict must not depend on order.

docs/audit_2026-09.md §1.3: tests/test_run69_fixes.py passed 13/13 alone and failed
under full discovery. A suite whose result depends on discovery order can flip with
no code change; the only proof that it does not is to run it in another order and
get the same answer. This makes that a verb (and a CI leg), not a one-off.

The reorder helper is a pure function on a list so it can be tested without
running anything.
"""

from __future__ import annotations

import unittest


class TestReorder(unittest.TestCase):
    def test_default_is_identity(self):
        from core.suite_order import reorder

        self.assertEqual(reorder(["a", "b", "c"], "default", seed=None), ["a", "b", "c"])

    def test_reverse_reverses(self):
        from core.suite_order import reorder

        self.assertEqual(reorder(["a", "b", "c"], "reverse", seed=None), ["c", "b", "a"])

    def test_shuffle_is_a_permutation_and_seed_reproducible(self):
        from core.suite_order import reorder

        items = [str(i) for i in range(50)]
        once = reorder(items, "shuffle", seed=1)
        twice = reorder(items, "shuffle", seed=1)
        self.assertEqual(once, twice, "same seed must give the same order")
        self.assertEqual(sorted(once), sorted(items), "a shuffle is a permutation, nothing dropped")
        self.assertNotEqual(once, items, "seed 1 must actually move something")

    def test_unknown_order_is_refused(self):
        from core.suite_order import reorder

        with self.assertRaises(ValueError):
            reorder(["a"], "sideways", seed=None)

    def test_flatten_walks_nested_suites(self):
        from core.suite_order import flatten

        class T(unittest.TestCase):
            def test_x(self):
                pass

            def test_y(self):
                pass

        inner = unittest.TestSuite([T("test_x")])
        outer = unittest.TestSuite([inner, unittest.TestSuite([T("test_y")])])
        self.assertEqual([t.id().rsplit(".", 1)[-1] for t in flatten(outer)], ["test_x", "test_y"])


class TestVerbSurface(unittest.TestCase):
    def test_the_parser_knows_order_and_seed(self):
        from scripts.ops import build_parser

        args = build_parser().parse_args(["test", "--order", "reverse", "--seed", "7"])
        self.assertEqual(args.order, "reverse")
        self.assertEqual(args.seed, 7)

    def test_order_defaults_to_default(self):
        from scripts.ops import build_parser

        self.assertEqual(build_parser().parse_args(["test"]).order, "default")


if __name__ == "__main__":
    unittest.main()
