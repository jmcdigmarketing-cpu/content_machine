"""Wave 135 (2026-10-30) - the countdown a day ahead, then the look list and the scoreboard's rest.

D1 (the operator: "A day ahead"): countdown days 21 and 20 were missed. The PC was off at 5 AM on
10-29, and on 10-30 overnight ran at 5:44 PM, drafted day 20 and gave its one render to a game. Now
each night also drafts tomorrow's countdown, renders countdowns outside the night's limit, and
uploads them scheduled for their own noon, so YouTube publishes them with the PC off.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
ROW = {"id": "gta6-countdown", "kind": "countdown", "subject": "GTA 6", "names": ["GTA 6"],
       "title": "GTA 6: {n} days to launch", "from": "2026-10-29", "until": "2026-11-19",
       "domain": "gaming", "playlist": "GTA"}  # fmt: skip
POWER_ON = datetime(2026, 10, 30, 22, 44, tzinfo=timezone.utc)  # 5:44 PM CDT, 10-30


def _idea(now, ahead=0):
    from core.series import countdown

    with (
        patch.dict(os.environ, {"SERIES_COUNTDOWN": "true"}),
        patch.object(countdown, "series_rows", return_value=[ROW]),
        patch.object(countdown, "channel_zone", return_value=EASTERN),
        patch("core.batch_generation.series_drafted", return_value=False),
    ):
        return countdown.countdown_idea("tapin", now=now, headlines=lambda *_a: [], ahead=ahead)


class CountdownAheadTests(unittest.TestCase):
    def test_a_countdown_goes_public_at_its_own_noon(self):
        idea = _idea(POWER_ON)
        self.assertEqual(idea.topic, "GTA 6: 20 days to launch")
        self.assertEqual(idea.publish_at, "2026-10-30T16:00:00+00:00")  # noon EDT
        ahead = _idea(POWER_ON, ahead=1)
        self.assertEqual(ahead.topic, "GTA 6: 19 days to launch")
        self.assertEqual(ahead.publish_at, "2026-10-31T16:00:00+00:00")
        self.assertEqual(ahead.deadline, "2026-11-01T04:00:00+00:00")

    def test_overnight_drafts_tomorrows_too(self):
        from core import batch_generation as bg
        from core.best_bet import BestBetResult

        def bet(topic, source="trending", **extra):
            return BestBetResult(topic=topic, domain="gaming", avg_engaged_rate=0.0,
                                 source=source, supporting_runs=0, rationale="",
                                 outlets=4, **extra)  # fmt: skip

        today = bet("GTA 6: 20 days to launch", "countdown")
        tomorrow = bet(
            "GTA 6: 19 days to launch", "countdown", publish_at="2026-10-31T16:00:00+00:00"
        )
        picks: dict = {}
        with (
            patch("core.best_bet.get_idea_menu", return_value=([today, bet("idea 0")], [])),
            patch("core.series.countdown.countdown_idea", return_value=tomorrow),
        ):
            topics = bg.collect_topics("tapin", count=1, picks=picks)
        self.assertEqual(topics, [today.topic, tomorrow.topic, "idea 0"])
        self.assertEqual(picks[tomorrow.topic]["publish_at"], "2026-10-31T16:00:00+00:00")

    def test_a_full_queue_drafts_both_once(self):
        from core import batch_generation as bg
        from core.best_bet import BestBetResult

        same = BestBetResult(topic="GTA 6: 20 days to launch", domain="gaming",
                             avg_engaged_rate=0.0, source="countdown", supporting_runs=0,
                             rationale="")  # fmt: skip
        with patch("core.series.countdown.countdown_idea", return_value=same):
            self.assertEqual(bg.collect_topics("tapin", count=0), [same.topic])

    def test_day_one_has_no_tomorrow(self):
        self.assertIsNone(_idea(datetime(2026, 11, 19, 15, tzinfo=timezone.utc)))


def _draft(run_id, *, series=""):
    from core.batch_review import PendingDraft

    meta = {"run_id": run_id, "topic": f"t{run_id}", "title": f"title {run_id}"}
    if series:
        meta["series"] = series
    return PendingDraft(folder=f"f{run_id}", meta=meta, script="One. Two.")


class CountdownRenderTests(unittest.TestCase):
    """10-30: one render a night, and the Lakers preview (sooner event) took it from day 20."""

    def _night(self, limit, pause=""):
        from core import batch_review as br

        game, countdown = _draft(218), _draft(216, series="countdown")
        rendered, queued, scheduled = [], [], []
        with (
            patch.object(br, "unattended_candidates", return_value=([game, countdown], [])),
            patch.object(br, "shelf_max", return_value=0),
            patch.object(br, "shelf_pause", return_value=pause),
            patch.object(br, "second_read", return_value=""),
            patch.object(br, "_smoke_failure", return_value=""),
            patch.object(br, "_memory_short", return_value=""),
            patch.object(br, "_disk_short", return_value=""),
            patch.object(br, "_write_review"),
            patch("core.nightly_task.beat_step"),
            patch.object(br, "_queue_scheduled", side_effect=lambda r, c: scheduled.append(r) or 1),
        ):
            br.render_unattended("tapin", limit,
                                 render=lambda d, _o: rendered.append(d.run_id) or True,
                                 queue=lambda r, c: queued.append(r) or 1)  # fmt: skip
        return rendered, queued, scheduled

    def test_a_countdown_renders_first_and_outside_the_limit(self):
        rendered, queued, scheduled = self._night(1)
        self.assertEqual(rendered, [216, 218])
        self.assertEqual(scheduled, [216])  # its own noon, not unlisted
        self.assertEqual(queued, [218])

    def test_a_full_shelf_still_renders_the_countdown(self):
        rendered, _queued, scheduled = self._night(1, pause="3 finished videos wait")
        self.assertEqual((rendered, scheduled), ([216], [216]))

    def test_no_limit_still_renders_the_countdown(self):
        rendered, _queued, scheduled = self._night(0)
        self.assertEqual((rendered, scheduled), ([216], [216]))

    def test_the_scheduled_upload_uses_its_slot(self):
        from core import batch_review as br

        when = datetime(2026, 10, 31, 16, tzinfo=timezone.utc)
        with (
            patch("core.spaced_queue.slot_for_run", return_value=(when, "")),
            patch("analytics.queue_manager.requeue_content_run", return_value=7) as requeue,
        ):
            br._queue_scheduled(216, "tapin")
        kwargs = requeue.call_args.kwargs
        self.assertEqual(kwargs["youtube_publish_at"], when)
        self.assertEqual(kwargs["privacy_status"], "private")  # YouTube's scheduled publish

    def test_a_countdown_says_its_day_ends(self):
        from core.batch_review import event_word

        self.assertEqual(event_word({"series": "countdown"}), "its day ends")
        self.assertEqual(event_word({}), "kicks off")


class _OwnStores(unittest.TestCase):
    def setUp(self):
        import tempfile

        from config import paths

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name in ("CLIP_USES_FILE", "COVERS_FILE"):
            patcher = patch.object(paths, name, os.path.join(tmp.name, name.lower() + ".json"))
            patcher.start()
            self.addCleanup(patcher.stop)


class RotationTests(_OwnStores):
    """L3 (look_and_feel.md): a folder's clips were drawn by file name, at most 12, so different
    runs started from the same first files - two GTA 6 Shorts opened on one dark car."""

    def test_every_clip_plays_before_any_third_use(self):
        from assets.clip_ledger import least_used, record_uses, uses

        clips = [f"C:/lib/GTA V/clip{i:02d}.mp4" for i in range(30)]
        counts: dict[str, int] = {}
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        for video in range(5):  # 60 picks over 30 clips
            pool = least_used(clips, 12)
            record_uses(pool, when=start + timedelta(hours=video))
            for clip in pool:
                counts[clip] = counts.get(clip, 0) + 1
        self.assertEqual(len(counts), 30)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        self.assertTrue(uses())

    def test_the_first_pick_is_not_the_first_twelve_by_name_after_use(self):
        from assets.clip_ledger import least_used, record_uses

        clips = [f"C:/lib/GTA V/clip{i:02d}.mp4" for i in range(30)]
        record_uses(clips[:12])
        self.assertEqual(least_used(clips, 12), clips[12:24])

    def test_the_fast_cut_reads_the_ledger(self):
        import inspect

        from assets import fast_cut

        self.assertIn("least_used(", inspect.getsource(fast_cut._clip_pool))
        self.assertIn("record_uses(", inspect.getsource(fast_cut._compose))


class FootageLedgerTests(_OwnStores):
    """L4: what each clip did - uses in 30 days, and the clips never used."""

    def test_the_folder_report(self):
        import tempfile

        from assets.clip_ledger import record_uses, report_lines

        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "GTA V")
            os.makedirs(folder)
            for i in range(4):
                open(os.path.join(folder, f"c{i}.mp4"), "wb").close()
            for _ in range(3):
                record_uses([os.path.join(folder, "c0.mp4")])
            text = "\n".join(report_lines([folder]))
        self.assertIn("GTA V", text)
        self.assertIn("3 uses", text)
        self.assertIn("3 never used", text)
        self.assertIn("most: c0.mp4 (3)", text)


class MenuClipTests(unittest.TestCase):
    """L5: an untagged FC Barcelona squad menu backed the Kane, Real Madrid and Man City Shorts."""

    FOLDER = "C:/lib/gaming/sports/EA Sports FC"

    def _index(self):
        return {"clips": {
            f"{self.FOLDER}/EA SPORTS FC 26 2026-08-19 12-40-15.mp4": {"motion": 4.52},
            f"{self.FOLDER}/fc26 gameplay.mp4": {"motion": 23.6},
            f"{self.FOLDER}/fc26 squad menu.mp4": {},
            f"{self.FOLDER}/fc26 tagged.mp4": {"tags": ["ui"], "motion": 30.0},
        }}  # fmt: skip

    def test_a_club_story_gets_action_clips_only(self):
        from assets.clip_tags import without_ui

        clips = list(self._index()["clips"])
        kept = without_ui(clips, "Real Madrid finally show their potential under Mourinho",
                          index=self._index())  # fmt: skip
        self.assertEqual([os.path.basename(c) for c in kept], ["fc26 gameplay.mp4"])

    def test_a_story_about_the_game_keeps_its_menus(self):
        from assets.clip_tags import without_ui

        clips = list(self._index()["clips"])
        kept = without_ui(clips, "EA Sports FC 26 ratings update", index=self._index())
        self.assertEqual(len(kept), 4)

    def test_a_still_clip_is_a_menu(self):
        from assets.clip_tags import MOTION_UI, is_ui_clip

        self.assertTrue(is_ui_clip("x.mp4", {"motion": MOTION_UI - 1.5}))
        self.assertFalse(is_ui_clip("x.mp4", {"motion": 7.9}))
        self.assertFalse(is_ui_clip("x.mp4", {}))
        self.assertTrue(is_ui_clip("Madden lineup screen.mp4", {}))

    def test_the_picker_and_the_measurement_read_it(self):
        import inspect

        from assets import clip_ingest, local_provider
        from core import overnight

        self.assertIn(
            "without_ui(", inspect.getsource(local_provider.LocalAssetProvider.candidate_clips)
        )
        self.assertIn("measure_motion(", inspect.getsource(clip_ingest.measure_library))
        self.assertIn("measure_library()", inspect.getsource(overnight))


class PlatformFootageTests(unittest.TestCase):
    """L6: Valve's Steam AI story cut a cartoon shooter; Xbox Game Pass cut Minecraft."""

    def test_platform_news_reaches_the_platform_folder(self):
        from assets.local_provider import choose_footage

        folders = ["lib/gaming/platforms/Steam", "lib/gaming/platforms/Xbox",
                   "lib/gaming/other/Minecraft", "lib/gaming/platforms/PlayStation"]  # fmt: skip
        # the folder names already match "Steam" and "Xbox"; these name only the company or service
        pick = choose_footage("Valve cracks down on AI-made games", folders, "tapin", use_llm=False)
        self.assertEqual(pick[0], folders[0])
        pick = choose_footage("Game Pass adds Final Fantasy 7 Remake", folders, "tapin",
                              use_llm=False)  # fmt: skip
        self.assertEqual(pick[0], folders[1])
        pick = choose_footage("PS5 Pro price rises again", folders, "tapin", use_llm=False)
        self.assertEqual(pick[0], folders[3])
        # a game the story names still wins
        pick = choose_footage("Minecraft comes to Game Pass", folders, "tapin", use_llm=False)
        self.assertEqual(pick[0], folders[2])

    def test_ops_footage_lists_the_missing_ones(self):
        import inspect

        from scripts import ops

        self.assertIn("Platform footage to record (L6)", inspect.getsource(ops))


