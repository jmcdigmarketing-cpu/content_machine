"""Wave C: public-apis shortlist in agent_reach_evaluation.md is complete enough to use."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "agent_reach_evaluation.md"


class TestWaveCShortlist(unittest.TestCase):
    def test_each_candidate_answers_key_and_rate_limit(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("Wave C", text)
        # Remaining paid Apify actors must be named so the shortlist cannot drift.
        self.assertIn("tiktok_trends", text)
        self.assertIn("youtube_competitors", text)
        section = text.split("Wave C", 1)[1]
        self.assertIn("keyless", section.lower())
        self.assertIn("rate", section.lower())
        # At least one named candidate with the four required fields nearby.
        self.assertRegex(
            section,
            re.compile(r"keyless|api key|needs a key", re.I),
        )
        self.assertRegex(
            section,
            re.compile(r"discovery.?load|rate.?limit", re.I),
        )


if __name__ == "__main__":
    unittest.main()
