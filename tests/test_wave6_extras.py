"""Wave 6 extras: verified chapter timings and title/script consistency.

Was `_wave6_extras.py`, named to dodge `unittest discover` while the wave was
uncommitted. Renamed on commit -- a test file the runner never collects is a
test that does not exist, and this one guards two shipped behaviours.
"""

from __future__ import annotations

import unittest
from typing import ClassVar
from unittest.mock import patch


class TestVerifiedChapterTimings(unittest.TestCase):
    SCRIPT = "Opening context. The second point matters. Final consequence."

    def test_chapters_use_the_real_start_time_of_each_sentence(self):
        from core.chapters import chapter_block

        words = [
            {"word": "Opening", "start": 0.0, "end": 0.5},
            {"word": "context.", "start": 0.5, "end": 1.0},
            {"word": "The", "start": 20.0, "end": 20.2},
            {"word": "second", "start": 20.2, "end": 20.5},
            {"word": "point", "start": 20.5, "end": 20.8},
            {"word": "matters.", "start": 20.8, "end": 21.2},
            {"word": "Final", "start": 40.0, "end": 40.3},
            {"word": "consequence.", "start": 40.3, "end": 41.0},
        ]
        block = chapter_block(
            self.SCRIPT,
            duration=60.0,
            length_choice="4",
            word_timings=words,
        )
        lines = block.splitlines()
        self.assertGreaterEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("0:00"))
        self.assertTrue(any(line.startswith("0:20") for line in lines))
        self.assertTrue(any(line.startswith("0:40") for line in lines))

    def test_missing_word_timings_still_span_the_duration(self):
        from core.chapters import chapter_block

        block = chapter_block(self.SCRIPT, duration=60.0, length_choice="4")
        self.assertIn("0:00", block)
        self.assertIn("0:20", block)


class TestTitleScriptConsistency(unittest.TestCase):
    def test_a_title_that_assigns_the_action_to_the_wrong_actor_fails(self):
        from core.youtube_meta import check_title_script_consistency

        class _Claim:
            def __init__(self, claim: str):
                self.claim = claim

        class _Verification:
            unsupported: ClassVar[list] = [_Claim("Jones beat Pereira")]
            total = 1

        with patch("core.claim_verifier.verify_claims", return_value=_Verification()):
            check = check_title_script_consistency(
                "Pereira beat Jones",
                "Jones beat Pereira at UFC 320.",
                topic="UFC 320",
            )

        self.assertEqual(check["status"], "failed")
        self.assertFalse(check["passed"])
        self.assertTrue(check["warnings"])

    def test_unavailable_when_the_verifier_cannot_run(self):
        from core.youtube_meta import check_title_script_consistency

        with patch("core.claim_verifier.verify_claims", side_effect=RuntimeError("down")):
            check = check_title_script_consistency(
                "Jones beat Pereira",
                "Jones beat Pereira at UFC 320.",
            )

        # #748: a verifier miss used to persist unavailable. Names in the title
        # are in the script, so the heuristic now passes.
        self.assertEqual(check["status"], "passed")
        self.assertTrue(check["passed"])
