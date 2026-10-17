"""#545: a franchise with a recorded correction says so in the next script.

The sentence names the claim. The veto (decisions §29) ignores that one sentence
and still blocks a second sentence that states the claim as fact. The store is a
temp file — never data/negative_facts.json.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_CLAIM = "Pereira retired in March 2024"
_UFC = "UFC Contender Series prospects"
_LAKERS = "Why the Lakers are not a contender yet"


class CorrectionBeatTests(unittest.TestCase):
    def test_a_ufc_correction_is_said_and_does_not_veto(self):
        from core.negative_facts import (
            correction_beat,
            matching_negatives,
            record_negative,
            with_correction_beat,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "negative_facts.json"
            with patch("core.negative_facts.STORE_PATH", store):
                record_negative("ufc", _CLAIM, reason="source retracted")
                beat = correction_beat(_UFC, "tapin")
                script = with_correction_beat(
                    "The division is still open this weekend.",
                    _UFC,
                    "tapin",
                )
                only_the_beat = matching_negatives(script, franchise="ufc")
                restated = matching_negatives(
                    f"Pereira retired in March 2024 and the division moved on. {beat}",
                    franchise="ufc",
                )
        self.assertEqual(beat, f"What I got wrong last time: {_CLAIM}.")
        self.assertIn(beat, script)
        self.assertEqual(only_the_beat, [])
        self.assertIn(_CLAIM, restated)

    def test_a_lakers_topic_does_not_inherit_a_ufc_correction(self):
        from core.negative_facts import record_negative, with_correction_beat

        script = "The Lakers are not a contender yet."
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "negative_facts.json"
            with patch("core.negative_facts.STORE_PATH", store):
                record_negative("ufc", _CLAIM, reason="source retracted")
                got = with_correction_beat(script, _LAKERS, "tapin")
        self.assertEqual(got, script)

    def test_no_correction_leaves_the_script_unchanged(self):
        from core.negative_facts import with_correction_beat

        script = "The division is still open."
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "negative_facts.json"
            with patch("core.negative_facts.STORE_PATH", store):
                got = with_correction_beat(script, _UFC, "tapin")
        self.assertIs(got, script)