class CostPerThousandTests(unittest.TestCase):
    """#1797 (B09.1): what a video cost against what it was watched."""

    def test_the_briefs_fixture(self):
        from core.success.scorecard import cost_per_thousand, week_cost_line

        self.assertEqual(cost_per_thousand(0.39, 325), "$1.20")
        self.assertEqual(cost_per_thousand(0.27, 0), "no views")
        self.assertEqual(cost_per_thousand(0.08, 23), "$3.48")
        line = week_cost_line([{"cost": 0.39, "views": 325}, {"cost": 0.27, "views": 0},
                               {"cost": 0.08, "views": 23}])  # fmt: skip
        self.assertIn("$2.13", line)
        self.assertIn("$0.74 over 348 views", line)
        self.assertIn("not measured", week_cost_line([]))


class HoursLedgerTests(unittest.TestCase):
    """#1728 (B06.7): long-form hours a week, and how far the bar is at that pace."""

    def test_the_briefs_fixture(self):
        from core.success.scorecard import hours_lines, hours_week

        self.assertEqual(hours_week([240, 90, 30]), 6.0)
        line = hours_lines([240, 90, 30], have=10.2, bars=(4000, 8000))[0]
        self.assertIn("6.0", line)
        self.assertIn("about 1,332 weeks", line)
        self.assertIn("not measured", hours_lines([], have=10.2, bars=(4000, 8000))[0])
        idle = hours_lines([0.0], have=10.2, bars=(4000, 8000))[
            0
        ]  # live 10-30: "is no pace yet away"
        self.assertIn("no pace yet", idle)
        self.assertNotIn("is no pace yet away", idle)

    def test_the_scoreboard_carries_both(self):
        from core.success.bridge import scoreboard_lines

        text = "\n".join(scoreboard_lines("tapin", numbers={"long_hours_365d": 10.2}, entries=[],
                                          today=datetime(2026, 10, 30).date()))  # fmt: skip
        self.assertIn("cost per 1,000 organic views", text)
        self.assertIn("long-form hours this week", text)

    def test_a_long_render_is_marked_for_the_ledger(self):
        import inspect

        from core.series import long_form

        self.assertIn('"long_form": True', inspect.getsource(long_form.finish_long_render))


