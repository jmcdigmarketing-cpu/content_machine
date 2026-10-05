"""#551: a date arithmetic check - "18 months since" must match the dates it counts from.

Grounding checks that a script's names and numbers appear in the facts; nothing checked the
arithmetic between them. "It's been 18 months since the trade" passes when the facts date the
trade 8 months ago, and "ten years since 2019" passes on its own. `core/facts/date_math`
reads each elapsed-time phrase ("N days/weeks/months/years since/ago/after/later", "for N
years") and checks it:

- against a date in the same sentence ("since 2019", "since March 2025") - always;
- against the facts: a fact line holding a date (written out, ISO or a bare year) that shares
  a topic word with the sentence. It is flagged only when such a line exists and none of its
  dates fits within tolerance (one unit, or a quarter of the span when that is more).

What it flags joins the ungrounded specifics, so the reground pass sees it, and the run's
quality keeps it as `date_mismatches` (the dossier prints them).
"""

from __future__ import annotations

import json
import unittest
from datetime import date
from types import SimpleNamespace

TODAY = date(2026, 10, 5)
TRADE = "The Lakers traded for Luka Doncic on February 2, 2025."


class InSentenceTests(unittest.TestCase):
    def _check(self, script, facts=""):
        from core.facts.date_math import find_elapsed_mismatches

        return find_elapsed_mismatches(script, facts, today=TODAY)

    def test_years_since_a_year(self):
        self.assertEqual(len(self._check("It's been ten years since 2019 for this franchise.")), 1)
        self.assertEqual(self._check("It's been seven years since 2019 for this franchise."), [])

    def test_months_since_a_month(self):
        self.assertEqual(len(self._check("It has been 3 months since March 2025.")), 1)
        self.assertEqual(self._check("It has been 19 months since March 2025."), [])

    def test_the_flag_says_what_the_dates_give(self):
        got = self._check("It's been ten years since 2019.")
        self.assertIn("ten years since", got[0])
        self.assertIn("7", got[0])


class AgainstFactsTests(unittest.TestCase):
    def _check(self, script, facts):
        from core.facts.date_math import find_elapsed_mismatches

        return find_elapsed_mismatches(script, facts, today=TODAY)

    def test_a_wrong_count_against_a_dated_fact(self):
        got = self._check("It's been 6 months since the Lakers traded for Doncic.", TRADE)
        self.assertEqual(len(got), 1)
        self.assertIn("2025-02-02", got[0])

    def test_a_right_count_passes(self):
        self.assertEqual(
            self._check("It's been 18 months since the Lakers traded for Doncic.", TRADE), []
        )
        self.assertEqual(self._check("Twenty months ago the Lakers traded for Doncic.", TRADE), [])

    def test_an_iso_date_and_an_accent(self):
        facts = "Ghost of Yōtei released 2026-10-02 (Wikidata, as of 2026-10-05)"
        got = self._check("Ghost of Yotei came out three weeks ago and it is huge.", facts)
        self.assertEqual(len(got), 1)
        self.assertEqual(self._check("Ghost of Yotei came out three days ago.", facts), [])

    def test_a_bare_year_counts_for_years(self):
        facts = "Elden Ring was released in 2022."
        self.assertEqual(len(self._check("Elden Ring came out ten years ago.", facts)), 1)
        self.assertEqual(self._check("Elden Ring came out four years ago.", facts), [])

    def test_nothing_to_check_against_says_nothing(self):
        self.assertEqual(self._check("It's been 6 months since he signed.", TRADE), [])
        self.assertEqual(self._check("Six months since the trade, nothing changed.", ""), [])

    def test_no_elapsed_phrase_says_nothing(self):
        self.assertEqual(self._check("The Lakers traded for Doncic in a stunner.", TRADE), [])


class WiringTests(unittest.TestCase):
    def test_it_joins_the_ungrounded_specifics(self):
        from core.facts.grounding import find_ungrounded_entities

        got = find_ungrounded_entities("It's been 40 years since 2019 for them.", "")
        self.assertTrue(any("40 years since" in g for g in got))

    def test_quality_keeps_it_and_the_dossier_prints_it(self):
        from unittest.mock import patch

        from core.run_ledger import render_dossier
        from core.run_quality import build_quality

        quality = build_quality(
            script="It's been 40 years since 2019 for this team.",
            features={"grounding_text": "", "facts": ""},
            channel_id="tapin",
        )
        self.assertTrue(any("40 years since" in d for d in quality["date_mismatches"]))
        record = SimpleNamespace(
            id=7, channel_id="tapin", status="done", selected_topic="t", input_topic="t",
            title="T", composite_score=50.0, abort_reason="", features_json="{}",
            quality_json=json.dumps(quality), timings_json="{}")  # fmt: skip
        with patch("storage.repositories.content_runs.get_content_run_repository",
                   return_value=type("Repo", (), {"get": lambda self, i: record})()):  # fmt: skip
            text = render_dossier(7)
        self.assertIn("date check", text)


if __name__ == "__main__":
    unittest.main()
