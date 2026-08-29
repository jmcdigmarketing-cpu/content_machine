"""Run 74: two gates must not disagree about the same phrase.

The script opened a pivot with "But here's the thing", and the run reported both
of these, four lines apart:

    [WARNING] persona lint: but here's the thing
    ✓ original_insight: has an authorial take ('here's the thing')

`core/persona_lint.py` bans it, `core/content_engine.py` bans it *in the prompt*,
and `core/authenticity.py` counted it as evidence of an authorial take — which is
why the run scored authenticity 100/100. A gate that rewards what another gate
forbids does not measure anything; it launders the defect into an A grade.

The prompt's banned list is the authority: it is what the model is told.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from core.authenticity import _INSIGHT_MARKERS
from core.persona_lint import _FILLER_PHRASES

_ENGINE = Path(__file__).resolve().parents[1] / "core" / "content_engine.py"


def _prompt_banned_phrases() -> set[str]:
    """Phrases the script prompt tells the model never to write."""
    text = _ENGINE.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if "Banned verbatim:" in ln)
    return {
        phrase.lower() for phrase in re.findall(r'"([^"]+)"', line.split("Banned verbatim:")[1])
    }


class TestNoPhraseIsBothRewardedAndBanned(unittest.TestCase):
    def test_the_filler_linter_and_the_insight_scorer_do_not_overlap(self):
        overlap = [
            marker
            for marker in _INSIGHT_MARKERS
            for filler in _FILLER_PHRASES
            if marker in filler or filler in marker
        ]
        self.assertEqual(overlap, [], f"rewarded and banned at once: {overlap}")

    def test_no_insight_marker_is_banned_by_the_script_prompt(self):
        banned = _prompt_banned_phrases()
        overlap = [
            marker
            for marker in _INSIGHT_MARKERS
            for phrase in banned
            if marker in phrase or phrase in marker
        ]
        self.assertEqual(overlap, [], f"prompt bans what authenticity rewards: {overlap}")


class TestTheRun74Phrase(unittest.TestCase):
    def test_heres_the_thing_no_longer_earns_an_authorial_take(self):
        for marker in _INSIGHT_MARKERS:
            self.assertNotIn("the thing", marker, marker)

    def test_the_linter_still_bans_it(self):
        """Removing the reward must not quietly remove the prohibition too."""
        from core.persona_lint import lint_persona_script

        hits = lint_persona_script("But here's the thing, the meta is dead.", channel_id="tapin")
        self.assertIn("but here's the thing", hits)


class TestTheInsightScorerStillWorks(unittest.TestCase):
    def test_plenty_of_markers_remain(self):
        self.assertGreater(len(_INSIGHT_MARKERS), 15)

    def test_a_real_authorial_take_is_still_recognised(self):
        from core.authenticity import _insight_check

        self.assertTrue(_insight_check("Mark my words, Rockstar delays this to spring.").passed)


if __name__ == "__main__":
    unittest.main()
