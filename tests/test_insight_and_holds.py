"""Wave 93 (#1210-#1211): why clean drafts wait, and what must not render tonight.

Read on 2026-10-15: the authenticity check's insight test said "no opinion/prediction/analysis
beat - reads as a neutral recap" for runs 149, 150, 151, 152 and 155, so they sat at "review"
and overnight would render none of them. Run 151 says "Here's my call anyway. I'm taking the
double"; 149 "Now here's the part that actually matters"; 152 "That's the mechanism people
miss". The check is a phrase list, and it had none of these.

Tonight's one planned render was run 153, drafted from the arc seed "Shavkat Rakhmonov week 4"
before #1205 ("So week four is progress without a finish line."). And run 149's stored title
still reads "... Denver Loss Angeles ..." - #1181 checks a title only as it is written.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

RUN151 = (
    "Wembanyama is +200 for MVP - no first-time MVP priced this short has ever won. That's the "
    "trap. Here's my call anyway. I'm taking the double."
)
RUN149 = (
    "Harbaugh stood up and took the blame himself. Now here's the part that actually matters. "
    "Harbaugh's message to Justin Herbert was two words: be better."
)
RUN152 = (
    "Cleveland isn't clean either. That's the mechanism people miss: this game isn't decided by "
    "who's better on paper, it's decided by who's actually available."
)
RUN151_THIRD = (
    "Shai Gilgeous-Alexander sits at +450. I have him third. That's disrespect, and I'll say it."
)
RECAP = (
    "The Chiefs beat the Bills 24-20 on Sunday. Patrick Mahomes threw two touchdowns. The "
    "defense held on the final drive."
)


# ---- #1210: the insight check reads the stance the scripts take --------------------------------


class InsightTests(unittest.TestCase):
    def test_run151_my_call_is_a_take(self):
        from core.authenticity import has_insight

        self.assertTrue(has_insight(RUN151))
        self.assertTrue(has_insight(RUN151_THIRD))

    def test_run149_the_part_that_matters_is_a_take(self):
        from core.authenticity import has_insight

        self.assertTrue(has_insight(RUN149))

    def test_run152_what_people_miss_is_a_take(self):
        from core.authenticity import has_insight

        self.assertTrue(has_insight(RUN152))

    def test_a_recap_is_still_a_recap(self):
        from core.authenticity import has_insight

        self.assertFalse(has_insight(RECAP))

    def test_no_banned_phrase_counts_as_a_stance(self):
        from core.authenticity import _STANCE_PATTERNS
        from core.persona_lint import _FILLER_PHRASES

        banned = [*_FILLER_PHRASES, "but here's the thing", "but wait, there's more",
                  "here's the kicker", "let that sink in", "my hot take"]  # fmt: skip
        hits = [(p.pattern, b) for p in _STANCE_PATTERNS for b in banned if p.search(b)]
        self.assertEqual(hits, [])


# ---- #1211: what must not render tonight ---------------------------------------------------------


def _draft(meta, run_id=153):
    from core.batch_review import PendingDraft

    folder = tempfile.mkdtemp()
    with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
        f.write("# Draft\n\n## Script\n\nA script.\n")
    base = {"run_id": run_id, "topic": "x", "title": "A fine title", "authenticity_verdict": "ok",
            "claim_verification": {"unsupported": [], "claims": []}}  # fmt: skip
    return PendingDraft(folder=folder, meta={**base, **meta}, script="A script.")


ARC_OFFERED = {"best_bet": {"offered": [
    {"topic": "Shavkat Rakhmonov week 4", "source": "arc"},
    {"topic": "Tennessee Titans at Indianapolis Colts", "source": "schedule"},
], "picked": 1}}  # fmt: skip


class HoldTests(unittest.TestCase):
    def test_run153_a_draft_from_the_arc_counter_waits(self):
        from core.batch_review import unattended_block_reason

        draft = _draft({"topic": "Shavkat Rakhmonov week 4"})
        with patch("core.run_features.load_features", return_value=ARC_OFFERED):
            reason = unattended_block_reason(draft)
        self.assertIn("arc counter", reason)
        self.assertIn("week 4", reason)

    def test_a_week_the_operator_typed_is_not_held(self):
        from core.batch_review import unattended_block_reason

        draft = _draft({"topic": "NFL week 6 picks"}, run_id=160)
        with patch("core.run_features.load_features", return_value=ARC_OFFERED):
            self.assertNotIn("arc counter", unattended_block_reason(draft))

    def test_run149_a_stored_title_that_broke_a_name_waits(self):
        from core.batch_review import unattended_block_reason

        title = "Chargers Hopeium: Harbaugh's Bold Move After Denver Loss Angeles Stays Optimistic"
        draft = _draft({"title": title, "topic": "Chargers Hopeium going into week 5"}, run_id=149)
        with patch("core.run_features.load_features", return_value={}):
            self.assertIn("Los Angeles", unattended_block_reason(draft))


if __name__ == "__main__":
    unittest.main()
