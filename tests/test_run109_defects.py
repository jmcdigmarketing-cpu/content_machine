"""Five defects run 109 (Uncharted, 2026-09-30, uploaded as job 49) put on screen.

#922 the discovery headroom line read `units_limit` / `units_used`, keys
     `apis/youtube_quota.get_usage_summary` has never returned, so it printed "YouTube
     quota unknown (no reading)" on every run - the test fed the same invented keys.
#923 "Projected cost if you proceed" left out the thumbnail: $0.3164 projected, $0.3614
     billed, the difference exactly the Flux image.
#924 a title over 100 characters was cut at a word and given an ellipsis, and
     "... narrative magic under Neil..." went to YouTube.
#925 a headline counted as "topic-matched" on one generic word: "game" matched every
     gaming headline, "new" matched "news" - so an AI survey and a Rockstar hacker story
     reached the facts, and the Rockstar headline gave GTA vault bullets entity support.
#926 "Surging competitor angle" was just the fastest video in the list: a 2016 IGN video
     at 28 views/day.
"""

from __future__ import annotations

import os
import unittest
from typing import ClassVar
from unittest.mock import patch

TOPIC = "New Uncharted Game Featuring Nathan Drake Reportedly in the Works at Naughty Dog"


class HeadroomTests(unittest.TestCase):
    def test_the_real_quota_summary_is_read(self):
        from apis import youtube_quota
        from core.discovery_headroom import headroom_line

        summary = youtube_quota.get_usage_summary()  # the suite's own empty store
        line = headroom_line(signal_count=12)
        self.assertNotIn("unknown", line)
        self.assertIn(f"{summary['remaining']} YouTube units left", line)


class ProjectedThumbnailTests(unittest.TestCase):
    def test_the_estimate_carries_the_thumbnail(self):
        from core.cost_meter import estimate_run_cost, thumbnail_cost

        with patch("core.llm_router.get_usage", return_value=[]):
            plain = estimate_run_cost(script="word " * 200, rendered=True)
            with_thumb = estimate_run_cost(
                script="word " * 200, rendered=True, thumbnail_provider="flux"
            )
        self.assertAlmostEqual(with_thumb["thumbnail"], thumbnail_cost("flux"))
        self.assertAlmostEqual(
            with_thumb["total"], round(plain["total"] + thumbnail_cost("flux"), 4)
        )

    def test_the_expected_provider_follows_the_chain(self):
        from assets.flux_thumbnail import expected_provider

        env = {"BFL_API_KEY": "k", "THUMBNAIL_PROVIDER": "", "FREE_MODE_STRICT": ""}
        with patch.dict(os.environ, env):
            self.assertEqual(expected_provider(None), "flux")
            self.assertEqual(expected_provider("D"), "pillow")  # below the paid floor
        with patch.dict(os.environ, {**env, "THUMBNAIL_PROVIDER": "ideogram"}):
            self.assertEqual(expected_provider(None), "ideogram")
        with patch.dict(os.environ, {**env, "BFL_API_KEY": "", "FLUX_API_KEY": ""}):
            self.assertEqual(expected_provider(None), "pillow")
        with patch.dict(os.environ, {**env, "FREE_MODE_STRICT": "1"}):
            self.assertEqual(expected_provider(None), "pillow")

    def test_the_pre_discovery_cap_counts_it_too(self):
        from core import run_mode

        est = {"total": 0.1}
        with (
            patch.dict(os.environ, {"PROJECTED_COST_MAX_USD": "5"}),
            patch("core.cost_meter.estimate_run_cost", return_value=est) as mock_est,
            patch("assets.flux_thumbnail.expected_provider", return_value="flux"),
        ):
            run_mode.projected_cost_block_reason()
        self.assertEqual(mock_est.call_args.kwargs.get("thumbnail_provider"), "flux")


