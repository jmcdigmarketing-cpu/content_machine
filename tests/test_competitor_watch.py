"""Wave 78 (#1120, #1063): a competitor list the outlier watch can use, and the watch.

Measured 2026-10-10: the list was one channel (a tech reviewer), edited by hand, and the stored
videos carried titles and dates only - while YouTube's free feed has carried a view count per
video all along (`media:statistics`). Nothing looked across the list between runs.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>aaa111</yt:videoId>
    <title>Topuria calls out Makhachev</title>
    <published>2026-10-08T15:00:00+00:00</published>
    <media:group><media:community>
      <media:starRating count="10" average="5.00" min="1" max="5"/>
      <media:statistics views="48211"/>
    </media:community></media:group>
  </entry>
  <entry>
    <yt:videoId>bbb222</yt:videoId>
    <title>Weigh-in recap</title>
    <published>2026-10-07T15:00:00+00:00</published>
  </entry>
</feed>"""

UC_A = "UC" + "a" * 22
UC_B = "UC" + "b" * 22


def _snapshot(views, label="MMA Daily"):
    return {
        "competitors": [
            {
                "youtube_channel_id": UC_A,
                "label": label,
                "recent_videos": [
                    {
                        "video_id": f"v{i}",
                        "title": f"Video {i}",
                        "views": count,
                        "published_at": "2026-10-08T15:00:00+00:00",
                    }
                    for i, count in enumerate(views)
                ],
            }
        ]
    }


class FeedViewsTests(unittest.TestCase):
    def test_the_feeds_view_count_is_kept(self):
        from analytics.youtube_rss import fetch_channel_uploads_rss

        reply = SimpleNamespace(status_code=200, content=FEED)
        with patch("analytics.youtube_rss.requests.get", return_value=reply):
            videos = fetch_channel_uploads_rss(UC_A)
        self.assertEqual(videos[0]["views"], 48211)
        self.assertEqual(videos[0]["title"], "Topuria calls out Makhachev")

    def test_an_entry_with_no_count_has_no_views_key(self):
        from analytics.youtube_rss import fetch_channel_uploads_rss

        reply = SimpleNamespace(status_code=200, content=FEED)
        with patch("analytics.youtube_rss.requests.get", return_value=reply):
            videos = fetch_channel_uploads_rss(UC_A)
        self.assertNotIn("views", videos[1])


class ApiViewsTests(unittest.TestCase):
    """The feed answered 404 for every channel on 2026-10-10; the API path had no counts."""

    def _service(self, stats, fail=False):
        service = MagicMock()
        service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]
        }
        service.playlistItems.return_value.list.return_value.execute.return_value = {
            "items": [
                {"contentDetails": {"videoId": vid}, "snippet": {"title": f"T {vid}"}}
                for vid in ("a1", "b2")
            ]
        }
        execute = service.videos.return_value.list.return_value.execute
        if fail:
            execute.side_effect = RuntimeError("quota")
        else:
            execute.return_value = {"items": stats}
        return service

    def test_the_api_path_stores_a_view_count_per_video(self):
        from analytics.competitor_sync import fetch_channel_recent_videos_api

        service = self._service(
            [{"id": "a1", "statistics": {"viewCount": "5120"}}, {"id": "b2", "statistics": {}}]
        )
        videos = fetch_channel_recent_videos_api(service, UC_A)
        self.assertEqual(videos[0]["views"], 5120)
        self.assertNotIn("views", videos[1])
        service.videos.return_value.list.assert_called_once_with(part="statistics", id="a1,b2")

    def test_a_refused_count_keeps_the_videos(self):
        from analytics.competitor_sync import fetch_channel_recent_videos_api

        videos = fetch_channel_recent_videos_api(self._service([], fail=True), UC_A)
        self.assertEqual([v["video_id"] for v in videos], ["a1", "b2"])
        self.assertNotIn("views", videos[0])