class ExperimentStopTests(unittest.TestCase):
    """#1827 (B10.6): an experiment runs 14 days unless it says otherwise, and the week says so."""

    def setUp(self):
        import tempfile

        from config import paths

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(paths, "EXPERIMENTS_FILE", os.path.join(tmp.name, "exp.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_stops_today(self):
        from core import experiments

        with patch.object(experiments, "_measured_n", return_value=0):
            record = experiments.start_experiment("tapin", "hook_rewrite", days=14,
                                                  today=datetime(2026, 10, 26).date())  # fmt: skip
        self.assertEqual(record["stop"], "2026-11-09")
        lines = experiments.experiment_lines("tapin", today=datetime(2026, 11, 9).date())
        self.assertIn("hook_rewrite (on, off): stops today", "\n".join(lines))
        later = experiments.experiment_lines("tapin", today=datetime(2026, 11, 10).date())
        self.assertIn("past its stop date", "\n".join(later))

    def test_an_older_experiment_stops_14_days_from_its_start(self):
        # live 10-30: hook_rewrite and preview_shape, started before #1827, read "no stop date"
        import json

        from config import paths
        from core import experiments

        began = datetime(2026, 10, 23, 12).timestamp()
        with open(paths.EXPERIMENTS_FILE, "w", encoding="utf-8") as handle:
            json.dump({"active": {"tapin": {"hook": {"lever": "hook_rewrite", "started_at": began}}},
                       "assignments": []}, handle)  # fmt: skip
        lines = experiments.experiment_lines("tapin", today=datetime(2026, 10, 31).date())
        self.assertIn("6 day(s) left (stops 2026-11-06)", "\n".join(lines))

    def test_the_week_lists_them(self):
        import inspect

        from analytics import weekly_report

        source = inspect.getsource(weekly_report._bridge_block)
        self.assertIn("experiment_lines(", source)
        self.assertIn("scorecard_lines(", source)


class WaveScorecardTests(unittest.TestCase):
    """#1836 (B10.15): each wave judged 14 days after on its own number."""

    def test_the_briefs_fixture(self):
        from datetime import date

        from core.success.scorecard import scorecard_line

        shipped = date(2026, 11, 8)
        series = {shipped - timedelta(days=i): 251 for i in range(1, 15)}
        series.update({shipped + timedelta(days=i): 412 for i in range(0, 14)})
        row = {
            "wave": "133",
            "shipped": "2026-11-08",
            "lane": "views",
            "metric": "organic views a day",
        }
        self.assertEqual(scorecard_line(row, series, today=date(2026, 11, 22)),
                         "wave 133 (views): 412 a day after against 251 before - up 64%")  # fmt: skip
        self.assertEqual(scorecard_line(row, series, today=date(2026, 11, 21)), "")

    def test_the_shipped_waves_have_rows(self):
        from core.success.scorecard import wave_rows

        self.assertIn("134", [r["wave"] for r in wave_rows()])


class BreakoutToastTests(unittest.TestCase):
    """#1832 (B10.11): a Short past 1,000 organic views in its first day, said once."""

    def test_the_briefs_table(self):
        from core.success.scorecard import breakouts

        now = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)

        def row(views, hours):
            return {"video_id": f"v{views}", "organic": views,
                    "published_at": now - timedelta(hours=hours)}  # fmt: skip

        hits = breakouts([row(1200, 20), row(900, 20), row(1500, 30)], now=now)
        self.assertEqual([h["video_id"] for h in hits], ["v1200"])

    def test_once_a_day_through_toast_daily(self):
        from core.success import scorecard

        now = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)
        published = SimpleNamespace(youtube_video_id="abc", title="Cyclops joins",
                                    published_at=now - timedelta(hours=5),
                                    metrics_json='{"lifetime_views": 1400, "paid_views": 0}')  # fmt: skip
        seen: list[str] = []
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository") as repo,
            patch(
                "core.win_notify.toast_daily",
                side_effect=lambda key, *a, **k: key not in seen and not seen.append(key),
            ),
        ):
            repo.return_value.list_uploaded_for_channel.return_value = [published]
            self.assertEqual(scorecard.toast_breakouts("tapin", now=now), ["Cyclops joins"])
            self.assertEqual(scorecard.toast_breakouts("tapin", now=now), [])

    def test_the_sync_asks(self):
        import inspect

        from analytics import sync_metrics

        self.assertIn("toast_breakouts(", inspect.getsource(sync_metrics))


