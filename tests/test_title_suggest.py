"""#1050: the title's subject is checked against what people type into YouTube.

The Google Suggest signal runs on the whole topic sentence and came back empty for most runs
(cited in 0 of 6 scripts on 2026-10-10), so nothing ever compared a title with a search. This
asks YouTube's own suggest for the title's subject and says whether the title's words are among
what people type after it. The suite never reaches the network: `TITLE_SUGGEST` is off there
and every test passes its own `fetch`.

The default is `report` - the result is stored and shown, the title is left alone. The
operator's most repeated complaint is a title or angle that moved off their idea, so a reword
is opt-in (`TITLE_SUGGEST=reword`) and must pass every check the first title passed.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

SUGGESTIONS = [
    "chargers playoff chances",
    "chargers super bowl odds",
    "chargers schedule 2026",
    "chargers injury report",
]


class SuggestCheckTests(unittest.TestCase):
    def _check(self, title, suggestions=SUGGESTIONS, topic="can the chargers make the super bowl"):
        from core.title_generator import suggest_check

        return suggest_check(title, topic, fetch=lambda phrase: suggestions)

    def test_a_title_with_a_searched_phrase_is_searched(self):
        got = self._check("Chargers Super Bowl odds after the 0-4 start")
        self.assertEqual(got["status"], "searched")
        self.assertEqual(got["match"], "chargers super bowl odds")
        self.assertEqual(got["subject"], "Los Angeles Chargers")

    def test_a_title_nobody_types_is_unsearched_and_names_what_they_type(self):
        got = self._check("Chargers face a narrow path through a brutal autumn")
        self.assertEqual(got["status"], "unsearched")
        self.assertEqual(got["suggestions"][:2], SUGGESTIONS[:2])

    def test_the_subject_alone_is_not_a_match(self):
        """Every suggestion starts with the subject; sharing only that proves nothing."""
        got = self._check("Chargers: the long view")
        self.assertEqual(got["status"], "unsearched")

    def test_no_suggestions_says_so(self):
        self.assertEqual(self._check("Chargers odds", suggestions=[])["status"], "none")

    def test_a_failed_lookup_is_unavailable_never_a_verdict(self):
        self.assertEqual(self._check("Chargers odds", suggestions=None)["status"], "unavailable")

    def test_a_title_with_no_subject_is_not_looked_up(self):
        from core.title_generator import suggest_check

        fetch = MagicMock(return_value=SUGGESTIONS)
        got = suggest_check("why this is so hard", "why this is so hard", fetch=fetch)
        self.assertEqual(got["status"], "no_subject")
        fetch.assert_not_called()

    def test_the_line_reads_plainly(self):
        from core.title_generator import suggest_line

        line = suggest_line(self._check("Chargers face a narrow path through a brutal autumn"))
        self.assertIn("chargers playoff chances", line)
        self.assertEqual(suggest_line({"status": "unavailable"}), "")
        self.assertIn("people search", suggest_line(self._check("Chargers Super Bowl odds")))


class SuggestFetchTests(unittest.TestCase):
    def test_youtube_suggest_is_asked_and_parsed(self):
        from apis import autocomplete_api

        response = MagicMock(status_code=200)
        response.json.return_value = ["chargers", ["chargers playoff chances", "chargers news"]]
        with patch.object(autocomplete_api.requests, "get", return_value=response) as get:
            got = autocomplete_api.youtube_suggestions("Los Angeles Chargers")
        self.assertEqual(got, ["chargers playoff chances", "chargers news"])
        self.assertEqual(get.call_args.kwargs["params"]["ds"], "yt")

    def test_any_failure_is_none(self):
        from apis import autocomplete_api

        with patch.object(autocomplete_api.requests, "get", side_effect=OSError("down")):
            self.assertIsNone(autocomplete_api.youtube_suggestions("x"))
        with patch.object(
            autocomplete_api.requests, "get", return_value=MagicMock(status_code=429)
        ):
            self.assertIsNone(autocomplete_api.youtube_suggestions("x"))


class SuggestModeTests(unittest.TestCase):
    def _apply(self, mode, title, reword=None, accept=True):
        from core import title_generator

        with (
            patch.dict(os.environ, {"TITLE_SUGGEST": mode}),
            patch.object(title_generator, "_suggest_fetch", return_value=SUGGESTIONS),
            patch.object(title_generator, "_complete_or_none", return_value=reword) as llm,
        ):
            out = title_generator.apply_suggest(
                title,
                "can the chargers make the super bowl",
                accept=lambda candidate: accept,
            )
        return out, llm

    TITLE = "Chargers face a narrow path through a brutal autumn"

    def test_off_looks_nothing_up(self):
        (title, report), llm = self._apply("off", self.TITLE)
        self.assertEqual((title, report), (self.TITLE, {}))
        llm.assert_not_called()

    def test_report_keeps_the_title_and_records_the_finding(self):
        (title, report), llm = self._apply("report", self.TITLE)
        self.assertEqual(title, self.TITLE)
        self.assertEqual(report["status"], "unsearched")
        llm.assert_not_called()

    def test_reword_takes_a_searched_title_that_passes_the_checks(self):
        (title, report), _llm = self._apply(
            "reword", self.TITLE, reword="Chargers playoff chances after the 0-4 start"
        )
        self.assertEqual(title, "Chargers playoff chances after the 0-4 start")
        self.assertEqual(report["reworded_from"], self.TITLE)
        self.assertEqual(report["status"], "searched")

    def test_reword_is_dropped_when_a_check_fails(self):
        (title, report), _llm = self._apply(
            "reword", self.TITLE, reword="Chargers playoff chances are dead", accept=False
        )
        self.assertEqual(title, self.TITLE)
        self.assertEqual(report["status"], "unsearched")
        self.assertNotIn("reworded_from", report)

    def test_reword_is_dropped_when_it_is_still_not_searched(self):
        (title, _report), _llm = self._apply("reword", self.TITLE, reword="Chargers: the long view")
        self.assertEqual(title, self.TITLE)

    def test_a_searched_title_is_never_reworded(self):
        (title, report), llm = self._apply("reword", "Chargers Super Bowl odds after 0-4")
        self.assertEqual(title, "Chargers Super Bowl odds after 0-4")
        self.assertEqual(report["status"], "searched")
        llm.assert_not_called()

    def test_the_suite_runs_with_it_off(self):
        self.assertEqual(os.environ.get("TITLE_SUGGEST"), "off")


class SuggestShownTests(unittest.TestCase):
    def test_the_review_screen_prints_the_finding(self):
        from core.ui import display_fact_engine_report

        printed: list[str] = []
        features = {
            "title_suggest": {
                "status": "unsearched",
                "subject": "Illia Topuria",
                "suggestions": ["ilia topuria", "ilia topuria highlights"],
            }
        }
        display_fact_engine_report(features, print_fn=printed.append)
        self.assertTrue(any("ilia topuria highlights" in line for line in printed), printed)

    def test_no_finding_prints_nothing_about_the_title(self):
        from core.ui import display_fact_engine_report

        printed: list[str] = []
        display_fact_engine_report(
            {"title_suggest": {"status": "unavailable"}}, print_fn=printed.append
        )
        self.assertFalse(any("Title:" in line for line in printed), printed)


if __name__ == "__main__":
    unittest.main()
