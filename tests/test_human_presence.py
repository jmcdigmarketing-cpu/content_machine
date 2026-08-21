"""Human-presence unattended-render gate — temp heartbeat, no real data/."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core.human_presence import (
    UNATTENDED_OPS,
    maybe_touch_ops,
    touch,
    unattended_render_block_reason,
)


class TestHumanPresence(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "hb.json")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_off(self):
        with patch.dict(os.environ, {"HUMAN_PRESENCE_HOURS": ""}, clear=False):
            self.assertIsNone(unattended_render_block_reason(path=self.path))

    def test_missing_heartbeat_fails_closed(self):
        env = {"HUMAN_PRESENCE_HOURS": "24"}
        with patch.dict(os.environ, env, clear=False):
            reason = unattended_render_block_reason(now=1_000.0, path=self.path)
        self.assertIsNotNone(reason)
        self.assertIn("no operator heartbeat", reason or "")

    def test_fresh_heartbeat_passes(self):
        touch(at=1_000.0, path=self.path)
        env = {"HUMAN_PRESENCE_HOURS": "24"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(unattended_render_block_reason(now=1_000.0 + 3600.0, path=self.path))

    def test_stale_heartbeat_blocks(self):
        touch(at=1_000.0, path=self.path)
        env = {"HUMAN_PRESENCE_HOURS": "24"}
        with patch.dict(os.environ, env, clear=False):
            reason = unattended_render_block_reason(now=1_000.0 + 25 * 3600.0, path=self.path)
        self.assertIsNotNone(reason)
        self.assertIn("last operator", reason or "")

    def test_overnight_does_not_touch(self):
        maybe_touch_ops("overnight", at=99.0, path=self.path)
        self.assertFalse(os.path.isfile(self.path))
        self.assertIn("overnight", UNATTENDED_OPS)

    def test_attended_ops_touches(self):
        maybe_touch_ops("status", at=42.0, path=self.path)
        self.assertTrue(os.path.isfile(self.path))

    def test_default_path_is_noop_when_gate_off(self):
        from core.human_presence import HEARTBEAT_FILE

        with patch.dict(os.environ, {"HUMAN_PRESENCE_HOURS": ""}, clear=False):
            touch(at=1.0)
        self.assertFalse(os.path.isfile(HEARTBEAT_FILE))


if __name__ == "__main__":
    unittest.main()
