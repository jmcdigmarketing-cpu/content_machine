"""Wave 142 (2026-11-01) - the next five (decision 94), S05 the shortfall it takes.

S05 the grade gates nothing - it ranked videos no better than chance against their views - and
S05 measures it against the audience instead of the operator; #1947 an NFL team named by its
nickname reads NFL, and a stored subject today's reading disputes is corrected; #1931 the
captions keep Instagram's 450 px clear; #1752 a tracking ID per place - a long video's
description and a link page per bio; #1919 the views YouTube says the link pages sent.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_organic_engaged import VIDEO, _Fake

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)


def _video(video_id, views, run_id, *, title="", parent=False):
    from core.success.videos import Video

    return Video(video_id=video_id, title=title or video_id, published_at=NOW - timedelta(days=9),
                 views=views, engaged_rate=None, run_id=run_id, seeded=False, views_7d=views,
                 lifetime_views=views)  # fmt: skip


# ---- S05 (decision 94): the grade gates nothing ----------------------------------------------------


def _no_gate_env():
    return {k: v for k, v in os.environ.items() if k not in ("GRADE_GATE", "BACKLOG_MIN_GRADE")}


class GradeGateTests(unittest.TestCase):
    def test_a_c_renders_unattended_when_authenticity_is_ok(self):
        from core.render_gate import unattended_render_block_reason

        with patch.dict(os.environ, _no_gate_env(), clear=True):
            self.assertIsNone(unattended_render_block_reason(letter="C", authenticity_verdict="ok"))
            self.assertIsNone(
                unattended_render_block_reason(letter=None, authenticity_verdict="ok")
            )
            self.assertIn(
                "authenticity review",
                unattended_render_block_reason(letter="A", authenticity_verdict="review"),
            )
            self.assertIsNotNone(
                unattended_render_block_reason(letter="A", authenticity_verdict=None)
            )

    def test_grade_gate_brings_the_floor_back(self):
        from core.render_gate import unattended_render_block_reason

        with patch.dict(os.environ, {**_no_gate_env(), "GRADE_GATE": "B"}, clear=True):
            self.assertIn(
                "report card C",
                unattended_render_block_reason(letter="C", authenticity_verdict="ok"),
            )
            self.assertIn(
                "report card missing",  # "" is "in" every string - it passed once
                unattended_render_block_reason(letter=None, authenticity_verdict="ok"),
            )
        with patch.dict(os.environ, {**_no_gate_env(), "BACKLOG_MIN_GRADE": "A"}, clear=True):
            self.assertIn(
                "report card B",
                unattended_render_block_reason(letter="B", authenticity_verdict="ok"),
            )

    def test_a_low_quality_dict_is_not_held_for_its_grade(self):
        from core.render_gate import block_reason_from_quality

        quality = {"hook_score": 10, "authenticity_score": 10, "authenticity_verdict": "ok",
                   "ungrounded_count": 8}  # fmt: skip
        with patch.dict(os.environ, _no_gate_env(), clear=True):
            self.assertIsNone(block_reason_from_quality(quality))

    def _gate(self, env):
        from publishing.backlog import backlog_gate

        draft = SimpleNamespace(
            run_id=7, meta={}, title="Lakers to Win vs Warriors", script="Text."
        )
        with (
            patch.dict(os.environ, env, clear=True),
            patch("core.video_grade.grade_run", return_value=SimpleNamespace(letter="C")),
        ):
            return backlog_gate(draft)

    def test_the_backlog_renders_a_c_draft_on_its_own(self):
        self.assertEqual([r for r in self._gate(_no_gate_env()) if "grade" in r], [])
        self.assertIn(
            "grade C (needs B or better)", self._gate({**_no_gate_env(), "GRADE_GATE": "B"})
        )


class GradeAgreementTests(unittest.TestCase):
    def _agreement(self, grades):
        from core.success import verdicts

        videos = [_video(f"v{i}", 700 - 100 * i, i) for i in range(1, 7)]  # v1 most viewed
        with (
            patch("core.success.videos.channel_videos", return_value=videos),
            patch(
                "core.video_grade.grade_run",
                side_effect=lambda run_id: SimpleNamespace(score=grades[run_id]),
            ),
        ):
            return verdicts.grade_agreement("tapin")

    def test_the_grade_is_ranked_in_thirds_against_the_views(self):
        # views thirds: v1 v2 | v3 v4 | v5 v6; grade thirds: v1 v2 | v5 v6 | v4 v3
        self.assertEqual(self._agreement({1: 90, 2: 85, 3: 40, 4: 50, 5: 80, 6: 70}), (2, 6))
        self.assertEqual(self._agreement({1: 90, 2: 85, 3: 80, 4: 70, 5: 50, 6: 40}), (6, 6))

    def test_s05_reads_the_grade_against_the_audience(self):
        from core.success.shortfalls import BUILT, MET, NOT_YET, _s05

        with (
            patch.dict(os.environ, _no_gate_env(), clear=True),
            patch("core.success.verdicts.grade_agreement", return_value=(20, 67)),
        ):
            reading = _s05("tapin", NOW)
        self.assertEqual(reading.status, BUILT)
        self.assertIn("20 of 67", reading.today)
        self.assertIn("gates nothing", reading.today)
        for agreed, status in ((20, NOT_YET), (40, MET)):
            with (
                patch.dict(os.environ, {**_no_gate_env(), "GRADE_GATE": "B"}, clear=True),
                patch("core.success.verdicts.grade_agreement", return_value=(agreed, 67)),
            ):
                self.assertEqual(_s05("tapin", NOW).status, status)

    def test_ops_verdicts_prints_the_grade_beside_you(self):
        from core.success import verdicts

        scored = {"measured": 30, "rated": 5, "agreed": 3, "loved": [], "doubted": [],
                  "heading": "views to date"}  # fmt: skip
        with (
            patch.object(verdicts, "_scored", return_value=scored),
            patch.object(verdicts, "grade_agreement", return_value=(9, 30)),
        ):
            text = "\n".join(verdicts.verdict_report("tapin"))
        self.assertIn("the grade against the audience: 9 of 30 in the same third", text)


# ---- #1947: subjects ------------------------------------------------------------------------------


class SubjectTests(unittest.TestCase):
    def test_nfl_teams_named_by_nickname_read_nfl(self):
        from apis.topic_scorer import infer_domain, infer_topic_domain

        for title in (
            "Tennessee Titans' offensive line faces test vs Colts' revamped pass rush",
            "Jets vs Patriots Preview: England's AFC East Clash with Playoff Implications",
            "Washington vs 49ers preview: San Francisco's 5-0 start faces test",
        ):
            self.assertEqual(infer_topic_domain(title), "nfl", title)
            self.assertEqual(infer_domain(title, "tapin"), "nfl", title)

    def test_one_ambiguous_nickname_is_not_enough(self):
        from apis.topic_scorer import infer_topic_domain

        self.assertNotEqual(
            infer_topic_domain("Teen Titans arrive in Fortnite's new season"), "nfl"
        )
        self.assertNotEqual(
            infer_topic_domain("Giants of the deep: the biggest sea monsters"), "nfl"
        )
        self.assertEqual(infer_topic_domain("Detroit Pistons bench outplays Boston Celtics"), "nba")
        self.assertEqual(infer_topic_domain("People Are Blending Minecraft Inside Elden Ring With AI"),
                         "gaming")  # fmt: skip

    def _drift(self, videos, features):
        from core.runs import domains

        with (
            patch("core.success.videos.channel_videos", return_value=videos),
            patch("core.run_features.load_features", side_effect=lambda r: features.get(r, {})),
        ):
            return domains.drift("tapin")

    def test_drift_lists_a_stored_subject_the_title_disputes(self):
        videos = [
            _video("a", 65, 120, title="People Are Blending Minecraft Inside Elden Ring With AI"),
            _video("b", 900, 190, title="GTA 6 map leak, explained"),  # a chapter Short
            _video("c", 4, 172, title="TapIn Media Week in Review: Oct 15 - Oct 18"),  # no domain
            _video("d", 30, 175, title="Xbox Game Pass subscribers react to Final Fantasy"),
            _video("e", 82, 155, title="Tennessee Titans' offensive line faces test vs Colts"),
        ]
        features = {
            120: {"domain": "nba", "domains": {"topic": "nba", "effective": "nba"}},
            190: {"parent_run_id": 186},
            172: {"compilation": {"shorts": 4}},
            175: {"domain": "gaming"},
            155: {"domain": "gaming", "domains": {"topic": "neutral", "effective": "neutral",
                                                  "weighting": "gaming"}},
        }  # fmt: skip
        found = {c.run_id: (c.stored, c.read, c.views) for c in self._drift(videos, features)}
        self.assertEqual(found, {120: ("nba", "gaming", 65), 155: ("neutral", "nfl", 82)})

    def test_apply_keeps_the_old_subject_and_growth_reads_the_new(self):
        from analytics.growth import _domain
        from core.runs import domains

        stored = {120: {"domain": "nba", "domains": {"topic": "nba", "effective": "nba",
                                                     "weighting": "nba"}}}  # fmt: skip

        def merge(run_id, updates):
            stored[run_id] = {**stored.get(run_id, {}), **updates}

        fix = domains.Correction(
            run_id=120, title="Minecraft", stored="nba", read="gaming", views=65
        )
        with (
            patch("core.run_features.load_features", side_effect=lambda r: dict(stored.get(r, {}))),
            patch("core.run_features.merge_features", side_effect=merge),
        ):
            self.assertEqual(domains.apply([fix], day="2026-11-01"), 1)
        self.assertEqual(stored[120]["domains"]["effective"], "gaming")
        self.assertEqual(stored[120]["domains"]["was"], "nba")
        self.assertEqual(stored[120]["domains"]["weighting"], "nba")
        self.assertEqual(_domain(stored[120]), "gaming")


# ---- #1931: Instagram's caption rows -------------------------------------------------------------


class CaptionBandTests(unittest.TestCase):
    def test_captions_keep_instagrams_450_px_clear(self):
        from video.safe_zone import (
            CAPTION_BAND,
            CAPTION_BOTTOM_PX,
            HEIGHT,
            LOWER_MARGIN,
            caption_margin,
        )

        self.assertEqual(CAPTION_BOTTOM_PX, 450)
        self.assertEqual(caption_margin("bottom", 260), 450)
        self.assertEqual(caption_margin("bottom", 500), 500)
        self.assertAlmostEqual(CAPTION_BAND[1], 1 - 450 / HEIGHT, places=3)
        self.assertAlmostEqual(CAPTION_BAND[1] - CAPTION_BAND[0], 0.12, places=2)
        self.assertGreaterEqual(LOWER_MARGIN, HEIGHT * (1 - CAPTION_BAND[0]))  # name tags above

    def test_the_karaoke_captions_end_450_px_up(self):
        from tests.test_wave137 import _WORDS, _styles
        from video.caption_timing import build_ass_karaoke

        ass = build_ass_karaoke(_WORDS, title_font="Impact", body_font="Arial", margin=260)
        for name in ("Title", "Body"):
            self.assertEqual(int(_styles(ass)[name]["MarginV"]), 450)


# ---- #1752 + #1919: a tracking ID per place, the link pages' views ---------------------------------


def _tags(**env):
    base = {k: v for k, v in os.environ.items()
            if k not in ("AFFILIATE_AMAZON_TAG", "AFFILIATE_AMAZON_TAGS", "R2_PUBLIC_BASE_URL")}  # fmt: skip
    return patch.dict(os.environ, {**base, **env}, clear=True)


class TrackingIdTests(unittest.TestCase):
    def test_each_place_has_its_own_id_and_falls_back_to_the_tag(self):
        from core.description_extras import amazon_tag

        with _tags(
            AFFILIATE_AMAZON_TAG="main-20", AFFILIATE_AMAZON_TAGS="long=yt-20, tiktok=tt-20"
        ):
            self.assertEqual(amazon_tag("long"), "yt-20")
            self.assertEqual(amazon_tag("tiktok"), "tt-20")
            self.assertEqual(amazon_tag("instagram"), "main-20")
            self.assertEqual(amazon_tag(""), "main-20")
        with _tags():
            self.assertEqual(amazon_tag("long"), "")

    def test_a_long_videos_link_carries_the_long_id(self):
        from core.description_extras import affiliate_lines

        with _tags(AFFILIATE_AMAZON_TAG="main-20", AFFILIATE_AMAZON_TAGS="long=yt-20"):
            lines = affiliate_lines("tapin", "GTA 6 - everything we know", long_form=True)
        self.assertIn("tag=yt-20", lines[0])

    def _pages(self, env):
        from publishing import link_page

        hosted: dict[str, str] = {}
        empty = SimpleNamespace(list_uploaded_for_channel=lambda channel_id: [])
        with (
            tempfile.TemporaryDirectory() as tmp,
            _tags(**env),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository", return_value=empty
            ),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(get=lambda run_id: None),
            ),
            patch.object(link_page, "_out_dir", return_value=tmp),
            patch(
                "publishing.video_host.host",
                side_effect=lambda path, key, **kw: hosted.setdefault(
                    key, open(path, encoding="utf-8").read()
                ),
            ),
        ):
            urls = link_page.build_all("tapin")
        return urls, hosted

    def test_a_link_page_per_bio_each_with_its_own_id(self):
        urls, hosted = self._pages({"AFFILIATE_AMAZON_TAG": "main-20",
                                    "AFFILIATE_AMAZON_TAGS": "tiktok=tt-20,instagram=ig-20"})  # fmt: skip
        self.assertEqual(set(urls), {"", "tiktok", "instagram", "facebook"})
        self.assertIn("tag=tt-20", hosted["tapin/links/tiktok.html"])
        self.assertIn("tag=ig-20", hosted["tapin/links/instagram.html"])
        self.assertIn("tag=main-20", hosted["tapin/links/facebook.html"])
        self.assertIn("tag=main-20", hosted["tapin/links.html"])  # the first address still works


EXT_DAY = {
    "columnHeaders": [{"name": "day"}, {"name": "insightTrafficSourceType"}, {"name": "views"}],
    "rows": [["2026-10-22", "SHORTS", 300], ["2026-10-23", "EXT_URL", 12]],
}
EXT_DETAIL = {
    "columnHeaders": [{"name": "insightTrafficSourceDetail"}, {"name": "views"}],
    "rows": [["pub-abc.r2.dev", 9], ["google.com", 3]],
}


class LinkPageViewsTests(unittest.TestCase):
    def test_the_sync_keeps_which_outside_site_sent_the_views(self):
        from analytics import youtube_metrics

        service = _Fake({"video": VIDEO, "day,insightTrafficSourceType": EXT_DAY,
                         "insightTrafficSourceDetail": EXT_DETAIL})  # fmt: skip
        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch.object(youtube_metrics, "_date_range", return_value=("2026-10-04", "2026-11-01")),
        ):
            metrics = youtube_metrics.fetch_video_metrics("vid1", channel_id="tapin")
        self.assertEqual(metrics["ext_url_detail"], {"pub-abc.r2.dev": 9, "google.com": 3})
        detail = [q for q in service.queries if q.get("dimensions") == "insightTrafficSourceDetail"]
        self.assertIn("insightTrafficSourceType==EXT_URL", detail[0]["filters"])

    def test_the_link_pages_views_are_the_ones_from_their_host(self):
        from publishing import link_page

        rows = [SimpleNamespace(youtube_video_id="v1", metrics_json=json.dumps(
                    {"ext_url_detail": {"pub-abc.r2.dev": 9, "google.com": 3}})),
                SimpleNamespace(youtube_video_id="v2", metrics_json=json.dumps(
                    {"ext_url_detail": {"https://pub-abc.r2.dev/tapin/links/tiktok.html": 2}})),
                SimpleNamespace(youtube_video_id="v3", metrics_json="{}")]  # fmt: skip
        repo = SimpleNamespace(list_uploaded_for_channel=lambda channel_id: rows)
        with (
            _tags(R2_PUBLIC_BASE_URL="https://pub-abc.r2.dev"),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
        ):
            self.assertEqual(link_page.clicks("tapin"), (11, 2))


if __name__ == "__main__":
    unittest.main()
