"""#442: ops next ranks cost, vault decay, then the existing publish blocker."""

from __future__ import annotations

import unittest
from argparse import Namespace
from io import StringIO
from unittest.mock import patch

from scripts.ops import COMMANDS, cmd_next


class TestOpsNext(unittest.TestCase):
    def test_command_is_registered(self):
        self.assertIn("next", COMMANDS)

    def test_projected_cost_prints_before_blocking(self):
        args = Namespace(channel="tapin")
        with (
            patch(
                "core.run_mode.projected_cost_block_reason",
                return_value=(
                    "Projected cost $1.00 exceeds PROJECTED_COST_MAX_USD=$0.10. "
                    "Stopping before discovery."
                ),
            ),
            patch("core.fact_expiry.warning_lines", return_value=["1 vault note(s) expired"]),
            patch(
                "core.publish_blockers.blocking_publish_sentence",
                return_value="Nothing is blocking publish: grade, authenticity, quota, and facts look clear.",
            ),
            patch("sys.stdout", new_callable=StringIO) as buf,
        ):
            rc = cmd_next(args)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("PROJECTED_COST_MAX_USD", out)
        self.assertNotIn("Nothing is blocking", out)
        self.assertNotIn("vault note", out)
