"""Run 74: nothing measured the script again after the passes that shorten it.

The run targeted Long (300-750 words), expanded once, and shipped **277 words
[SHORT]** — and still graded A (87/100). The expansion loop in
`generate_content_package` runs *before* `_maybe_improve_hook`,
`_maybe_recenter_on_key_facts`, `_maybe_inject_insight` and
`_maybe_reground_script`, and every one of those can remove text. The loop's exit
condition was therefore checked against a script that no longer existed by the
time the operator saw it.

Re-checking after those passes is safe only if it cannot undo them: regrounding
has already run at this point, so a late expansion that reintroduces unsupported
specifics is reverted rather than shipped.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.content_engine import _relength_after_postprocessing

SHORT = "Word " * 200
LONG = "Word " * 320


def _relength(script, *, attempts_left=2, ungrounded=None, grounding_text="facts"):
    return _relength_after_postprocessing(
        script,
        topic="GTA 6 extended look",
        min_words=300,
        max_words=750,
        length_choice="3",
        attempts_left=attempts_left,
        grounding_text=grounding_text,
        ungrounded=list(ungrounded or []),
    )


class TestAShortScriptIsExpandedAgain(unittest.TestCase):
    def test_a_script_under_target_triggers_another_expansion(self):
        with (
            patch("core.content_engine._expand_script", return_value=LONG) as expand,
            patch("core.content_engine.find_ungrounded_entities", return_value=[]),
        ):
            script, ungrounded = _relength(SHORT)
        self.assertEqual(script, LONG)
        self.assertEqual(ungrounded, [])
        self.assertEqual(expand.call_count, 1)

    def test_a_script_already_on_target_is_left_alone(self):
        with patch("core.content_engine._expand_script") as expand:
            script, _ = _relength(LONG)
        self.assertEqual(script, LONG)
        expand.assert_not_called()

    def test_no_attempts_left_means_no_expansion(self):
        with patch("core.content_engine._expand_script") as expand:
            script, _ = _relength(SHORT, attempts_left=0)
        self.assertEqual(script, SHORT)
        expand.assert_not_called()

    def test_it_gives_up_when_expansion_stops_helping(self):
        with (
            patch("core.content_engine._expand_script", side_effect=lambda **_k: SHORT) as expand,
            patch("core.content_engine.find_ungrounded_entities", return_value=[]),
        ):
            script, _ = _relength(SHORT, attempts_left=3)
        self.assertEqual(script, SHORT)
        self.assertEqual(expand.call_count, 1)  # unchanged output -> stop, do not burn calls


class TestItCannotUndoGrounding(unittest.TestCase):
    """Regrounding has already run; a late expansion must not walk it back."""

    def test_an_expansion_that_invents_specifics_is_reverted(self):
        with (
            patch("core.content_engine._expand_script", return_value=LONG),
            patch(
                "core.content_engine.find_ungrounded_entities",
                return_value=["Slim Jim Pro", "Rockstar Tokyo"],
            ),
        ):
            script, ungrounded = _relength(SHORT, ungrounded=[])
        self.assertEqual(script, SHORT)
        self.assertEqual(ungrounded, [])

    def test_an_expansion_that_holds_the_line_is_kept(self):
        with (
            patch("core.content_engine._expand_script", return_value=LONG),
            patch("core.content_engine.find_ungrounded_entities", return_value=["Known gap"]),
        ):
            script, ungrounded = _relength(SHORT, ungrounded=["Known gap"])
        self.assertEqual(script, LONG)
        self.assertEqual(ungrounded, ["Known gap"])


class TestFailureIsNeverFatal(unittest.TestCase):
    def test_an_expansion_error_leaves_the_script_untouched(self):
        with patch("core.content_engine._expand_script", side_effect=RuntimeError("boom")):
            script, ungrounded = _relength(SHORT, ungrounded=["Known gap"])
        self.assertEqual(script, SHORT)
        self.assertEqual(ungrounded, ["Known gap"])


if __name__ == "__main__":
    unittest.main()