class OutlierTests(unittest.TestCase):
    def test_a_video_at_three_times_the_median_is_a_breakout(self):
        from analytics.competitor_context import outliers

        rows = outliers(_snapshot([1000, 1200, 900, 1100, 5000]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Video 4")
        self.assertEqual(rows[0]["median"], 1100)
        self.assertEqual(rows[0]["ratio"], 4.5)
        self.assertEqual(rows[0]["url"], "https://www.youtube.com/watch?v=v4")
        self.assertEqual(rows[0]["label"], "MMA Daily")

    def test_an_even_channel_has_none(self):
        from analytics.competitor_context import outliers

        self.assertEqual(outliers(_snapshot([1000, 1200, 900, 1100, 2500])), [])

    def test_too_few_counted_videos_is_no_median(self):
        from analytics.competitor_context import outliers

        self.assertEqual(outliers(_snapshot([100, 100, 9000])), [])

    def test_videos_without_a_count_are_not_guessed(self):
        from analytics.competitor_context import outliers

        snap = _snapshot([1000, 1000, 1000, 9000])
        for video in snap["competitors"][0]["recent_videos"]:
            video.pop("views")
        self.assertEqual(outliers(snap), [])
        self.assertEqual(outliers({}), [])
        self.assertEqual(outliers(None), [])

    def test_the_strongest_comes_first_and_the_lines_carry_the_link(self):
        from analytics.competitor_context import outlier_lines, outliers

        snap = _snapshot([1000, 1000, 1000, 1000, 4000, 9000])
        self.assertEqual([r["ratio"] for r in outliers(snap)], [9.0, 4.0])
        lines = outlier_lines(snap)
        self.assertIn("9.0x  Video 5  - MMA Daily, 9,000 views (median 1,000)", lines[1])
        self.assertIn("https://www.youtube.com/watch?v=v5", lines[2])
        self.assertEqual(outlier_lines(_snapshot([1, 2, 3])), [])


class _ListCase(unittest.TestCase):
    def setUp(self):
        import config.competitors as competitors

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(competitors, "COMPETITORS_DIR", self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        competitors.get_competitor_channels.cache_clear()
        self.addCleanup(competitors.get_competitor_channels.cache_clear)
        quota = patch("apis.youtube_quota.record_usage")
        self.spent = quota.start()
        self.addCleanup(quota.stop)

    def _stored(self):
        with open(os.path.join(self.tmp.name, "tapin.json"), encoding="utf-8") as fh:
            return json.load(fh)["youtube_channels"]


class ListTests(_ListCase):
    def test_add_writes_the_list_and_the_sync_sees_it(self):
        from analytics import competitor_list
        from config.competitors import get_competitor_channels

        self.assertEqual(get_competitor_channels("tapin"), [])
        self.assertTrue(competitor_list.add("tapin", UC_A, "MMA Daily"))
        self.assertEqual(self._stored(), [{"id": UC_A, "label": "MMA Daily"}])
        self.assertEqual(get_competitor_channels("tapin"), [{"id": UC_A, "label": "MMA Daily"}])

    def test_add_refuses_a_repeat_and_a_string_that_is_not_an_id(self):
        from analytics import competitor_list

        self.assertTrue(competitor_list.add("tapin", UC_A, "MMA Daily"))
        self.assertFalse(competitor_list.add("tapin", UC_A, "Again"))
        self.assertFalse(competitor_list.add("tapin", "@mmadaily", "A handle"))
        self.assertEqual(len(self._stored()), 1)

    def test_remove_takes_an_id_or_a_word_of_the_label(self):
        from analytics import competitor_list

        competitor_list.add("tapin", UC_A, "MMA Daily")
        competitor_list.add("tapin", UC_B, "Gridiron Shorts")
        self.assertEqual(competitor_list.remove("tapin", "gridiron"), ["Gridiron Shorts"])
        self.assertEqual(competitor_list.remove("tapin", UC_A), ["MMA Daily"])
        self.assertEqual(competitor_list.remove("tapin", "nothing"), [])
        self.assertEqual(self._stored(), [])

    def test_a_channel_is_named_by_id_handle_or_url(self):
        from analytics.competitor_list import channel_ref

        self.assertEqual(channel_ref(UC_A), ("id", UC_A))
        self.assertEqual(channel_ref(f"https://www.youtube.com/channel/{UC_A}"), ("id", UC_A))
        self.assertEqual(channel_ref("https://www.youtube.com/@mmadaily"), ("handle", "@mmadaily"))
        self.assertEqual(channel_ref("mma daily"), ("", ""))

    def test_resolve_asks_once_by_handle(self):
        from analytics import competitor_list

        service = MagicMock()
        service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": UC_A, "snippet": {"title": "MMA Daily"}}]
        }
        found = competitor_list.resolve(service, "@mmadaily")
        self.assertEqual(found, {"id": UC_A, "title": "MMA Daily"})
        service.channels.return_value.list.assert_called_once_with(
            part="snippet", forHandle="@mmadaily"
        )
        self.spent.assert_called_once_with(units=1)

    def test_resolve_of_nothing_asks_nothing(self):
        from analytics import competitor_list

        service = MagicMock()
        self.assertIsNone(competitor_list.resolve(service, "mma daily"))
        service.channels.assert_not_called()


class SuggestTests(_ListCase):
    def _service(self, by_query, sizes=None):
        service = MagicMock()

        def _list(**kwargs):
            call = MagicMock()
            call.execute.return_value = {"items": by_query.get(kwargs["q"], [])}
            return call

        service.search.return_value.list.side_effect = _list
        service.channels.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": cid, "statistics": {"subscriberCount": str(subs), "videoCount": "120"}}
                for cid, subs in (sizes or {}).items()
            ]
        }
        return service

    def _item(self, cid, title, about=""):
        return {"id": {"channelId": cid}, "snippet": {"title": title, "description": about}}

    def test_a_shortlist_is_printed_and_nothing_is_added(self):
        from analytics import competitor_list

        service = self._service(
            {"UFC shorts": [self._item(UC_A, "MMA Daily", "Daily UFC news in 60 seconds")]}
        )
        rows = competitor_list.suggest("tapin", service, queries=["UFC shorts"])
        self.assertEqual(rows[0]["id"], UC_A)
        self.assertEqual(rows[0]["query"], "UFC shorts")
        lines = "\n".join(competitor_list.suggestion_lines("tapin", rows))
        self.assertIn("MMA Daily - Daily UFC news in 60 seconds", lines)
        self.assertIn(f"competitors add --source {UC_A}", lines)
        self.assertIn("Nothing was added", lines)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "tapin.json")))
        self.assertEqual([c.kwargs["units"] for c in self.spent.call_args_list], [100, 1])

    def test_sizes_sort_the_shortlist_and_drop_tiny_channels(self):
        from analytics import competitor_list

        uc_c = "UC" + "c" * 22
        service = self._service(
            {
                "UFC news": [
                    self._item(UC_A, "Small MMA"),
                    self._item(UC_B, "Big MMA"),
                    self._item(uc_c, "Tiny MMA"),
                ]
            },
            sizes={UC_A: 52000, UC_B: 1400000, uc_c: 40},
        )
        rows = competitor_list.suggest("tapin", service, queries=["UFC news"])
        self.assertEqual([r["title"] for r in rows], ["Big MMA", "Small MMA"])
        lines = "\n".join(competitor_list.suggestion_lines("tapin", rows))
        self.assertIn("Big MMA (1.4M subscribers, 120 videos)", lines)
        self.assertIn("Small MMA (52K subscribers, 120 videos)", lines)

    def test_a_title_with_a_line_break_prints_on_one_line(self):
        from analytics import competitor_list

        service = self._service({"UFC news": [self._item(UC_A, "Malek\nBasket")]})
        rows = competitor_list.suggest("tapin", service, queries=["UFC news"])
        self.assertEqual(rows[0]["title"], "Malek Basket")

    def test_a_channel_already_watched_or_seen_twice_is_left_out(self):
        from analytics import competitor_list

        competitor_list.add("tapin", UC_A, "MMA Daily")
        service = self._service(
            {
                "UFC shorts": [self._item(UC_A, "MMA Daily"), self._item(UC_B, "Octagon Cuts")],
                "NFL shorts": [self._item(UC_B, "Octagon Cuts")],
            }
        )
        rows = competitor_list.suggest("tapin", service, queries=["UFC shorts", "NFL shorts"])
        self.assertEqual([r["id"] for r in rows], [UC_B])

    def test_the_searches_come_from_the_channels_own_niches(self):
        from analytics.competitor_list import niche_queries

        queries = niche_queries("tapin")
        self.assertEqual(len(queries), 4)
        self.assertIn("UFC news", queries)
        self.assertEqual(queries[-1], "gaming news")
        self.assertTrue(all(q.endswith(" news") for q in queries))

    def test_the_upload_reserve_refuses_a_search(self):
        from analytics import competitor_list

        with (
            patch.dict("os.environ", {"COMPETITOR_SYNC_RESERVE_UNITS": "1600"}),
            patch("apis.youtube_quota.get_usage_summary", return_value={"remaining": 1650}),
        ):
            self.assertIn("kept for uploads", competitor_list.block_reason(300) or "")
            self.assertIsNone(competitor_list.block_reason(1))