class TitleFitTests(unittest.TestCase):
    RAW = (
        "Critics question if new Uncharted game can recapture series' narrative magic "
        "under Neil Druckmann's new direction at Naughty Dog"
    )

    def test_a_long_title_ends_at_a_clause_not_mid_name(self):
        from core.title_generator import generate_title

        with patch("core.title_generator.complete", return_value=self.RAW):
            title = generate_title(
                script="Neil Druckmann said Naughty Dog was done with Uncharted.",
                topic="Critics question if new Uncharted game can recapture series' magic",
                seed_topic=TOPIC,
            )
        self.assertEqual(
            title,
            "Critics question if new Uncharted game can recapture series' narrative magic",
        )
        self.assertNotIn("…", title)

    def test_a_title_within_the_limit_is_untouched(self):
        from core.title_generator import _fit_title

        self.assertEqual(
            _fit_title("Topuria holds at UFC 320", angle=""), "Topuria holds at UFC 320"
        )


class HeadlineMatchTests(unittest.TestCase):
    HEADLINES: ClassVar[dict[str, bool]] = {
        "Naughty Dog Reportedly Working On A New Uncharted Game": True,
        "Over 85 Percent Of Japanese Game Developers Are Using AI": False,
        "Control Resonant Has The Coolest Bit Of Video Game Audio In 2026": False,
        "Alleged Rockstar Games Hacker Arrested In Connection With Data Breach": False,
        "PlayStation's Free PS Plus Games For October Aren't Really Scary At All": False,
    }

    def test_one_generic_word_is_not_a_match(self):
        from apis.rss_feeds import _anchor_phrases, _matches_topic, _topic_tokens

        tokens, phrases = _topic_tokens(TOPIC), _anchor_phrases(TOPIC)
        got = {h: _matches_topic(h, tokens, phrases=phrases) for h in self.HEADLINES}
        self.assertEqual(got, self.HEADLINES)

    def test_a_token_matches_whole_words_only(self):
        from apis.rss_feeds import _matches_topic, _topic_tokens

        tokens = _topic_tokens("Dogecoin rally")
        self.assertTrue(_matches_topic("Dogecoin jumps 20%", tokens))
        self.assertFalse(_matches_topic("Dogecoin jumps 20%", _topic_tokens("Dog days")))
        self.assertTrue(_matches_topic("Topuria's next fight is set", _topic_tokens("Topuria")))

    def test_a_topic_of_only_register_words_still_matches(self):
        from apis.rss_feeds import _matches_topic, _topic_tokens

        self.assertTrue(_matches_topic("The best new games of October", _topic_tokens("new games")))


class OutlierTests(unittest.TestCase):
    @staticmethod
    def _signals(videos):
        return {"youtube_competitors": {"active": True, "data": {"videos": videos}}}

    def test_an_old_slow_video_is_not_surging(self):
        from core.outlier import get_competitor_outlier

        videos = [
            {
                "title": "Uncharted 4 is Gorgeous",
                "channel": "IGN",
                "velocity": 28.0,
                "age_days": 3600,
            },
            {
                "title": "Uncharted 3 review",
                "channel": "GameSpot",
                "velocity": 9.0,
                "age_days": 4800,
            },
        ]
        self.assertIsNone(get_competitor_outlier(self._signals(videos)))

    def test_a_recent_video_well_above_the_rest_is(self):
        from core.outlier import get_competitor_outlier

        videos = [
            {"title": "New Uncharted leak", "channel": "A", "velocity": 5000.0, "age_days": 2},
            {"title": "b", "channel": "B", "velocity": 400.0, "age_days": 5},
            {"title": "c", "channel": "C", "velocity": 300.0, "age_days": 9},
        ]
        outlier = get_competitor_outlier(self._signals(videos))
        self.assertIsNotNone(outlier)
        self.assertEqual(outlier.title, "New Uncharted leak")

    def test_a_recent_video_level_with_the_rest_is_not(self):
        from core.outlier import get_competitor_outlier

        videos = [
            {"title": "a", "velocity": 500.0, "age_days": 2},
            {"title": "b", "velocity": 450.0, "age_days": 3},
            {"title": "c", "velocity": 400.0, "age_days": 4},
        ]
        self.assertIsNone(get_competitor_outlier(self._signals(videos)))


if __name__ == "__main__":
    unittest.main()
