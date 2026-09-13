"""Wave 15: run 76 leftovers. Fail-first on unmodified 2421e15.

#534 title drift, #748 title/script unavailable, #746 Wiki Gta/Goy,
#747 autocomplete 400, #738 TTS-cap publish feeder.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

RUN76_SEED = (
    "GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting "
    "the hype mean, is a goy candidate a failure? Long form predictions and content "
    "analysis so far"
)
RUN76_ANGLE = "GTA 6 Will It Be the Best: The One Criterion That Decides It All"
RUN76_DRONES_TITLE = "Rockstar Fights Drones And Hackers To Protect GTA 6 Secrets"


class TestAnglePhraseSurvivesIntoTitle(unittest.TestCase):
    """#534. Run 76 selected the criterion angle and shipped the GameSpot drones title."""

    def test_generate_title_keeps_a_phrase_from_the_selected_angle(self):
        from core.title_generator import generate_title

        with patch(
            "core.title_generator.complete",
            return_value=RUN76_DRONES_TITLE,
        ):
            title = generate_title(
                script="Start with what we actually know about GTA 6.",
                topic=RUN76_ANGLE,
                seed_topic=RUN76_SEED,
                key_facts=["Rockstar is fighting drones and hackers to protect GTA 6 secrets."],
                channel_id="tapin",
            )
        low = title.lower()
        self.assertTrue(
            "criterion" in low or "will it be the best" in low,
            title,
        )


class TestTitleScriptCheckStillRuns(unittest.TestCase):
    """#748. verify_claims None used to persist unavailable; the check did not run."""

    def test_llm_miss_falls_back_to_a_real_title_vs_script_verdict(self):
        from core.youtube_meta import check_title_script_consistency

        with patch("core.llm_router.complete_json", side_effect=RuntimeError("extract down")):
            drifted = check_title_script_consistency(
                RUN76_DRONES_TITLE,
                "Start with what we actually know. Meeting the hype is the only criterion.",
                topic=RUN76_ANGLE,
            )
            aligned = check_title_script_consistency(
                "Jones beat Pereira",
                "Jones beat Pereira at UFC 320.",
                topic="UFC 320",
            )
        self.assertEqual(drifted["status"], "failed")
        self.assertFalse(drifted["passed"])
        self.assertTrue(drifted["warnings"])
        self.assertEqual(aligned["status"], "passed")
        self.assertTrue(aligned["passed"])


class TestWikiDoesNotInventGtaOrGoy(unittest.TestCase):
    """#746. capitalize() turned GTA into Gta and goy into Goy."""

    def test_run_76_seed_does_not_emit_gta_or_goy_articles(self):
        from apis.wikipedia_pageviews_api import _article_candidates

        candidates = _article_candidates(RUN76_SEED)
        self.assertNotIn("Gta", candidates)
        self.assertNotIn("Goy", candidates)
        self.assertTrue(
            any(c == "GTA" or c.startswith("GTA_") for c in candidates),
            candidates,
        )

    def test_an_already_titled_topic_still_forms_an_article(self):
        from apis.wikipedia_pageviews_api import _article_candidates

        self.assertIn("Marvel_Rivals", _article_candidates("Marvel Rivals"))
        self.assertIn("UFC_250", _article_candidates("UFC 250"))


class TestAutocomplete400IsASkip(unittest.TestCase):
    """#747. Long thesis 400'd and showed as HTTP ERROR noise."""

    def test_run_76_seed_is_not_sent_verbatim(self):
        from apis.autocomplete_api import get_autocomplete_data

        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = ["q", ["gta 6 release date"]]
        with patch("apis.autocomplete_api.requests.get", return_value=fake) as get:
            get_autocomplete_data(RUN76_SEED)
        sent = get.call_args.kwargs.get("params") or get.call_args[1].get("params")
        q = sent["q"]
        self.assertLess(len(q), len(RUN76_SEED))
        self.assertNotIn("!!", q)

    def test_http_400_is_a_skip_with_reason_not_a_bare_http_error(self):
        from apis.autocomplete_api import get_autocomplete_data
        from apis.signal_contract import STATUS_HTTP

        fake = MagicMock()
        fake.status_code = 400
        fake.text = "Bad Request"
        with patch("apis.autocomplete_api.requests.get", return_value=fake):
            sig = get_autocomplete_data(RUN76_SEED)
        self.assertNotEqual(sig["status"], STATUS_HTTP)
        detail = str(sig.get("status_detail") or "").lower()
        self.assertIn("400", detail)
        self.assertTrue("skip" in detail or "reject" in detail, sig)


class TestTtsCapPublishFeeder(unittest.TestCase):
    """#738. blocking_publish_reasons only checked a script nobody passed."""

    def test_persisted_char_count_feeds_the_publish_list(self):
        from core.publish_blockers import blocking_publish_reasons

        reasons = blocking_publish_reasons(features={"tts_char_count": 8000})
        blob = " ".join(reasons)
        self.assertIn("TTS character cap", blob)
        self.assertIn("8000", blob.replace(",", ""))

    def test_a_forced_overage_does_not_block_publish(self):
        from core.publish_blockers import blocking_publish_reasons

        reasons = blocking_publish_reasons(features={"tts_char_count": 8000, "tts_force": True})
        self.assertFalse(any("TTS character cap" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
