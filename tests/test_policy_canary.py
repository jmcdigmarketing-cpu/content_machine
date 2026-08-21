"""Policy canary — local fixture, snapshot file isolated, no HTTP."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.policy_canary import DEFAULT_FIXTURE, inspect, page_hash, warning_lines


class TestPolicyCanary(unittest.TestCase):
    def test_hash_stable_for_fixture(self):
        text = Path(DEFAULT_FIXTURE).read_text(encoding="utf-8")
        self.assertEqual(page_hash(text), page_hash(text))
        self.assertEqual(len(page_hash(text)), 64)

    def test_first_snapshot_not_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "c.json")
            first = inspect(source_path=DEFAULT_FIXTURE, snapshot_path=snap)
            self.assertTrue(first["ok"])
            self.assertFalse(first["changed"])
            self.assertEqual(warning_lines(first), [])

    def test_hash_move_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "c.json")
            inspect(source_text="alpha", snapshot_path=snap)
            second = inspect(source_text="beta", snapshot_path=snap)
            self.assertTrue(second["changed"])
            self.assertTrue(warning_lines(second))

    def test_fetch_env_off_does_not_http(self):
        with (
            patch.dict(os.environ, {"POLICY_CANARY_FETCH": "false"}),
            patch("requests.get") as get,
            tempfile.TemporaryDirectory() as tmp,
        ):
            inspect(snapshot_path=os.path.join(tmp, "c.json"), fetch=True)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
