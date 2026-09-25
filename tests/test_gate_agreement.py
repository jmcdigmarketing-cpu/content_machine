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


_VARIANTS = Path(__file__).resolve().parents[1] / "apis" / "topic_variants.py"


def _angle_prompt_banned_phrases() -> set[str]:
    """Headline templates the ANGLE prompt tells the model never to write.

    Deliberately not the single-line trick `_prompt_banned_phrases` uses: this
    list wraps across two source lines, and a single-line reader silently drops
    the second half — which is where "my hot take" lives, the phrase this whole
    module exists to police. `TestExtractorsSeeWhatTheyClaimTo` guards that.
    """
    text = _VARIANTS.read_text(encoding="utf-8")
    start = text.index("BANNED headline templates:")
    # The bullet ends at the first period-quote that closes the list.
    body = text[start : text.index('".', start) + 2]
    return {phrase.lower() for phrase in re.findall(r'"([^"]+)"', body)}


def _engine_banned_jargon() -> set[str]:
    """The script prompt's *other* ban list (`BANNED - never write these`).

    The original test read only the "Banned verbatim:" line; this one has never
    been checked against any reward list.
    """
    text = _ENGINE.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if "BANNED — never write these" in ln)
    return {phrase.lower() for phrase in re.findall(r'"([^"]+)"', line)}


def _ban_vocabulary() -> set[str]:
    """Every phrase some component forbids, from all four ban lists."""
    from core.title_generator import _SLOP_PATTERNS

    return (
        {p.lower() for p in _SLOP_PATTERNS}
        | _angle_prompt_banned_phrases()
        | _engine_banned_jargon()
        | _prompt_banned_phrases()
    )


def _collides(reward: str, banned: str) -> bool:
    """Whether rewarding `reward` contradicts forbidding `banned`.

    Phrase-level, not naive substring. `_CURIOSITY` contains bare English words
    ("nobody", "actually", "biggest") that appear inside banned templates by
    coincidence; banning those outright from every hook would be wrong, and
    flagging them here would bury the four real collisions in noise. A reward
    only collides when it is itself a multi-word phrase.
    """
    if len(reward.split()) < 2:
        return False
    return reward in banned or banned in reward


class TestExtractorsSeeWhatTheyClaimTo(unittest.TestCase):
    """A source-scraping guard that silently finds nothing passes every test
    below it. These assertions are what make the rest of this module honest."""

    def test_the_angle_prompt_list_includes_its_second_line(self):
        phrases = _angle_prompt_banned_phrases()
        self.assertIn("my hot take", phrases)
        self.assertIn("just broke the league", phrases)
        self.assertGreaterEqual(len(phrases), 6, phrases)

    def test_the_engine_jargon_list_is_found(self):
        phrases = _engine_banned_jargon()
        self.assertIn("at a crossroads", phrases)
        self.assertGreaterEqual(len(phrases), 10, phrases)

    def test_the_ban_vocabulary_spans_all_four_lists(self):
        vocab = _ban_vocabulary()
        self.assertIn("this changes everything", vocab)  # title_generator
        self.assertIn("my hot take", vocab)  # angle prompt
        self.assertIn("at a crossroads", vocab)  # engine jargon
        self.assertIn("but here's the thing", vocab)  # engine verbatim


class TestTheHookScorerDoesNotPayForBannedClickbait(unittest.TestCase):
    """`hook_score` is the single heaviest report-card component (0.28,
    `core/video_grade.py`). It awards +15 for `_CURIOSITY` and +10 for
    `_STAKES` — and four of those terms are templates two other components
    reject outright. The grade pays for what the pipeline forbids.
    """

    def test_no_multiword_curiosity_term_is_banned_elsewhere(self):
        from core.hook_score import _CURIOSITY

        vocab = _ban_vocabulary()
        overlap = sorted({r for r in _CURIOSITY for b in vocab if _collides(r.strip().lower(), b)})
        self.assertEqual(overlap, [], f"hook_score rewards banned phrases: {overlap}")

    def test_scoring_a_banned_template_awards_no_clickbait_bonus(self):
        """Behavioural: the real scorer, on the real banned strings."""
        from core.hook_score import score_hook

        paid = {"curiosity / contradiction", "high stakes"}
        for banned in ("nobody's talking about", "you won't believe", "this changes everything"):
            with self.subTest(banned=banned):
                hs = score_hook(f"{banned} what Rockstar just did.")
                bonuses = [f"{label} +{d}" for label, d in hs.reasons if d > 0 and label in paid]
                self.assertEqual(bonuses, [], f"'{banned}' earned {bonuses}")


class TestTheInsightScorerDoesNotPayForBannedClickbait(unittest.TestCase):
    def test_no_multiword_insight_marker_is_banned_elsewhere(self):
        vocab = _ban_vocabulary()
        overlap = sorted(
            {m for m in _INSIGHT_MARKERS for b in vocab if _collides(m.strip().lower(), b)}
        )
        self.assertEqual(overlap, [], f"authenticity rewards banned phrases: {overlap}")


class TestThePromptDoesNotTeachAPhraseTheTitleCleanerRejects(unittest.TestCase):
    """Self-contained, needs no list comparison. `core/content_engine.py` offers
    "This changes everything for the division." as a model strong hook, and
    `title_generator._clean_title` discards any title matching
    "this changes everything". The prompt demonstrates what the next stage bins.
    """

    def test_the_example_strong_hooks_survive_the_title_cleaner(self):
        from core.title_generator import _clean_title

        text = _ENGINE.read_text(encoding="utf-8")
        line = next(ln for ln in text.splitlines() if "Strong hooks:" in ln)
        examples = re.findall(r'"([^"]+)"', line.split("Strong hooks:")[1])
        self.assertGreaterEqual(len(examples), 2, f"extractor found {examples}")

        rejected = [
            ex for ex in examples if _clean_title(ex, fallback="__FALLBACK__") == "__FALLBACK__"
        ]
        self.assertEqual(rejected, [], f"prompt teaches hooks the title cleaner bins: {rejected}")


if __name__ == "__main__":
    unittest.main()
