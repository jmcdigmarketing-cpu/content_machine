import unittest
from unittest.mock import MagicMock, patch

from core import best_bet as bb
from core.best_bet import get_best_bet, get_best_bets
from storage.repositories.content_runs import ContentRunRecord

# Mirrors the live run: one thin 39% UFC sample vs six well-sampled 11% NBA videos.
_ENTRIES_MIX = [
    {"topic": "ufc thing", "engaged_rate": 0.39, "composite_score": 60, "domain": "ufc"},
] + [
    {"topic": f"nba thing {i}", "engaged_rate": 0.11, "composite_score": 50, "domain": "nba"}
    for i in range(6)
]

_ENTRIES = [
    {"topic": "old ufc topic", "engaged_rate": 0.39, "composite_score": 60, "domain": "ufc"},
    {"topic": "old gaming topic", "engaged_rate": 0.25, "composite_score": 50, "domain": "gaming"},
]


class TestFreshBestBets(unittest.TestCase):
    def test_fresh_headlines_preferred_and_ranked_by_domain(self):
        fresh = [
            {"topic": "Gaethje turns top 10 P4P", "domain": "ufc", "source": "ESPN MMA"},
            {"topic": "New roguelike hits Steam", "domain": "gaming", "source": "IGN"},
        ]
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=fresh),
        ):
            bets = get_best_bets("tapin", 3)
        # UFC (39%) outranks gaming (25%); both are fresh/trending, not historical.
        self.assertEqual(bets[0].topic, "Gaethje turns top 10 P4P")
        self.assertEqual(bets[0].source, "trending")
        self.assertIn("trending", bets[0].rationale)

    def test_recently_covered_topics_excluded(self):
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch(
                "core.best_bet.recent_input_topics",
                return_value=["Gaethje turns top 10 P4P"],
            ),
            # The helper itself excludes recent topics, so it returns none here.
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bets = get_best_bets("tapin", 3)
        # Falls back to historical; the recent topic is not re-suggested.
        self.assertTrue(all("Gaethje turns top 10" not in b.topic for b in bets))

    def test_falls_back_to_historical_without_fresh(self):
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bets = get_best_bets("tapin", 3)
        self.assertTrue(bets)
        self.assertEqual(bets[0].source, "analytics")

    def test_fresh_disabled_via_env(self):
        with (
            patch.dict("os.environ", {"BEST_BET_FRESH": "false"}, clear=False),
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates") as mock_fresh,
        ):
            get_best_bets("tapin", 3)
            mock_fresh.assert_not_called()


class TestConfidenceAndDiversity(unittest.TestCase):
    def test_adjusted_rate_shrinks_thin_domain(self):
        adj = bb._adjusted_domain_rates(_ENTRIES_MIX)
        self.assertLess(adj["ufc"], 0.39)  # 1-sample 39% pulled toward the mean
        self.assertIn("nba", adj)

    def test_domain_priority_prefers_well_sampled(self):
        adjusted = {"nba": 0.12, "ufc": 0.20}
        counts = {"nba": 6, "ufc": 1}
        self.assertGreater(
            bb._domain_priority("nba", adjusted, counts),
            bb._domain_priority("ufc", adjusted, counts),
        )

    def test_well_sampled_domain_leads_over_thin_high_rate(self):
        fresh = [
            {"topic": "UFC champ plans return", "domain": "ufc", "source": "ESPN MMA"},
            {"topic": "NBA trade shakes the East", "domain": "nba", "source": "ESPN NBA"},
        ]
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES_MIX),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=fresh),
        ):
            bets = get_best_bets("tapin", 3)
        # NBA (6 samples) leads the thin 1-sample UFC despite UFC's higher raw rate.
        self.assertEqual(bets[0].domain, "nba")
        # And the picks span domains instead of stacking one.
        self.assertIn("ufc", {b.domain for b in bets})

    def test_does_not_stack_a_single_thin_domain(self):
        # Three UFC headlines, one thin UFC sample, plus well-sampled NBA history.
        fresh = [
            {"topic": "UFC story one", "domain": "ufc", "source": "ESPN MMA"},
            {"topic": "UFC story two", "domain": "ufc", "source": "ESPN MMA"},
            {"topic": "UFC story three", "domain": "ufc", "source": "ESPN MMA"},
        ]
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES_MIX),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=fresh),
        ):
            bets = get_best_bets("tapin", 3)
        # Not all three are the thin UFC domain — historical NBA fills a slot.
        self.assertLess(sum(1 for b in bets if b.domain == "ufc"), 3)
        self.assertTrue(any(b.domain == "nba" for b in bets))