class WhereItIsUsedTests(_ListCase):
    def _run(self, command, **kwargs):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS[command][1](Namespace(channel="tapin", **kwargs))
        return code, buf.getvalue()

    def test_ops_competitors_lists_and_removes(self):
        from analytics import competitor_list

        competitor_list.add("tapin", UC_A, "MMA Daily")
        code, text = self._run("competitors", target="list", source=None, name="")
        self.assertEqual(code, 0)
        self.assertIn(f"MMA Daily  [{UC_A}]", text)
        code, text = self._run("competitors", target="remove", source="mma", name="")
        self.assertEqual(code, 0)
        self.assertIn("Removed: MMA Daily", text)

    def test_ops_competitors_add_resolves_then_stores(self):
        service = MagicMock()
        service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": UC_A, "snippet": {"title": "MMA Daily"}}]
        }
        with (
            patch("analytics.competitor_sync._get_youtube_service", return_value=service),
            patch("analytics.competitor_list.block_reason", return_value=None),
        ):
            code, text = self._run("competitors", target="add", source="@mmadaily", name="")
        self.assertEqual(code, 0, text)
        self.assertIn(f"Added: MMA Daily [{UC_A}]", text)
        self.assertEqual(self._stored(), [{"id": UC_A, "label": "MMA Daily"}])

    def test_a_kept_shortlist_is_reprinted_without_a_search(self):
        from analytics import competitor_list

        rows = [{"id": UC_A, "title": "MMA Daily", "about": "", "query": "UFC news"}]
        with patch.object(
            competitor_list,
            "_shortlist_path",
            return_value=os.path.join(self.tmp.name, "shortlist.json"),
        ):
            competitor_list.save_shortlist("tapin", rows)
            with patch("analytics.competitor_sync._get_youtube_service") as service:
                code, text = self._run(
                    "competitors", target="suggest", source=None, name="", force=False
                )
            service.assert_not_called()
            self.assertEqual(code, 0)
            self.assertIn("no quota spent", text)
            self.assertIn(f"competitors add --source {UC_A}", text)
            # once approved it leaves the shortlist
            competitor_list.add("tapin", UC_A, "MMA Daily")
            self.assertEqual(competitor_list.load_shortlist("tapin")[1], [])

    def test_an_old_shortlist_is_not_reused(self):
        from datetime import date, timedelta

        from analytics import competitor_list

        rows = [{"id": UC_A, "title": "MMA Daily", "about": "", "query": "UFC news"}]
        with patch.object(
            competitor_list,
            "_shortlist_path",
            return_value=os.path.join(self.tmp.name, "shortlist.json"),
        ):
            competitor_list.save_shortlist("tapin", rows)
            later = date.today() + timedelta(days=8)
            self.assertEqual(competitor_list.load_shortlist("tapin", today=later), ("", []))
            self.assertEqual(len(competitor_list.load_shortlist("tapin")[1]), 1)

    def test_ops_competitors_suggest_stops_at_the_reserve(self):
        with (
            patch("analytics.competitor_list.block_reason", return_value="1650 units left"),
            patch("analytics.competitor_list.load_shortlist", return_value=("", [])),
        ):
            code, text = self._run("competitors", target="suggest", source=None, name="")
        self.assertEqual(code, 1)
        self.assertIn("Not run: 1650 units left", text)

    def test_competitor_health_prints_the_breakouts(self):
        from core import competitor_health

        snap = _snapshot([1000, 1000, 1000, 1000, 9000])
        with (
            patch.object(competitor_health, "_load_snapshot", return_value=snap),
            patch.object(
                competitor_health,
                "inspect_competitors",
                return_value=competitor_health.CompetitorHealth(channel_id="tapin"),
            ),
        ):
            _code, text = self._run("competitor-health")
        self.assertIn("Breakout videos on the channels you watch", text)
        self.assertIn("9.0x  Video 4", text)

    def test_best_bets_may_offer_a_breakout_with_its_source(self):
        from core import best_bet

        snap = _snapshot([1000, 1000, 1000, 1000, 9000])
        snap["competitors"][0]["recent_videos"][4]["title"] = "UFC 325 Topuria knockout reaction"
        with patch("analytics.competitor_context.load_competitor_snapshot", return_value=snap):
            rows = best_bet._competitor_outlier_candidates(
                "tapin", allowed={"ufc", "gaming", "nfl"}, exclude=set(), seen_local=set()
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["topic"], "UFC 325 Topuria knockout reaction")
        self.assertEqual(rows[0]["source"], "MMA Daily breakout, 9.0x their median")

    def test_a_breakout_already_covered_is_not_offered_again(self):
        from core import best_bet
        from core.best_bet import normalize_seed_topic

        snap = _snapshot([1000, 1000, 1000, 1000, 9000])
        title = "UFC 325 Topuria knockout reaction"
        snap["competitors"][0]["recent_videos"][4]["title"] = title
        with patch("analytics.competitor_context.load_competitor_snapshot", return_value=snap):
            rows = best_bet._competitor_outlier_candidates(
                "tapin",
                allowed={"ufc"},
                exclude={normalize_seed_topic(title).lower()},
                seen_local=set(),
            )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
