"""#877 / #878: run 99's title shipped flagged, built from uncertain vault facts.

The title "UFC week 2: Gane stops Pereira, Dana White bans White House fights" sat on
a Contender Series contracts script. The title/script check flagged all of it and the
upload went ahead, because the check only warned. The facts behind it came from
pressing Enter at "Use uncertain facts? [Enter=all ...]".

Now a flagged title is regenerated once from the script alone, a title still flagged
must be confirmed before it is queued, and Enter at the uncertain prompt takes none.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core import content_engine as ce
from core.facts.store import FactRecord

RUN99_TITLE = "UFC week 2: Gane stops Pereira, Dana White bans White House fights"
SCRIPT = (
    "Dana White handed out five contracts on week two of the Contender Series. "
    "The standout was a flyweight who finished his fight in the first round. "
    "Two heavyweights also earned deals after a close decision."
)
GOOD_TITLE = "Contender Series Week 2: Five Contracts, One First-Round Finish"


def _package(titles, check):
    calls = []

    def fake_title(**kwargs):
        calls.append(kwargs)
        return titles[min(len(calls) - 1, len(titles) - 1)]

    payload = {"script": SCRIPT, "title": "x", "description": "d", "tags": ["ufc"]}
    with (
        patch.object(ce, "enrich_facts", return_value="Dana White handed out five contracts."),
        patch.object(ce, "_call_content_llm", return_value=payload),
        patch.object(ce, "find_ungrounded_entities", return_value=[]),
        patch("core.claim_verifier.verify_claims", return_value=None),
        patch("core.title_generator.generate_title", side_effect=fake_title),
        patch("core.youtube_meta.check_title_script_consistency", side_effect=check),
    ):
        pkg = ce.generate_content_package(
            "UFC week 2",
            {},
            (20, 200),
            "2026-09-26",
            channel_id="tapin",
            length_choice="1",
            key_facts=["Gane stops Pereira at UFC Oklahoma City."],
        )
    return pkg, calls


def _check(title, script, *, topic=""):
    bad = title == RUN99_TITLE
    return {
        "status": "failed" if bad else "passed",
        "passed": not bad,
        "warnings": ["title contradicts or is not supported by the final script: Gane"]
        if bad
        else [],
        "total": 1,
    }


class TitleRegenerationTests(unittest.TestCase):
    def test_a_flagged_title_is_regenerated_from_the_script_alone(self):
        pkg, calls = _package([RUN99_TITLE, GOOD_TITLE], _check)
        self.assertEqual(pkg["title"], GOOD_TITLE)
        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[1].get("key_facts"), "the retry must not reuse the facts")
        self.assertEqual(pkg["title_script_check"]["status"], "passed")
        self.assertEqual(pkg["title_script_check"]["regenerated_from"], RUN99_TITLE)

    def test_a_title_still_flagged_stays_flagged(self):
        pkg, calls = _package([RUN99_TITLE, RUN99_TITLE], _check)
        self.assertEqual(len(calls), 2)
        self.assertEqual(pkg["title_script_check"]["status"], "failed")

    def test_a_clean_title_is_not_regenerated(self):
        _pkg, calls = _package([GOOD_TITLE], _check)
        self.assertEqual(len(calls), 1)


class UploadConfirmTests(unittest.TestCase):
    def _plan(self, answers, warnings):
        from core.ui import prompt_upload_plan

        inputs = iter(answers)
        with (
            patch("core.ui.display_upload_queue"),
            patch("analytics.post_timing.next_optimal_post_time", return_value=None),
            patch("analytics.post_timing.format_scheduled_local", return_value="soon"),
        ):
            return prompt_upload_plan(
                channel_id="tapin",
                topic="t",
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: next(inputs),
                title_warnings=warnings,
            )

    def test_enter_at_the_confirm_skips_a_flagged_title(self):
        plan = self._plan(["2", ""], ["title contradicts the script: Gane"])
        self.assertEqual(plan.mode, "skip")

    def test_y_at_the_confirm_queues_it(self):
        plan = self._plan(["2", "y", "1"], ["title contradicts the script: Gane"])
        self.assertEqual(plan.mode, "queue")

    def test_a_clean_title_is_not_asked_about(self):
        plan = self._plan(["2", "1"], [])
        self.assertEqual(plan.mode, "queue")


class UncertainFactsTests(unittest.TestCase):
    def _run(self, answer):
        from core.ui import prompt_key_facts_result

        inputs = iter(["", answer])
        records = [
            FactRecord(
                claim="Contender Series week 2 handed out five contracts.",
                relevance_score=0.82,
                relevance_band="confident",
            ),
            FactRecord(
                claim="Gane stops Pereira at UFC Oklahoma City.",
                uncertain=True,
                relevance_score=0.45,
                relevance_band="uncertain",
            ),
        ]
        with patch("core.obsidian_facts.load_fact_records", return_value=records):
            result = prompt_key_facts_result(
                "UFC week 2",
                "tapin",
                signals={},
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: next(inputs),
            )
        return result, records

    def test_enter_takes_no_uncertain_fact(self):
        result, records = self._run("")
        self.assertIn(records[0].claim, result.facts)
        self.assertNotIn(records[1].claim, result.facts)

    def test_a_takes_them_all(self):
        result, records = self._run("a")
        self.assertIn(records[1].claim, result.facts)

    def test_the_parser(self):
        from core.ui import parse_uncertain_choice

        self.assertEqual(parse_uncertain_choice(""), "none")
        self.assertEqual(parse_uncertain_choice("n"), "none")
        self.assertEqual(parse_uncertain_choice("a"), "all")
        self.assertEqual(parse_uncertain_choice("all"), "all")
        self.assertEqual(parse_uncertain_choice("2, 4"), [2, 4])


if __name__ == "__main__":
    unittest.main()
