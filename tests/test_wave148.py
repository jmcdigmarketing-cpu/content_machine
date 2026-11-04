"""Wave 148 (2026-11-04) - the next five, S01 (long-form hours) the shortfall it takes.

#1989 a series playlist keeps its block on top; #1987 the videos already in a playlist are moved
into binge order a little each day; #1985 a video with no views in its window is recorded synced,
with 0 (run 202); #1986 the paid views on uploads the publish log does not hold are found and named
(4,112 on five December 2025 videos); #1732 a long video's length by its format, capped by its
facts; #1745 each long video's first 30 seconds measured and its opener learned.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Imported before any patch below: a module first imported under a patch of a name it imports
# binds the mock for the rest of the process (wave 145's reversed-suite failure).
import analytics.growth
import analytics.hook_learning
import analytics.youtube_metrics
import apis.youtube_quota
import core.batch_generation
import core.playlists
import core.series.long_form
import jobs.worker
import youtube.channel_uploads

UTC = timezone.utc


def _store(tmp: str, data: dict) -> str:
    path = os.path.join(tmp, "playlists.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return path


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ---- #1989: a series playlist keeps its block on top -----------------------------------------------


class SeriesBlockTests(unittest.TestCase):
    def test_a_new_video_goes_in_after_the_countdown(self):
        service = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp, {"ids": {"GTA": "PL1", "Gaming": "PL2"},
                                 "series": {"GTA": ["c21", "c20", "c19"]}})  # fmt: skip
            with patch("youtube.oauth.token_has_scope", return_value=True):
                core.playlists.add_to_playlists(service, "tapin", "news", title="GTA 6 leaks a map",
                                                store_path=store)  # fmt: skip
            self.assertEqual(_read(store)["series"]["GTA"], ["c21", "c20", "c19"])
        bodies = [
            c.kwargs["body"]["snippet"] for c in service.playlistItems().insert.call_args_list
        ]
        self.assertEqual(
            [(b["playlistId"], b["position"]) for b in bodies], [("PL1", 3), ("PL2", 0)]
        )


# ---- #1987: the playlists' older videos into binge order -------------------------------------------


def _item(item_id: str, video: str, day: str, position: int) -> dict:
    return {"id": item_id, "video_id": video, "published_at": f"2026-10-{day}T16:00:00Z",
            "position": position}  # fmt: skip


ITEMS = [_item("i1", "a", "20", 0), _item("i2", "b", "22", 1), _item("i3", "c", "25", 2),
         _item("i4", "c19", "31", 3), _item("i5", "c20", "30", 4)]  # fmt: skip


def _apply(current: list[str], moves: list[tuple[str, int]]) -> list[str]:
    now = list(current)
    for item, position in moves:
        now.remove(item)
        now.insert(position, item)
    return now


class BingeOrderTests(unittest.TestCase):
    def test_the_series_first_then_newest_first(self):
        from core.playlists import desired_order

        self.assertEqual(desired_order(ITEMS, ["c20", "c19"]), ["i5", "i4", "i3", "i2", "i1"])
        self.assertEqual(desired_order(ITEMS, []), ["i4", "i5", "i3", "i2", "i1"])

    def test_the_moves_reach_it(self):
        from core.playlists import order_moves

        current, desired = ["i1", "i2", "i3", "i4"], ["i4", "i3", "i2", "i1"]
        moves = order_moves(current, desired)
        self.assertEqual(len(moves), 3)
        self.assertEqual(_apply(current, moves), desired)
        self.assertEqual(order_moves(desired, desired), [])

    def _service(self, pages: dict[str, list[dict]]):
        service = MagicMock()

        def listing(**kwargs):
            items = [{"id": i["id"], "snippet": {"position": i["position"]},
                      "contentDetails": {"videoId": i["video_id"],
                                         "videoPublishedAt": i["published_at"]}}
                     for i in pages[kwargs["playlistId"]]]  # fmt: skip
            return SimpleNamespace(execute=lambda: {"items": items})

        service.playlistItems().list.side_effect = listing
        return service

    def test_a_day_moves_what_the_budget_allows_and_records_the_rest(self):
        service = self._service({"PL1": ITEMS})
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp, {"ids": {"GTA": "PL1"}, "series": {"GTA": ["c20", "c19"]},
                                 "added": {"a": ["GTA"]}})  # fmt: skip
            lines = core.playlists.reorder_playlists("tapin", service, budget=120,
                                                     store_path=store, today="2026-11-05")  # fmt: skip
            again = core.playlists.reorder_playlists("tapin", service, budget=120,
                                                     store_path=store, today="2026-11-05")  # fmt: skip
            order = _read(store)["order"]
        updates = [c.kwargs["body"] for c in service.playlistItems().update.call_args_list]
        self.assertEqual(
            [(u["id"], u["snippet"]["position"]) for u in updates], [("i5", 0), ("i4", 1)]
        )
        self.assertEqual(updates[0]["snippet"]["resourceId"]["videoId"], "c20")
        self.assertEqual(order, {"day": "2026-11-05", "moved": 2, "left": {"GTA": 2}})
        self.assertEqual(lines, ["GTA: 2 moved, 2 to go"])
        self.assertEqual(again, [])  # once a day

    def test_the_budget_leaves_two_uploads(self):
        def summary(remaining):
            return patch(
                "apis.youtube_quota.get_usage_summary", return_value={"remaining": remaining}
            )

        with patch.dict(os.environ, {"PLAYLIST_ORDER_UNITS": ""}):
            with summary(10_000):
                self.assertEqual(core.playlists.order_budget(), 1000)
            with summary(3_500):
                self.assertEqual(core.playlists.order_budget(), 300)
            with summary(2_000):
                self.assertEqual(core.playlists.order_budget(), 0)
        with summary(10_000):
            self.assertEqual(core.playlists.order_budget(), 0)  # the suite pins it off
        self.assertEqual(apis.youtube_quota.API_UNITS["playlistItems.update"], 50)

    def test_what_is_left_is_said(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "playlists_tapin.json")
            with patch.object(core.playlists, "store_path_for", return_value=path):
                self.assertEqual(core.playlists.order_line("tapin"), "")
                _store(tmp, {})
                os.replace(os.path.join(tmp, "playlists.json"), path)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump({"order": {"day": "2026-11-05", "moved": 20,
                                         "left": {"Gaming": 2, "GTA": 0}}}, handle)  # fmt: skip
                self.assertEqual(core.playlists.order_line("tapin"), "Playlist order (#1987): 2 "
                                 "moves to go - Gaming 2 (20 moved on 2026-11-05).")  # fmt: skip

    def test_the_worker_spends_nothing_in_the_suite(self):
        with patch("youtube.oauth.get_youtube_service") as service:
            self.assertEqual(jobs.worker._order_playlists(), 0)
        service.assert_not_called()


# ---- #1985: an empty window is a window with no views ---------------------------------------------


class EmptyWindowTests(unittest.TestCase):
    def test_the_query_says_it_was_empty(self):
        ym = analytics.youtube_metrics
        service = MagicMock()
        service.reports().query().execute.return_value = {"columnHeaders": [{"name": "video"}],
                                                          "rows": []}  # fmt: skip
        window: dict = {}
        with (
            patch.object(ym, "_analytics_enabled", return_value=True),
            patch.object(ym, "get_youtube_analytics_service", return_value=service),
        ):
            self.assertIsNone(
                ym.fetch_video_metrics("v202", channel_id="tapin", empty_window=window)
            )
        self.assertEqual(set(window), {"period_start", "period_end"})

    def _row(self, days_ago: float, metrics: dict):
        return SimpleNamespace(id=1669, published_at=datetime.now(UTC) - timedelta(days=days_ago),
                               metrics_json=json.dumps(metrics))  # fmt: skip

    def test_run202_is_recorded_synced_with_no_views(self):
        ym = analytics.youtube_metrics
        repo = MagicMock()
        row = self._row(7, {"lifetime_views": 0, "thumbnail_impressions": 139})
        window = {"period_start": "2026-10-07", "period_end": "2026-11-04"}
        with (
            patch.object(ym, "get_publish_log_repository", return_value=repo),
            patch.object(ym, "_existing_publish_row", return_value=row),
        ):
            self.assertTrue(ym._record_empty_window("tapin", 202, 1669, window))
        stored = json.loads(repo.update.call_args.args[1]["metrics_json"])
        self.assertEqual((stored["views"], stored["estimated_minutes_watched"]), (0, 0))
        self.assertEqual((stored["period_end"], stored["window_empty"]), ("2026-11-04", True))
        self.assertEqual(stored["thumbnail_impressions"], 139)

    def test_not_while_the_report_may_still_be_catching_up(self):
        ym = analytics.youtube_metrics
        repo = MagicMock()
        with (
            patch.object(ym, "get_publish_log_repository", return_value=repo),
            patch.object(ym, "_existing_publish_row", return_value=self._row(1, {})),
        ):
            self.assertFalse(ym._record_empty_window("tapin", 232, 1, {"period_end": "x"}))
        repo.update.assert_not_called()

    def test_the_sync_records_it_and_a_window_with_views_clears_it(self):
        ym = analytics.youtube_metrics
        repo = MagicMock()
        row = self._row(7, {"lifetime_views": 0, "window_empty": True, "snapshots": {"24h": {}}})

        def empty(_video, *, channel_id, empty_window):
            empty_window.update(period_start="2026-10-07", period_end="2026-11-04")

        with (
            patch.object(ym, "get_publish_log_repository", return_value=repo),
            patch.object(ym, "_existing_publish_row", return_value=row),
            patch.object(ym, "fetch_video_metrics", side_effect=empty),
            patch.object(ym, "_record_empty_window") as record,
        ):
            self.assertFalse(ym.refresh_publish_metrics(content_run_id=202, youtube_video_id="v",
                                                        channel_id="tapin", publish_log_id=1669))  # fmt: skip
        record.assert_called_once()
        with (
            patch.object(ym, "get_publish_log_repository", return_value=repo),
            patch.object(ym, "_existing_publish_row", return_value=row),
            patch.object(ym, "fetch_video_metrics", return_value={"views": 3, "engaged_rate": 0.4}),
            patch.object(ym, "record_publish_outcome"),
        ):
            ym.refresh_publish_metrics(content_run_id=202, youtube_video_id="v",
                                       channel_id="tapin", publish_log_id=1669)  # fmt: skip
        stored = json.loads(repo.update.call_args.args[1]["metrics_json"])
        self.assertNotIn("window_empty", stored)
        self.assertEqual(stored["views"], 3)


# ---- #1986: paid views on uploads the publish log does not hold ------------------------------------


class OutsidePaidTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        template = os.path.join(self.tmp.name, "paid_outside_{channel}.json")
        rows = [SimpleNamespace(youtube_video_id="v170", metrics_json=json.dumps(
            {"lifetime_paid_views": 37270, "lifetime_paid_at": "x"}))]  # fmt: skip
        for item in (
            patch.object(analytics.youtube_metrics, "OUTSIDE_PAID_TEMPLATE", template),
            patch.object(analytics.youtube_metrics, "get_publish_log_repository",
                         return_value=SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)),
        ):  # fmt: skip
            item.start()
            self.addCleanup(item.stop)

    def test_the_unlogged_uploads_are_asked(self):
        uploads = [{"video_id": "v170", "title": "MW4", "published_at": "2026-10-19"},
                   {"video_id": "llUT", "title": "Wemby", "published_at": "2025-12-31T17:00:00Z"},
                   {"video_id": "hAtH", "title": "Glitched", "published_at": "2025-12-30"},
                   {"video_id": "none", "title": "Quiet", "published_at": "2025-12-01"}]  # fmt: skip
        paid = {"llUT": [["2026-09-26", 1172], ["2026-10-25", 141]], "hAtH": [["2026-09-26", 475]],
                "none": []}  # fmt: skip
        asked: list[str] = []

        def fetch(video, *, channel_id, start, end):
            asked.append(video)
            return paid[video]

        got = analytics.youtube_metrics.fetch_paid_outside(
            "tapin", today=date(2026, 11, 4), uploads=uploads, fetch=fetch
        )
        self.assertEqual(asked, ["llUT", "hAtH", "none"])  # not the logged one
        self.assertEqual((got["total"], got["asked"]), (1788, 3))
        self.assertEqual([v["video_id"] for v in got["videos"]], ["llUT", "hAtH"])

    def test_asked_weekly_while_youtube_runs_ahead(self):
        ym = analytics.youtube_metrics
        today = date(2026, 11, 4)
        self.assertTrue(ym.paid_outside_due("tapin", {"shorts_paid_90d": 44114}, today=today))
        self.assertFalse(ym.paid_outside_due("tapin", {"shorts_paid_90d": 37300}, today=today))
        with patch.object(ym, "fetch_paid_outside", return_value={
            "as_of": "2026-11-04", "videos": [{"video_id": "llUT", "paid": 4112}], "asked": 51,
            "total": 4112}):  # fmt: skip
            line = ym.sync_paid_outside("tapin", {"shorts_paid_90d": 44114}, today=today)
        self.assertIn("4,112 on 1 of 51 unlogged uploads", line)
        self.assertEqual(ym.load_paid_outside("tapin")["total"], 4112)
        self.assertFalse(ym.paid_outside_due("tapin", {"shorts_paid_90d": 44114},
                                             today=today + timedelta(days=3)))  # fmt: skip
        self.assertTrue(ym.paid_outside_due("tapin", {"shorts_paid_90d": 44114},
                                            today=today + timedelta(days=8)))  # fmt: skip

    def test_the_paid_line_says_where(self):
        rep = {"paid_share": 0.75, "paid": {"views": 40002, "videos": 3, "of": 97,
               "channel_90d": 44114, "outside": {"total": 4112, "videos": 5, "as_of": "2026-11-04",
                                                 "oldest": "2025-12"}}}  # fmt: skip
        self.assertTrue(analytics.growth.paid_line(rep).endswith(
            "4,112 of them are not in these videos' synced days: 4,112 on 5 uploads the publish "
            "log does not hold, from 2025-12 (asked 2026-11-04)"))  # fmt: skip

    def test_every_page_of_uploads_is_read(self):
        service = MagicMock()
        service.channels().list().execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]
        }

        def page(item: str, token: str | None) -> dict:
            out = {"items": [{"snippet": {"resourceId": {"videoId": item}, "title": item},
                              "contentDetails": {}}]}  # fmt: skip
            return {**out, "nextPageToken": token} if token else out

        service.playlistItems().list().execute.side_effect = [page("a", "t2"), page("b", None)]
        service.playlistItems().list.reset_mock()
        got = youtube.channel_uploads.uploads_playlist_items(service, pages=10)
        self.assertEqual([g["video_id"] for g in got], ["a", "b"])
        calls = service.playlistItems().list.call_args_list
        self.assertNotIn("pageToken", calls[0].kwargs)
        self.assertEqual(calls[1].kwargs["pageToken"], "t2")


# ---- #1732: a long video's length by its format ---------------------------------------------------


class LongLengthTests(unittest.TestCase):
    def test_the_facts_cap_the_words(self):
        from core.series.long_form import long_word_range

        self.assertEqual(long_word_range("GTA 6 editions explained", 0), (1584, 2376))  # 8-12 min
        self.assertEqual(long_word_range("GTA 6 editions explained", 12), (1170, 1560))
        self.assertEqual(long_word_range("GTA 6 editions explained", 2), (450, 600))
        self.assertEqual(long_word_range("UFC 334 recap: every finish and what's next", 21),
                         (1188, 1980))  # fmt: skip

    def test_the_long_draft_takes_it(self):
        from tests.test_wave145 import _draft_kwargs

        topic = "GTA 6 editions explained"
        facts = [f"IGN reported: GTA 6 edition detail {n}" for n in range(12)]
        bet = {"offered": [{"topic": topic, "source": "long", "domain": "gaming"}], "picked": 1,
               "draft_kind": "long", "facts": facts}  # fmt: skip
        self.assertEqual(_draft_kwargs(topic, bet)["word_range"], (1170, 1560))
        short = {"offered": [{"topic": topic, "source": "trending", "domain": "gaming"}],
                 "picked": 1}  # fmt: skip
        self.assertNotIn("word_range", _draft_kwargs(topic, short))

    def test_the_pipeline_hands_the_writer_the_range(self):
        from core.pipeline import DiscoveryResult, run_pipeline

        discovery = DiscoveryResult(input_topic="GTA 6", base_signals={},
                                    evaluated=[("GTA 6 editions", 100.0, {})], channel_id="tapin")  # fmt: skip
        with (
            patch("core.pipeline.write_run_dossier"),
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=78),
            patch("core.pipeline.build_research_brief",
                  return_value=SimpleNamespace(version="v1", to_prompt_block=lambda: "")),
            patch("core.pipeline.generate_content_package",
                  return_value={"title": "T", "script": "Hook. Body.", "description": "d"}) as content,
            patch("core.llm_router.complete_json", side_effect=RuntimeError("extract down")),
            patch("builtins.print"),
        ):  # fmt: skip
            run_pipeline("GTA 6", discovery=discovery, variant_index=0, length_choice="4",
                         proceed_video=False, channel_id="tapin", word_range=(1170, 1560))  # fmt: skip
        self.assertEqual(content.call_args.kwargs["word_range"], (1170, 1560))


# ---- #1745: each long video's first 30 seconds ----------------------------------------------------


def _long(run_id: int, held: float, hook_traits: set[str], kind: str = "long") -> dict:
    return {"run_id": run_id, "title": f"Long {run_id}", "kind": kind, "hook": f"Opener {run_id}",
            "traits": hook_traits, "held": held}  # fmt: skip


class LongOpenerTests(unittest.TestCase):
    def test_each_long_video_is_read_30_seconds_in(self):
        curve = [[0.0, 1.0], [0.05, 0.62], [0.5, 0.3], [1.0, 0.1]]
        row = SimpleNamespace(youtube_video_id="vL", content_run_id=301, metrics_json=json.dumps(
            {"retention_curve": curve}))  # fmt: skip
        run = SimpleNamespace(id=301, title="GTA 6 editions explained",
                              features_json=json.dumps({"long_form": True}))  # fmt: skip
        hl = analytics.hook_learning
        with (
            patch.object(hl, "_publish_repo",
                         return_value=SimpleNamespace(list_uploaded_for_channel=lambda _c: [row])),
            patch.object(hl, "_run_repo", return_value=SimpleNamespace(get=lambda _i: run)),
            patch("core.retention._render_seconds", return_value=600.0),
            patch("core.runs.script_report.script_of",
                  return_value="Rockstar priced the Gold edition at $99. Here is why."),
        ):  # fmt: skip
            rows = hl.long_rows("tapin")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["held"], 0.62, places=2)  # 30 s of 600 is 5% in
        self.assertIn("a number", rows[0]["traits"])

    def test_the_opener_is_learned_only_from_enough_scripted_videos(self):
        hl = analytics.hook_learning
        few = [_long(1, 0.6, {"a number"}), _long(2, 0.3, set())]
        with patch.object(hl, "long_rows", return_value=few):
            self.assertEqual(hl.long_opener_guidance("tapin"), "")
            lines = hl.long_opener_lines("tapin")
        self.assertIn("2 measured, 2 scripted (their openers teach from 5)", lines[0])
        self.assertIn("60% still watching at 30 s - Long 1", lines[1])
        many = [_long(n, 0.6, {"a number"}) for n in range(3)]
        many += [_long(10 + n, 0.35, set()) for n in range(3)]
        many.append(_long(20, 0.9, set(), kind="compilation"))  # never learned from
        with patch.object(hl, "long_rows", return_value=many):
            guidance = hl.long_opener_guidance("tapin")
        self.assertIn("open with a number", guidance)
        self.assertIn("kept 60% watching at 30 s, against 35% without", guidance)

    def test_the_long_draft_carries_it(self):
        from tests.test_wave145 import _draft_kwargs

        topic = "GTA 6 editions explained"
        bet = {"offered": [{"topic": topic, "source": "long", "domain": "gaming"}], "picked": 1,
               "draft_kind": "long"}  # fmt: skip
        with patch("analytics.hook_learning.long_opener_guidance", return_value="LONG OPENER: x"):
            self.assertIn("LONG OPENER: x", _draft_kwargs(topic, bet)["directions"])
            short = {"offered": [{"topic": topic, "source": "trending", "domain": "gaming"}],
                     "picked": 1}  # fmt: skip
            self.assertNotIn("LONG OPENER", _draft_kwargs(topic, short)["directions"])


if __name__ == "__main__":
    unittest.main()