class TestCommerceFilter(unittest.TestCase):
    def test_flags_deal_and_hardware_headlines(self):
        commerce = [
            "The RTX 5080 Prebuilt Gaming PC Drops to $2,350",
            "Alienware AW3426DW Gaming Monitor Review",
            "Dell Outlet Has Restocked Alienware Area-51 RTX 5090 Gaming PCs",
            "Best Gaming Laptop Deals This Week",
            "Save $400 on This GeForce RTX Bundle",
        ]
        for title in commerce:
            self.assertTrue(bb._is_commerce_headline(title), title)

    def test_keeps_real_content_headlines(self):
        content = [
            "Marvel Rivals Season 9 overhauls Black Widow and 80% of the roster",
            "Palworld's 1.0 patch notes are so massive Steam wouldn't accept them",
            "Gaethje turns top 10 pound-for-pound after the White House card",
        ]
        for title in content:
            self.assertFalse(bb._is_commerce_headline(title), title)

    def test_fresh_candidates_drops_commerce(self):
        rows = [
            {"title": "RTX 5090 Gaming PC Drops to $2,350", "published": ""},
            {"title": "Marvel Rivals Season 9 reworks Black Widow entirely", "published": ""},
            {"title": "Alienware Monitor Review", "published": ""},
        ]
        with (
            patch("apis.rss_feeds._fetch_feed", return_value=rows),
            patch("apis.topic_scorer.infer_domain", return_value="gaming"),
            patch(
                "config.data_sources.rss_feeds_for_channel",
                return_value=[{"url": "http://feed", "name": "IGN"}],
            ),
        ):
            cands = bb._fresh_candidates("tapin", allowed={"gaming"}, exclude=set(), limit=10)
        topics = [c["topic"] for c in cands]
        self.assertIn("Marvel Rivals Season 9 reworks Black Widow entirely", topics)
        self.assertFalse(any("Drops to" in t or "Monitor Review" in t for t in topics))

    def test_filter_can_be_disabled_via_env(self):
        with patch.dict("os.environ", {"BEST_BET_FILTER_COMMERCE": "false"}, clear=False):
            self.assertFalse(bb._commerce_filter_enabled())


