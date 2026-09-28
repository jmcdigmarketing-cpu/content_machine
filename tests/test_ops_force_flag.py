"""`--force` was read by four ops verbs and declared by none.

`scripts/ops.py` forwards `--force` for `backfill-cost`, `competitor-sync`,
`daily-sync` and (wave 30) `backfill-quality`, each via
`getattr(args, "force", False)`. The shared parser never declared the flag, so
argparse rejected it at the top level - `py -m scripts.ops backfill-features
--force` exits with "unrecognized arguments: --force" - and the `getattr`
default meant the code path silently read False even if it had got through.

Found while re-running the #823 backfill with `--force`.
"""

from __future__ import annotations

import unittest
from typing import ClassVar


class TestForceIsAcceptedWhereItIsRead(unittest.TestCase):
    def _parse(self, *argv: str):
        from scripts.ops import build_parser

        return build_parser().parse_args(list(argv))

    def test_the_parser_knows_the_flag(self) -> None:
        args = self._parse("backfill-quality", "--force")
        self.assertTrue(args.force)

    def test_it_defaults_off(self) -> None:
        self.assertFalse(self._parse("backfill-quality").force)

    def test_every_verb_that_reads_force_can_be_given_it(self) -> None:
        """The three that predate this wave, not just the new one."""
        for verb in ("backfill-cost", "competitor-sync", "daily-sync"):
            with self.subTest(verb=verb):
                self.assertTrue(self._parse(verb, "--force").force)


class TestNoOtherFlagIsReadButUndeclared(unittest.TestCase):
    """A ratchet: the same shape must not come back."""

    def test_every_getattr_flag_in_ops_is_declared_or_defaulted(self) -> None:
        """The exact failure mode: read from args, not a flag, and not assigned.

        `queue_upload` and friends are read but never declared *as flags* - they
        are switched off by an explicit `args.x = False` in `main`, which is a
        deliberate disable, not a bug. `--force` had neither, which is why it
        could not be passed and read False when it was.
        """
        import re
        from pathlib import Path

        from scripts.ops import build_parser

        source = Path("scripts/ops.py").read_text(encoding="utf-8")
        read = {m.group(1) for m in re.finditer(r'getattr\(args,\s*"([a-z_]+)"', source)}
        assigned = {m.group(1) for m in re.finditer(r"^\s+args\.([a-z_]+)\s*=", source, re.M)}
        declared = set(vars(build_parser().parse_args(["status"])))
        missing = sorted(read - declared - assigned)
        self.assertEqual(missing, [], f"read from args but neither a flag nor defaulted: {missing}")


class TestForceReachesTheCodeItGuards(unittest.TestCase):
    """#825: the parser half was fixed in wave 30; nothing ran the rest of the chain.

    `ops` hands `--force` to a child process, so the flag only matters if the child's
    own parser declares it *and* passes it on. Each link is proved here, because none
    of the three verbs has ever been force-run on the operator's PC.
    """

    VERBS: ClassVar[dict[str, str]] = {
        "backfill-cost": "analytics.backfill_cost",
        "competitor-sync": "analytics.competitor_sync",
        "daily-sync": "scripts.daily_sync",
    }

    def test_ops_hands_the_flag_to_the_child_process(self) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from scripts import ops

        for verb, module in self.VERBS.items():
            with self.subTest(verb=verb):
                args = ops.build_parser().parse_args([verb, "--force"])
                with (
                    patch.object(ops.subprocess, "call", return_value=0) as call,
                    redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(ops.COMMANDS[verb][1](args), 0)
                argv = call.call_args.args[0]
                self.assertEqual(argv[1:3], ["-m", module])
                self.assertIn("--force", argv)

    def test_daily_sync_forces_the_competitor_snapshot(self) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from scripts import daily_sync

        with (
            patch.object(
                daily_sync, "ensure_competitor_snapshot", return_value={"skipped": True}
            ) as snap,
            patch.object(daily_sync, "refresh_seo_hints", return_value={}),
            patch("core.vault.writeback.write_channel_beliefs", return_value=None),
            patch("core.vault.dossiers.refresh_dossiers", return_value=0),
            redirect_stdout(io.StringIO()),
        ):
            daily_sync.main(["--channel", "tapin", "--force"])
        self.assertTrue(snap.call_args.kwargs["force"])

    def test_competitor_sync_skips_the_freshness_check(self) -> None:
        import io
        import sys
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from analytics import competitor_sync

        with (
            patch.object(sys, "argv", ["competitor_sync", "--channel", "tapin", "--force"]),
            patch("analytics.competitor_context.is_snapshot_stale", return_value=False) as stale,
            patch.object(
                competitor_sync, "sync_competitors", return_value={"competitors": []}
            ) as sync,
            redirect_stdout(io.StringIO()),
        ):
            competitor_sync.main()
        stale.assert_not_called()
        sync.assert_called_once_with("tapin")

    def test_backfill_cost_recomputes_with_force(self) -> None:
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from analytics import backfill_cost

        with (
            patch.object(backfill_cost, "plan_channel", return_value=[]) as plan,
            redirect_stdout(io.StringIO()),
        ):
            backfill_cost.main(["--channel", "tapin", "--force"])
        self.assertTrue(plan.call_args.kwargs["force"])


if __name__ == "__main__":
    unittest.main()
