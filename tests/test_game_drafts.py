"""Wave 87 (#1169-#1173): what overnight drafts.

The overnight run of 2026-10-14 (it started at 5:54 PM, when the PC woke):

- Its three drafts were scheduled NFL games and all three came back as recaps of games not
  yet played ("Seattle Seahawks miss tackles as Denver Broncos convert short-yardage plays",
  game on Oct 16). The operator keeps the schedule in the batch, so the angles must be previews.
- Run 146 (Seahawks at Broncos) ran `lastfm` and `musicbrainz`: the topic read as having no
  domain, and gating runs everything then. The claim check then had 17-21 fact lines it could
  not fit on 5 of the day's checks.
- `blog_rss` with no feed for an NFL topic answered "no key", which trips the session breaker
  and persists across runs.
- Game drafts whose game had started waited until twice their window.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.test_batch_generation import BatchCase, _discovery, _pipeline_result
from tests.test_overnight_renders import _DraftsCase

GAME = "Seattle Seahawks at Denver Broncos"
PICK = {
    "offered": [{"topic": GAME, "domain": "nfl", "source": "schedule"}],
    "picked": 1,
    "by": "batch",
}

# ---- #1169: a scheduled game gets preview angles --------------------------------------------


class PreviewBriefTests(BatchCase):
    def _draft(self, event_at, topic=GAME, pick=PICK):
        from core import batch_generation as bg

        with (
            patch("core.pipeline.run_discovery", return_value=_discovery(topic=topic)) as rd,
            patch("core.pipeline.run_pipeline", return_value=_pipeline_result()) as rp,
            patch("core.seasonal_calendar.event_start", return_value=event_at),
        ):
            kwargs = {"best_bet": pick} if pick else {}
            bg.generate_draft(topic, "tapin", **kwargs)
        return rd, rp

    def test_a_game_ahead_is_drafted_as_a_preview(self):
        rd, rp = self._draft("2099-10-16T00:15Z")
        brief = rd.call_args.kwargs.get("brief", "")
        self.assertTrue(brief.startswith("This game has not been played yet"), brief)
        self.assertIn("what to watch", brief)
        self.assertTrue(rp.call_args.kwargs["creative_brief"].startswith(brief))

    def test_the_brief_is_not_read_as_the_operators_points(self):
        from core.experiment_levers import is_directive
        from core.facts.event_dates import preview_brief

        self.assertTrue(is_directive(preview_brief("2026-10-16T00:15Z")))
        self.assertTrue(is_directive(preview_brief("2026-10-16T00:15Z") + "\nOpen on a number."))

    def test_the_brief_names_the_day(self):
        from core.facts.event_dates import preview_brief

        self.assertIn("Oct 16", preview_brief("2026-10-16T00:15Z"))
        self.assertIn("never describe plays", preview_brief("2026-10-16T00:15Z").lower())

    def test_a_game_already_started_gets_no_preview(self):
        rd, _rp = self._draft("2001-10-16T00:15Z")
        self.assertFalse(rd.call_args.kwargs.get("brief"))

    def test_a_typed_topic_is_untouched(self):
        rd, _rp = self._draft("", topic="UFC 320", pick=None)
        self.assertFalse(rd.call_args.kwargs.get("brief"))


# ---- #1170: a game topic knows its sport ----------------------------------------------------


class FixtureDomainTests(unittest.TestCase):
    def test_run146_a_schedule_name_is_its_sport(self):
        from apis.topic_scorer import infer_topic_domain

        self.assertEqual(infer_topic_domain(GAME), "nfl")
        self.assertEqual(infer_topic_domain("Chicago Bears at Atlanta Falcons"), "nfl")
        self.assertEqual(infer_topic_domain("Cleveland Cavaliers at Orlando Magic"), "nba")
        self.assertEqual(infer_topic_domain("Indiana Pacers at Oklahoma City Thunder"), "nba")

    def test_a_word_that_is_also_a_team_is_not_a_game(self):
        from apis.topic_scorer import infer_topic_domain

        self.assertNotEqual(infer_topic_domain("Giants of the deep: a Subnautica guide"), "nfl")
        self.assertNotEqual(infer_topic_domain("Magic: The Gathering at its best"), "nba")

    def test_run146_music_and_filings_signals_stay_off(self):
        from apis.register_signals import _gated_signal_names

        gated = _gated_signal_names(GAME)
        for name in ("lastfm", "musicbrainz", "sec_edgar", "coingecko"):
            self.assertIn(name, gated)
        self.assertNotIn("live_scores", gated)


# ---- #1171: the claim check's own budget ------------------------------------------------------


class CheckBudgetTests(unittest.TestCase):
    def _budget(self, value=None):
        from core.claim_verifier import _max_fact_chars

        env = {k: v for k, v in os.environ.items() if k != "CLAIM_FACT_CHAR_BUDGET"}
        if value is not None:
            env["CLAIM_FACT_CHAR_BUDGET"] = value
        with patch.dict(os.environ, env, clear=True):
            return _max_fact_chars()

    def test_the_check_reads_twice_what_it_did(self):
        self.assertEqual(self._budget(), 24000)
        self.assertEqual(self._budget("30000"), 30000)
        self.assertEqual(self._budget("junk"), 24000)

    def test_the_script_prompt_keeps_its_own(self):
        from core.operator_facts import operator_key_fact_char_budget

        with patch.dict(os.environ, {"CLAIM_FACT_CHAR_BUDGET": "40000"}):
            self.assertEqual(operator_key_fact_char_budget(), 12000)


# ---- #1172: no feed for a topic is not a missing key ------------------------------------------


class RssStatusTests(unittest.TestCase):
    def test_no_feed_for_the_topic_is_inactive(self):
        from apis.blog_rss_api import get_blog_rss_signal
        from apis.signal_contract import STATUS_INACTIVE

        with patch("apis.blog_rss_api.rss_feeds_for_topic", return_value=[]):
            sig = get_blog_rss_signal(GAME)
        self.assertEqual(sig["status"], STATUS_INACTIVE)
        self.assertTrue(sig["connected"])
        self.assertFalse(sig["active"])

    def test_inactive_does_not_trip_the_breaker(self):
        from apis.register_signals import _trip_statuses
        from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY

        self.assertNotIn(STATUS_INACTIVE, _trip_statuses())
        self.assertIn(STATUS_NO_KEY, _trip_statuses())  # a real missing key still trips


# ---- #1173: a game draft whose game has started is set aside ----------------------------------


class StartedGameTests(_DraftsCase):
    def test_a_started_game_is_set_aside(self):
        from core.batch_review import expire_old_drafts

        past = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%MZ")
        ahead = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%MZ")
        self._draft(1, topic="Houston Texans at Tennessee Titans", event_at=past)
        self._draft(2, topic="Seattle Seahawks at Denver Broncos", event_at=ahead)
        found = expire_old_drafts("tapin", root=self.tmp.name, apply=False)
        self.assertEqual([d.run_id for d in found], [1])
        expire_old_drafts("tapin", root=self.tmp.name)
        self.assertIn("its game has started", self._stored(1)["review"]["reason"])


if __name__ == "__main__":
    unittest.main()