def _picture(path, *, seed=0, dark=False, flat=False):
    """A 1080x1920 frame: busy edges in the middle unless flat, bright unless dark."""
    import random

    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    image = Image.new("RGB", (1080, 1920), (20, 20, 20) if dark else (150, 150, 150))
    if not flat:
        draw = ImageDraw.Draw(image)
        for _ in range(120):
            x, y = rng.randint(270, 800), rng.randint(480, 1440)
            shade = rng.randint(0, 255)
            draw.rectangle([x, y, x + rng.randint(20, 120), y + rng.randint(20, 120)],
                           fill=(shade, 255 - shade, shade // 2))  # fmt: skip
    image.save(path)
    return path


class FrameCoverTests(_OwnStores):
    """L1 + L2 (decision 85): covers were AI images from one prompt per genre - every GTA cover
    looked alike. A cover is a frame of the video's own shots, and never one already used."""

    def _choose(self, specs):
        import tempfile

        from assets import cover_frames

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        made = {}

        def fake_frame(video, _at, dest):
            spec = made[video]
            return _picture(dest, **spec)

        shots = []
        for i, spec in enumerate(specs):
            shot = os.path.join(tmp.name, f"shot{i}.mp4")
            made[shot] = spec
            shots.append(shot)
        with patch.object(cover_frames, "frame_at", side_effect=fake_frame):
            return cover_frames.choose_cover(
                shots, [4.0] * len(specs), os.path.join(tmp.name, "v")
            ), tmp

    def test_the_best_frame_not_a_dark_or_flat_one(self):
        cover, _tmp = self._choose([{"dark": True}, {"flat": True}, {"seed": 3}])
        self.assertEqual(cover.index, 2)

    def test_no_two_videos_share_a_cover(self):
        from assets.cover_frames import record_cover

        first, _tmp = self._choose([{"seed": 5}])
        record_cover(first.hash, first.path)
        again, _tmp2 = self._choose([{"seed": 5}, {"seed": 9}])
        self.assertEqual(again.index, 1)  # the same picture is refused, the next taken

    def test_the_hash_says_near(self):
        from PIL import Image

        from assets.cover_frames import dhash, near

        a = Image.new("L", (90, 80), 100)
        b = a.copy()
        b.putpixel((1, 1), 101)
        self.assertTrue(near(dhash(a), dhash(b)))


class OpeningShotTests(_OwnStores):
    """L8: the Short opens on the shot its cover came from."""

    def test_the_cover_shot_moves_first_and_keeps_the_lengths(self):
        from assets import cover_frames, fast_cut

        done = [(0, ("a.mp4", 1.0, 3.0), "s0.mp4"), (1, ("b.mp4", 5.0, 6.0), "s1.mp4")]
        rendered = []
        cover = cover_frames.Cover(index=1, path="c.jpg", hash=1, score=0.5)
        with (
            patch.object(cover_frames, "choose_cover", return_value=cover),
            patch.object(cover_frames, "frame_at", return_value="c.jpg"),
            patch.object(cover_frames, "finish", return_value="v_frame_cover.jpg"),
            patch.object(fast_cut, "_render_shot", side_effect=lambda *a: rendered.append(a)),
        ):
            path = fast_cut._cover_and_open(done, "v.mp4")
        self.assertEqual(path, "v_frame_cover.jpg")
        self.assertEqual(done[0][1], ("b.mp4", 5.0, 3.0))  # b's moment, the first shot's length
        self.assertEqual(done[1][1], ("a.mp4", 1.0, 6.0))
        self.assertEqual(len(rendered), 2)

    def test_the_cut_carries_its_cover(self):
        import inspect

        from assets import fast_cut
        from core import pipeline

        self.assertIn("_cover_and_open(", inspect.getsource(fast_cut._compose))
        self.assertIn(
            'getattr(background, "cover_path"', inspect.getsource(pipeline.run_media_only)
        )


class RetiredArmsTests(unittest.TestCase):
    """L7: no image model is asked for a cover unless THUMBNAIL_AI is on."""

    def test_a_key_alone_does_not_make_ai_covers(self):
        from assets import flux_thumbnail as ft

        with patch.dict(os.environ, {"FLUX_API_KEY": "x", "THUMBNAIL_AI": ""}):
            self.assertFalse(ft.is_flux_configured())
            self.assertEqual(ft._provider_chain("ideogram"), ["pillow"])
        with patch.dict(os.environ, {"FLUX_API_KEY": "x", "THUMBNAIL_AI": "true"}):
            self.assertTrue(ft.is_flux_configured())

    def test_frames_mode_uploads_only_a_frame(self):
        from youtube import thumbnails

        with (
            patch.dict(os.environ, {"YOUTUBE_THUMBNAIL_UPLOAD": "frames"}),
            patch.object(thumbnails, "resolve_thumbnail_path", return_value="out/ai_thumb.png"),
            patch.object(thumbnails, "set_video_thumbnail") as sent,
        ):
            got = thumbnails.maybe_upload_thumbnail(object(), video_id="v", channel_id="tapin",
                                                    thumbnail_path="out/ai_thumb.png")  # fmt: skip
        self.assertEqual(got.status, "skipped")
        sent.assert_not_called()


class CoverStripTests(_OwnStores):
    """L10: the new cover beside the last ten, a repeat flagged before it goes out."""

    def test_a_repeat_is_flagged(self):
        import tempfile

        from PIL import Image

        from assets.cover_frames import dhash, record_cover, strip_lines

        with tempfile.TemporaryDirectory() as tmp:
            old = _picture(os.path.join(tmp, "old.jpg"), seed=7)
            new = _picture(os.path.join(tmp, "new.jpg"), seed=7)
            with Image.open(old) as image:
                record_cover(dhash(image), old)
            text = "\n".join(strip_lines(new))
        self.assertIn("the same picture", text)


class LongCoverTestTests(_OwnStores):
    """L9: a long video's cover - three words against none - as an experiment."""

    def setUp(self):
        super().setUp()
        import tempfile

        from config import paths

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(paths, "EXPERIMENTS_FILE", os.path.join(tmp.name, "exp.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_first_long_video_starts_it_and_takes_an_arm(self):
        from core import experiments
        from core.series.long_form import cover_arm

        with patch.object(experiments, "_measured_n", return_value=0):
            arm = cover_arm("tapin", 301)
        self.assertIn(arm, ("words", "none"))
        self.assertEqual(
            experiments.active_experiment("tapin", "long_cover")["lever"], "long_cover"
        )

    def test_none_is_the_frame_alone(self):
        import tempfile

        from PIL import Image

        from core.series import long_form

        def fake_frame(_video, _at, dest):
            Image.new("RGB", (1920, 1080), (90, 60, 120)).save(dest)
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "card.png")
            with (
                patch.object(long_form, "_frame", side_effect=fake_frame),
                patch.object(long_form, "_duration", return_value=600.0),
                patch("assets.thumbnail_compose.compose_thumbnail") as compose,
            ):
                path = long_form.long_thumbnail(os.path.join(tmp, "v.mp4"), "", dest,
                                                channel_id="tapin")  # fmt: skip
            self.assertEqual(path, dest)
            compose.assert_not_called()
            with Image.open(dest) as card:
                self.assertEqual(card.size, (1280, 720))


if __name__ == "__main__":
    unittest.main()
