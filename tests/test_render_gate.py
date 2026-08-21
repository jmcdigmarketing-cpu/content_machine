"""Unattended render-queue gate — no DB, no data/ writes."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.render_gate import (
    block_reason_from_quality,
    unattended_render_block_reason,
)


class TestRenderGate(unittest.TestCase):
    def test_a_and_ok_passes(self):
        self.assertIsNone(unattended_render_block_reason(letter="A", authenticity_verdict="ok"))
        self.assertIsNone(unattended_render_block_reason(letter="B", authenticity_verdict="ok"))

    def test_c_is_blocked(self):
        reason = unattended_render_block_reason(letter="C", authenticity_verdict="ok")
        self.assertIsNotNone(reason)
        self.assertIn("report card C", reason)

    def test_review_authenticity_blocked(self):
        reason = unattended_render_block_reason(letter="A", authenticity_verdict="review")
        self.assertIsNotNone(reason)
        self.assertIn("authenticity review", reason)

    def test_missing_fails_closed(self):
        reason = unattended_render_block_reason(letter=None, authenticity_verdict="ok")
        self.assertIsNotNone(reason)
        reason = unattended_render_block_reason(letter="A", authenticity_verdict=None)
        self.assertIsNotNone(reason)

    def test_disabled_via_env(self):
        with patch.dict(os.environ, {"OVERNIGHT_RENDER_GATE": "false"}, clear=False):
            self.assertIsNone(
                unattended_render_block_reason(letter="F", authenticity_verdict="block")
            )

    def test_quality_dict_b_and_ok(self):
        quality = {
            "hook_score": 80,
            "authenticity_score": 90,
            "authenticity_verdict": "ok",
            "ungrounded_count": 0,
        }
        self.assertIsNone(block_reason_from_quality(quality))

    def test_quality_dict_low_grade(self):
        quality = {
            "hook_score": 10,
            "authenticity_score": 10,
            "authenticity_verdict": "ok",
            "ungrounded_count": 8,
        }
        reason = block_reason_from_quality(quality)
        self.assertIsNotNone(reason)
        self.assertIn("report card", reason)


if __name__ == "__main__":
    unittest.main()