class TestBestBetFreshnessDiversity(unittest.TestCase):
    def test_first_anchor_collapses_gta_variants(self):
        # "GTA VI" and "GTA 6" must resolve to the SAME franchise so the cap dedupes them.
        self.assertEqual(bb._first_anchor("GTA VI new 2026 leak"), "gta")
        self.assertEqual(bb._first_anchor("GTA 6 map details revealed"), "gta")
        self.assertIsNone(bb._first_anchor("Some generic esports drama"))

    def test_parse_pubdate_formats(self):
        self.assertIsNotNone(bb._parse_pubdate("Tue, 08 Jul 2026 14:03:00 GMT"))  # RFC822
        self.assertIsNotNone(bb._parse_pubdate("2026-07-08T14:03:00Z"))  # ISO8601 / Atom
        self.assertIsNone(bb._parse_pubdate("not a date"))
        self.assertIsNone(bb._parse_pubdate(None))

    def test_anchor_cap_limits_one_pick_per_franchise(self):
        # Three GTA headlines (same franchise) must NOT fill every gaming slot.
        fresh = [
            {"topic": "GTA VI new trailer breakdown", "domain": "gaming", "source": "IGN"},
            {"topic": "GTA 6 map size leaks online", "domain": "gaming", "source": "Dexerto"},
            {"topic": "GTA VI pre-order controversy", "domain": "gaming", "source": "Kotaku"},
        ]
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=fresh),
        ):
            bets = get_best_bets("tapin", 3)
        gta = [b for b in bets if "gta" in b.topic.lower()]
        self.assertLessEqual(len(gta), 1)  # at most one GTA pick

    def test_fresh_candidates_prefers_recent_and_rotates_daily(self):
        from datetime import datetime, timezone

        rows = [
            {"title": f"Gaming headline {i}", "link": "", "published": "2026-07-08T12:00:00Z"}
            for i in range(15)
        ] + [{"title": "Ancient gaming headline", "link": "", "published": "2020-01-01T00:00:00Z"}]

        def _fake_now_factory(day):
            class _DT(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime(2026, 7, day, 12, 0, 0, tzinfo=timezone.utc)

            return _DT

        with (
            patch("apis.rss_feeds._fetch_feed", return_value=rows),
            patch("apis.topic_scorer.infer_domain", return_value="gaming"),
            patch(
                "config.data_sources.rss_feeds_for_channel",
                return_value=[{"url": "http://feed", "name": "Feed"}],
            ),
        ):
            with patch("core.best_bet.datetime", _fake_now_factory(8)):
                day8 = bb._fresh_candidates("tapin", allowed={"gaming"}, exclude=set(), limit=5)
            with patch("core.best_bet.datetime", _fake_now_factory(9)):
                day9 = bb._fresh_candidates("tapin", allowed={"gaming"}, exclude=set(), limit=5)
        # The stale 2020 item is dropped when enough recent items exist.
        self.assertTrue(all("Ancient" not in c["topic"] for c in day8))
        # Daily-seeded rotation: different day → a different surfaced order/set.
        self.assertNotEqual([c["topic"] for c in day8], [c["topic"] for c in day9])


class TestBestBet(unittest.TestCase):
    def test_prefers_marvel_rivals_continuity_on_tapin(self):
        runs = [
            ContentRunRecord(
                id=23,
                channel_id="tapin",
                input_topic="Marvel rivals update",
                selected_topic="Primary Storyline: Marvel's Game-Changing Rivalries",
                status="done",
                composite_score=100.0,
            ),
            ContentRunRecord(
                id=19,
                channel_id="tapin",
                input_topic="State of Gaming 2026. Marvel Rivals, terraria, cod",
                selected_topic="Marvel Rivals Takes the Gaming World by Storm",
                status="done",
                composite_score=86.8,
            ),
            ContentRunRecord(
                id=16,
                channel_id="tapin",
                input_topic="The fall of COD Zombies from the glory days",
                selected_topic="Overlooked Gems: COD Zombies",
                status="done",
                composite_score=100.0,
            ),
        ]

        mock_repo = MagicMock()
        mock_repo.list_for_channel.return_value = runs
        mock_log_repo = MagicMock()
        mock_log_repo.list_timed_outcomes.return_value = []

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=mock_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=mock_log_repo,
            ),
        ):
            result = get_best_bet("tapin")

        self.assertIsNotNone(result)
        self.assertIn("marvel rivals", result.topic.lower())
        self.assertEqual(result.source, "continuity")

    def test_score_fallback_uses_input_topic_not_variant_title(self):
        runs = [
            ContentRunRecord(
                id=5,
                channel_id="tapin",
                input_topic="GTA VI Online Wishlist",
                selected_topic="Hidden Gems: Features We Need in GTA VI",
                status="done",
                composite_score=90.0,
            ),
        ]

        mock_repo = MagicMock()
        mock_repo.list_for_channel.return_value = runs
        mock_log_repo = MagicMock()
        mock_log_repo.list_timed_outcomes.return_value = []

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=mock_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=mock_log_repo,
            ),
            patch("core.best_bet._continuity_seed", return_value=None),
        ):
            result = get_best_bet("tapin")

        self.assertEqual(result.topic, "GTA VI Online Wishlist")
        self.assertEqual(result.source, "score")


if __name__ == "__main__":
    unittest.main()
