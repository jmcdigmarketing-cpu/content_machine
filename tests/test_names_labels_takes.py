"""Wave 98 (#1224-#1226): what the angle and the authenticity check read - runs 158 and 159.

- Run 159, "New York Jets at New England Patriots", came back as the angle "New York Jets vs
  England Patriots" and the title "... England's AFC East Clash". `_subject_terms` told the angle
  prompt "Keep the seed's subject: York, Jets, England".
- Run 158's angle kept its label, "Long-term outlook: Pokemon's Snorlax and Bewear pillows ...":
  the type is `long_term_outlook` and the hyphen stopped the match. Its title ended in the model's
  own "…" ("... signal positive outlook…", 94 characters).
- Run 158's script says "If this sells, every franchise with a cozy mascot suddenly has a
  blueprint" and "Watch whether the therapist credit survives" - read as "no take found".
- Run 159 (intent explainer) and 150 (plan): the engine adds no beat to a calm draft, and the
  check then held both for "no take found". The operator (2026-10-16): give them a "what to
  watch" beat.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

JETS = "New York Jets at New England Patriots"

# ---- #1224: a team name stays whole ---------------------------------------------------------------


class TeamNameTests(unittest.TestCase):
    def test_run159s_subjects_are_the_two_teams(self):
        from apis.topic_variants import _subject_terms

        terms = _subject_terms(JETS)
        self.assertIn("New York Jets", terms)
        self.assertIn("New England Patriots", terms)
        self.assertNotIn("England", terms)

    def test_the_prompt_never_says_york_jets_england(self):
        from apis.topic_variants import _anchor_rules

        rules = _anchor_rules(JETS, None)
        self.assertIn("New England Patriots", rules)
        self.assertNotIn("York, Jets, England", rules)

    def test_a_single_name_still_counts(self):
        from apis.topic_variants import _subject_terms

        self.assertIn("Kape", _subject_terms("MMA divisional rankings: Kape punches his ticket"))

    def test_england_patriots_is_a_broken_name(self):
        from core.title_generator import broken_place_name

        self.assertEqual(
            broken_place_name("New York Jets vs England Patriots: How playoff races shape it"),
            "New England Patriots",
        )
        self.assertEqual(broken_place_name("Why the York Jets keep losing"), "New York Jets")

    def test_whole_names_and_short_names_pass(self):
        from core.title_generator import broken_place_name

        for title in (
            "Jets vs Patriots: How playoff races shape this AFC East clash",
            "New York Jets at New England Patriots preview",
            "Trail Blazers rookies stand out in Portland's opener",
            "England's World Cup squad named",
        ):
            with self.subTest(title=title):
                self.assertEqual(broken_place_name(title), "")


# ---- #1225: a hyphenated label is a label, and the model does not cut a title ------------------------


class LabelTests(unittest.TestCase):
    def test_run158s_label_is_dropped(self):
        from apis.topic_variants import _clean_angle_lines

        raw = "1. Long-term outlook: Pokemon's Snorlax and Bewear pillows could pave the way"
        self.assertEqual(
            _clean_angle_lines(raw, ["long_term_outlook"]),
            ["Pokemon's Snorlax and Bewear pillows could pave the way"],
        )

    def test_a_subject_before_a_colon_stays(self):
        from apis.topic_variants import _clean_angle_lines

        raw = "Chargers: the 0-4 start and the road back"
        self.assertEqual(_clean_angle_lines(raw, ["long_term_outlook"]), [raw])

    def test_the_models_ellipsis_is_dropped(self):
        from core.title_generator import _clean_title

        title = (
            "Pokemon's Snorlax and Bewear body pillows designed by sleep therapist "
            "signal positive outlook…"
        )
        cleaned = _clean_title(title, fallback="x")
        self.assertFalse(cleaned.endswith("…"), cleaned)
        self.assertTrue(cleaned.endswith("outlook"), cleaned)

    def test_a_cut_title_waits_for_a_person(self):
        from core.batch_review import PendingDraft, unattended_block_reason

        meta = {"run_id": 158, "topic": "Pokemon body pillows",
                "title": "Pokemon's body pillows signal positive outlook...",
                "created_at": __import__("datetime").datetime.now().isoformat(),
                "claim_verification": {"unsupported": [], "claims": []}}  # fmt: skip
        draft = PendingDraft(folder="", meta=meta, script="s")
        with patch("core.run_features.load_features", return_value={}):
            self.assertIn("cut off", unattended_block_reason(draft))


# ---- #1226: the insight check reads more takes, and a calm draft gets a beat -----------------------

RUN158 = (
    "That's a different category. If this sells, every franchise with a cozy mascot suddenly has a "
    "blueprint: hire a specialist, slap a character on it, sell rest instead of plastic. Watch "
    "whether the therapist credit survives past this first drop."
)
RECAP = (
    "Sunday, October 18, 1 PM ET, Gillette Stadium. New England is 3-2. The Jets are 1-4. "
    "Drake Maye threw for 374 yards last week."
)


class InsightTests(unittest.TestCase):
    def test_run158s_take_is_read(self):
        from core.authenticity import has_insight

        self.assertTrue(has_insight(RUN158))

    def test_a_recap_is_still_a_recap(self):
        from core.authenticity import has_insight

        self.assertFalse(has_insight(RECAP))

    def _inject(self, **kwargs):
        from core import content_engine

        beat = RECAP + " Watch whether the Jets' rush gets home early - that decides Sunday."
        with (
            patch.dict(os.environ, {"INSIGHT_INJECTION_ENABLED": "true"}),
            patch.object(content_engine, "_call_content_llm", return_value={"script": beat}) as llm,
        ):
            out = content_engine._maybe_inject_insight(
                RECAP,
                "- New England is 3-2",
                "How playoff races shape this AFC East clash",
                **kwargs,
            )
        return out, llm

    def test_run159_an_explainer_gets_a_what_to_watch_beat(self):
        out, llm = self._inject(intent="explainer")
        self.assertIn("Watch whether", out)
        prompt = llm.call_args.args[0]
        self.assertIn("what to watch", prompt)
        self.assertIn("not a contrarian hot take", prompt)

    def test_your_own_idea_is_left_as_written(self):
        out, llm = self._inject(intent="plan", own_idea=True)
        self.assertEqual(out, RECAP)
        llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
