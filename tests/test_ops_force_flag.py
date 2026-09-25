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


if __name__ == "__main__":
    unittest.main()
