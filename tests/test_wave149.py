"""Wave 149 (2026-11-04) - the next five, S01 (long-form hours) the shortfall it takes.

#1990 the Weeks in Review get impressions and no clicks: the cover is the week's top Short with
its subject on it, and a live one under 2% after 100 impressions gets it; #1992 (found on the way)
a long video's frame-built cover passes the frames-only upload gate; #1727 one weekly long slot,
Sunday 7 PM, the compile on its morning; #1724 a franchise's long explainer each new season;
#1981 an NVENC fallback says why; #1979 the four modules nothing imported, retired.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

# Imported before any patch below: a module first imported under a patch of a name it imports
# binds the mock for the rest of the process (wave 145's reversed-suite failure).
import analytics.packaging
import core.batch_generation
import core.overnight
import core.roadmap_index
import core.series.dated
import core.series.long_form
import core.spaced_queue
import video.encoder
import video.render_video
import video.week_compile
import youtube.thumbnails

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]


def _short(run_id, title, names, views, path="", **extra):
    return {"run_id": run_id, "title": title, "names": names, "views": views, "path": path,
            "offset": 1.5, "published_at": datetime(2026, 10, 27, 16, tzinfo=UTC), **extra}  # fmt: skip


def _fake_ffmpeg(argv, **_kwargs):
    """Write the frame ffmpeg was asked for, as a real image."""
    from PIL import Image

    Image.new("RGB", (1280, 720), (40, 90, 40)).save(argv[-1], "PNG")
    return SimpleNamespace(returncode=0)


def _fake_compose(_image, words, dest, **_kwargs):
    Path(dest).write_bytes(b"jpeg")
    return SimpleNamespace(path=dest, words=words.split())


# ---- #1990: the cover names the week's top Short ---------------------------------------------------


class CompilationCoverTests(unittest.TestCase):
    def _plan(self, items, kind="week", week="2026-11-08"):
        return video.week_compile.WeekPlan(channel_id="tapin", week=week, title="T",
                                           description="", items=items, kind=kind)  # fmt: skip

    def test_the_cover_says_the_top_shorts_subject(self):
        items = [_short(1, "Hurts leads late comeback", ["Jalen Hurts"], 90, deep=2),
                 _short(2, "GTA 6 trailer 3 breaks every record", ["GTA 6"], 300, deep=1)]  # fmt: skip
        plan = self._plan(items)
        top = video.week_compile.cover_item(plan)
        self.assertEqual(top["run_id"], 2)
        self.assertEqual(video.week_compile.cover_words(plan, top), "GTA 6 This Week")
        self.assertEqual(video.week_compile.cover_item(plan, 2)["run_id"], 1)

    def test_a_month_keeps_best_of(self):
        plan = self._plan([_short(1, "GTA 6 news", ["GTA 6"], 9)], kind="month", week="2026-10")
        self.assertEqual(video.week_compile.cover_words(plan, plan.items[0]), "Best of October")

    def test_the_frame_is_a_band_clear_of_the_captions(self):
        argv = video.week_compile.cover_frame_argv("short.mp4", "f.png", at=12.34)
        self.assertEqual(argv[argv.index("-i") + 1], "short.mp4")
        band = argv[argv.index("-vf") + 1]
        self.assertIn("crop=iw:'min(ih,iw*9/16)'", band)
        self.assertIn("ih*0.36", band)
        self.assertIn("scale=1280:720", band)

    def test_the_thumbnail_is_cut_from_the_short_not_the_blurred_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            short = os.path.join(tmp, "short.mp4")
            Path(short).write_bytes(b"x")
            video_path = os.path.join(tmp, "week_2026-11-08.mp4")
            items = [_short(2, "GTA 6 trailer 3 breaks every record", ["GTA 6"], 300,
                            path=short, deep=1, seconds=40.0, start=100.0)]  # fmt: skip
            with (
                patch("video.week_compile.subprocess.run", side_effect=_fake_ffmpeg) as run,
                patch(
                    "assets.thumbnail_compose.compose_thumbnail", side_effect=_fake_compose
                ) as compose,  # fmt: skip
            ):
                thumb = video.week_compile.make_thumbnail(self._plan(items), video_path)
            argv = run.call_args_list[0].args[0]
            self.assertEqual(argv[argv.index("-i") + 1], short)
            self.assertAlmostEqual(float(argv[argv.index("-ss") + 1]), 1.5 + 16.0, places=1)
            self.assertEqual(compose.call_args.args[1], "GTA 6 This Week")
            self.assertTrue(thumb.endswith("_frame_long.jpg"), thumb)

    def test_a_band_an_earlier_cover_used_is_passed_over(self):
        from PIL import Image

        def ramp(up):  # a picture whose difference hash is all 0s (rising) or all 1s (falling)
            row = bytes(range(256)) if up else bytes(range(255, -1, -1))
            return Image.frombytes("L", (256, 1), row).resize((1280, 720)).convert("RGB")

        def ffmpeg(argv, **_kwargs):
            at = float(argv[argv.index("-ss") + 1])
            ramp(abs(at - 17.5) < 0.05).save(argv[-1], "PNG")  # 40% in: the taken picture
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as tmp:
            short = os.path.join(tmp, "short.mp4")
            Path(short).write_bytes(b"x")
            items = [_short(2, "GTA 6 trailer 3", ["GTA 6"], 300, path=short, deep=1,
                            seconds=40.0)]  # fmt: skip
            with (
                patch("video.week_compile.subprocess.run", side_effect=ffmpeg) as run,
                patch("assets.cover_frames.used_covers", return_value=[{"hash": "0" * 16}]),
                patch("assets.cover_frames.record_cover") as record,
                patch("assets.thumbnail_compose.compose_thumbnail", side_effect=_fake_compose),
            ):
                thumb = video.week_compile.make_thumbnail(
                    self._plan(items), os.path.join(tmp, "w.mp4")
                )
        stamps = [float(c.args[0][c.args[0].index("-ss") + 1]) for c in run.call_args_list]
        self.assertEqual(stamps, [17.5, 11.5])  # 40% was taken; 25% in was not
        record.assert_called_once_with((1 << 64) - 1, thumb)

    def test_a_recorded_compilation_says_its_cover_names_a_subject(self):
        plan = self._plan([_short(2, "GTA 6", ["GTA 6"], 3)])
        with patch("core.run_recorder.record_content_run", return_value=9) as record:
            video.week_compile._record(plan, "x.mp4", thumbnail="t_frame_long.jpg")
        self.assertEqual(record.call_args.kwargs["features"]["compilation"]["cover"], "subject")


def _reach_row(run_id, impressions, ctr):
    metrics = {"thumbnail_impressions": impressions, "thumbnail_ctr": ctr}
    return SimpleNamespace(content_run_id=run_id, youtube_video_id=f"v{run_id}",
                           privacy_status="public", metrics_json=json.dumps(metrics))  # fmt: skip


class CompilationCoverSwapTests(unittest.TestCase):
    def test_a_week_in_review_swaps_at_100_impressions(self):
        rows = [_reach_row(202, 139, 0.0), _reach_row(300, 139, 0.0), _reach_row(172, 279, 0.0108)]
        repo = SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)
        runs = {rid: SimpleNamespace(id=rid, title=f"Run {rid}", mp4_path="m.mp4")
                for rid in (202, 300, 172)}  # fmt: skip
        features = {202: {"compilation": {"week": "2026-10-26"}}, 300: {"long_form": True},
                    172: {"compilation": {"week": "2026-10-19"}}}  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch("publishing.prepublish._is_long", return_value=True),
            patch("publishing.prepublish._run", side_effect=lambda rid: runs.get(rid)),
            patch(
                "publishing.prepublish._features",
                side_effect=lambda run: features.get(getattr(run, "id", 0), {}),
            ),  # fmt: skip
        ):
            found = analytics.packaging.cover_swap_candidates("tapin")
        self.assertEqual(sorted(c["run_id"] for c in found), [172, 202])
        self.assertTrue(all(c["compilation"] for c in found))

    def test_a_compilations_second_cover_is_its_subject_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "week.mp4")
            Path(mp4).write_bytes(b"x")
            found = {"run_id": 202, "mp4": mp4, "title": "T", "compilation": True}
            with (
                patch("core.output_paths.channel_output_root", return_value=tmp),
                patch("video.week_compile.compilation_cover", return_value="c.jpg") as cover,
                patch("core.series.long_form.long_thumbnail", return_value="long.jpg"),
            ):
                self.assertEqual(analytics.packaging._second_cover(found, "tapin"), "c.jpg")
        self.assertEqual(cover.call_args.args[:2], ("tapin", 202))
        self.assertTrue(cover.call_args.args[2].endswith("run202-cover2_frame_long.jpg"))

    def test_the_stored_compilation_shows_its_top_short_then_its_second(self):
        def stored(cover):
            data = {"compilation": {"week": "2026-10-26", "runs": [5, 6], **cover}}
            return SimpleNamespace(features_json=json.dumps(data), title="T", mp4_path="m.mp4")

        shorts = [_short(5, "A", [], 10, path="a.mp4"), _short(6, "B", [], 50, path="b.mp4"),
                  _short(7, "Not in it", [], 900, path="c.mp4")]  # fmt: skip
        ranks = []
        for cover, rank in (({}, 1), ({"cover": "subject"}, 2)):
            with (
                patch("video.week_compile._run", return_value=stored(cover)),
                patch("video.week_compile._public_shorts", return_value=[dict(s) for s in shorts]),
                patch("video.week_compile._duration", return_value=41.5),
                patch("video.week_compile.make_thumbnail", return_value="t.jpg") as make,
            ):
                video.week_compile.compilation_cover("tapin", 202, "d.jpg")
            plan = make.call_args.args[0]
            self.assertEqual(sorted(i["run_id"] for i in plan.items), [5, 6])
            self.assertEqual(plan.items[0]["seconds"], 40.0)
            ranks.append(make.call_args.kwargs["rank"])
            self.assertEqual(rank, ranks[-1])


# ---- #1992: a long video's frame-built cover is uploaded in frames-only mode ------------------------


class LongCoverGateTests(unittest.TestCase):
    def test_a_long_frame_cover_passes_and_a_word_png_does_not(self):
        self.assertTrue(youtube.thumbnails.is_frame_cover("run9_16x9_frame_long.jpg"))
        self.assertTrue(youtube.thumbnails.is_frame_cover("run9-fastcut_frame_cover.jpg"))
        self.assertFalse(youtube.thumbnails.is_frame_cover("week_2026-11-02_thumb.png"))

    def test_frames_mode_uploads_a_long_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            cover = os.path.join(tmp, "week_2026-11-08_frame_long.jpg")
            Path(cover).write_bytes(b"x")
            ok = youtube.thumbnails.ThumbnailUploadResult("set", "ok")
            with (
                patch.dict(os.environ, {"YOUTUBE_THUMBNAIL_UPLOAD": "frames"}),
                patch("youtube.thumbnails.set_video_thumbnail", return_value=ok) as upload,
            ):
                result = youtube.thumbnails.maybe_upload_thumbnail(
                    object(), video_id="v1", thumbnail_path=cover
                )
        self.assertEqual(result.status, "set")
        upload.assert_called_once()

    def test_the_long_render_names_its_cover_for_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = os.path.join(tmp, "gta6.mp4")
            Path(primary).write_bytes(b"x")
            Path(os.path.join(tmp, "gta6_16x9.mp4")).write_bytes(b"x")
            repo = SimpleNamespace(get=lambda _rid: SimpleNamespace(mp4_path=primary, mp3_path=""))
            with (
                patch(
                    "storage.repositories.content_runs.get_content_run_repository",
                    return_value=repo,
                ),  # fmt: skip
                patch("core.run_recorder.update_content_run_media"),
                patch("core.series.long_form.cover_arm", return_value="words"),
                patch("core.series.long_form.style_palette", return_value=[]),
                patch("core.series.long_form.long_thumbnail", return_value="") as thumb,
                patch("core.run_features.merge_features"),
            ):
                core.series.long_form.finish_long_render(9, "tapin", "GTA 6 explained")
        self.assertTrue(thumb.call_args.args[2].endswith("gta6_16x9_frame_long.jpg"))


# ---- #1727: one weekly long slot ------------------------------------------------------------------


class LongSlotTests(unittest.TestCase):
    def test_sunday_7_pm_by_default(self):
        with patch.dict(os.environ, {"LONG_SLOT": ""}):
            self.assertEqual(core.spaced_queue.long_slot(), (6, 19))
            self.assertEqual(core.spaced_queue.long_slot_words(), "every Sunday")
        with patch.dict(os.environ, {"LONG_SLOT": "off"}):
            self.assertIsNone(core.spaced_queue.long_slot())
            self.assertEqual(core.spaced_queue.long_slot_words(), "every week")
        with patch.dict(os.environ, {"LONG_SLOT": "9@99"}):
            self.assertEqual(core.spaced_queue.long_slot(), (6, 19))
        with patch.dict(os.environ, {"LONG_SLOT": "0@12"}):
            self.assertEqual(core.spaced_queue.long_slot(), (0, 12))

    def _next(self, now, taken=()):
        with (
            patch.dict(os.environ, {"LONG_SLOT": ""}),
            patch("core.spaced_queue._channel_tz", return_value=NY),
            patch("core.spaced_queue._taken_slots", return_value=set(taken)),
        ):
            return core.spaced_queue.next_long_slot("tapin", now=now)

    def test_the_next_free_sunday_evening(self):
        sunday = datetime(2026, 11, 9, 0, tzinfo=UTC)  # Nov 8, 7 PM EST
        self.assertEqual(self._next(datetime(2026, 11, 4, 15, tzinfo=UTC)), sunday)
        self.assertEqual(self._next(datetime(2026, 11, 4, 15, tzinfo=UTC), taken=[sunday]),
                         sunday + timedelta(days=7))  # fmt: skip
        # Sunday at 6 PM: an upload needs 90 minutes, so the next Sunday
        self.assertEqual(self._next(datetime(2026, 11, 8, 23, tzinfo=UTC)),
                         sunday + timedelta(days=7))  # fmt: skip

    def test_a_week_in_review_takes_it_whatever_its_title_names(self):
        run = SimpleNamespace(features_json=json.dumps({"compilation": {"week": "2026-11-08"}}))
        repo = SimpleNamespace(get=lambda _rid: run)
        game = datetime(2026, 11, 9, 18, tzinfo=UTC)  # "49ers" in run 202's title
        with (
            patch.dict(os.environ, {"LONG_SLOT": ""}),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),  # fmt: skip
            patch("core.spaced_queue._channel_tz", return_value=NY),
            patch("core.spaced_queue._taken_slots", return_value=set()),
            patch("core.spaced_queue.preview_event", return_value=game),
            patch("core.spaced_queue._window_days", return_value=2.0),
            patch("core.spaced_queue._age_days", return_value=0.0),
            patch("core.spaced_queue._planned_time", return_value=None),
        ):
            when, why = core.spaced_queue.slot_for_run(
                "tapin", 240, title="GTA 6, Jalen Hurts & 49ers - Week in Review",
                now=datetime(2026, 11, 8, 10, tzinfo=UTC),
            )  # fmt: skip
        self.assertEqual((when, why), (datetime(2026, 11, 9, 0, tzinfo=UTC), ""))

    def test_a_season_explainer_takes_it_and_a_month_does_not(self):
        def taken(features, meta):
            run = SimpleNamespace(features_json=json.dumps(features))
            with (
                patch(
                    "storage.repositories.content_runs.get_content_run_repository",
                    return_value=SimpleNamespace(get=lambda _rid: run),
                ),  # fmt: skip
                patch("core.batch_review.draft_meta_for_run", return_value=meta),
            ):
                return core.spaced_queue.takes_long_slot("tapin", 1)

        self.assertTrue(taken({}, {"series": "season", "kind": "long"}))
        self.assertFalse(taken({"compilation": {"month": "2026-10"}}, {}))
        self.assertFalse(taken({"long_form": True}, {"kind": "long"}))

    def test_the_week_is_keyed_by_its_slot_day(self):
        sunday = datetime(2026, 11, 8, 10, tzinfo=UTC)
        monday = datetime(2026, 11, 2, 15, tzinfo=UTC)
        with patch.dict(os.environ, {"LONG_SLOT": ""}):
            self.assertEqual(video.week_compile.week_key("tapin", sunday), "2026-11-08")
            self.assertEqual(video.week_compile.week_key("tapin", monday), "2026-11-08")
        with patch.dict(os.environ, {"LONG_SLOT": "off"}):
            self.assertEqual(video.week_compile.week_key("tapin", monday), "2026-11-02")

    def test_overnight_compiles_on_the_slots_morning(self):
        result = SimpleNamespace(channel_id="tapin", week_line="")
        sunday = datetime(2026, 11, 8, 10, tzinfo=UTC)
        with (
            patch.dict(os.environ, {"WEEK_COMPILE": "true", "LONG_SLOT": ""}),
            patch("core.spaced_queue._channel_tz", return_value=NY),
            patch("video.week_compile.compile_week", return_value=["  queued"]) as compile_,
        ):
            core.overnight._week_compile(result, now=sunday)
            core.overnight._week_compile(result, now=sunday + timedelta(days=1))
        self.assertEqual(compile_.call_count, 1)
        self.assertEqual(compile_.call_args.kwargs["now"], sunday)

    def test_a_short_is_in_one_weeks_video(self):
        made = SimpleNamespace(features_json=json.dumps(
            {"compilation": {"week": "2026-11-02", "runs": [5]}}))  # fmt: skip
        repo = SimpleNamespace(list_for_channel=lambda _c: [made])
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),  # fmt: skip
            patch(
                "video.week_compile._public_shorts",
                return_value=[_short(5, "A", [], 1), _short(6, "B", [], 1)],
            ),  # fmt: skip
        ):
            shorts = video.week_compile.week_shorts("tapin", now=datetime(2026, 11, 8, tzinfo=UTC))
        self.assertEqual([s["run_id"] for s in shorts], [6])

    def test_a_made_week_says_so_before_it_plans(self):
        with (
            patch.dict(os.environ, {"LONG_SLOT": ""}),
            patch("video.week_compile.week_done", return_value=True),
            patch("video.week_compile.plan_week", return_value=None) as plan,
            patch("video.week_compile.week_shorts", return_value=[]),
        ):
            lines = video.week_compile.compile_week(
                "tapin", now=datetime(2026, 11, 8, 12, tzinfo=UTC)
            )
        self.assertIn("2026-11-08 is already made", lines[0])
        plan.assert_not_called()

    def test_the_scripts_promise_the_slots_day(self):
        with patch.dict(os.environ, {"LONG_SLOT": ""}):
            long_line = core.batch_generation.follow_brief({"draft_kind": "long"})
            trending = core.batch_generation.follow_brief(
                {"offered": [{"topic": "Pacers trade", "source": "trending"}], "picked": 1}
            )
        self.assertIn("every Sunday", long_line)
        self.assertNotIn("Monday", long_line)
        self.assertIn("every Sunday", trending)
        self.assertNotIn("Monday", trending)

    def test_launch_week_special_is_on_the_slots_sunday(self):
        from core.series.countdown import series_rows

        days = {r["id"]: r.get("on") for r in series_rows("tapin")}
        self.assertEqual(days.get("gta6-week-one"), "2026-11-22")
        self.assertEqual(datetime(2026, 11, 22).weekday(), 6)


# ---- #1724: a franchise's long explainer each new season -------------------------------------------

NOW = datetime(2026, 11, 20, 15, tzinfo=UTC)
ROW = {"id": "marvel-rivals-seasons", "kind": "season", "subject": "Marvel Rivals",
       "names": ["Marvel Rivals"], "domain": "gaming",
       "topic": "Everything in Marvel Rivals {season}"}  # fmt: skip


def _line(title, source, hours=5):
    return {"title": title, "source": source, "published": NOW - timedelta(hours=hours)}


class SeasonExplainerTests(unittest.TestCase):
    def test_the_season_a_headline_names(self):
        from core.series.seasons import season_label

        self.assertEqual(season_label("Marvel Rivals Season 5 adds two heroes")[1], "Season 5")
        self.assertEqual(season_label("Fortnite Chapter 7 Season 1 battle pass")[1],
                         "Chapter 7 Season 1")  # fmt: skip
        self.assertEqual(season_label("Marvel Rivals Season 4.5 patch notes")[1], "Season 4.5")
        self.assertIsNone(season_label("Marvel Rivals' best plays of the 2026 season"))
        self.assertIsNone(season_label("Season 2026 recap"))

    def test_two_outlets_name_it_and_the_newest_wins(self):
        from core.series.seasons import latest_season

        one = [_line("Marvel Rivals Season 5 starts Friday", "IGN")]
        self.assertEqual(latest_season(["Marvel Rivals"], one, now=NOW), "")
        two = [*one, _line("Marvel Rivals Season 5: every new hero", "Dexerto"),
               _line("Marvel Rivals Season 4 ends with a bang", "IGN"),
               _line("Marvel Rivals Season 4 recap", "PC Gamer")]  # fmt: skip
        self.assertEqual(latest_season(["Marvel Rivals"], two, now=NOW), "Season 5")
        old = [_line("Marvel Rivals Season 6 leak", s, hours=100) for s in ("IGN", "Dexerto")]
        self.assertEqual(latest_season(["Marvel Rivals"], [*two, *old], now=NOW), "Season 5")

    def test_the_night_drafts_it_long(self):
        lines = [_line("Marvel Rivals Season 5 starts Friday", "IGN"),
                 _line("Marvel Rivals Season 5: every new hero", "Dexerto")]  # fmt: skip
        with (
            patch.dict(os.environ, {"SERIES_DATED": "true"}),
            patch("core.series.dated.series_rows", return_value=[ROW]),
            patch("core.batch_generation.series_drafted", return_value=False),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda _c: []),
            ),  # fmt: skip
        ):
            ideas = core.series.dated.dated_ideas("tapin", now=NOW,
                                                  headlines=lambda *_a: lines)  # fmt: skip
        self.assertEqual([i.topic for i in ideas], ["Everything in Marvel Rivals Season 5"])
        self.assertEqual((ideas[0].source, ideas[0].draft_kind), ("season", "long"))
        self.assertEqual(len(ideas[0].facts), 2)
        self.assertIn("season", core.batch_generation.DATED_SOURCES)

    def test_a_season_is_drafted_once_however_long_ago(self):
        from core.series.seasons import season_drafted

        old = SimpleNamespace(input_topic="Everything in Marvel Rivals Season 5", selected_topic="")
        with (
            patch("core.batch_generation.series_drafted", return_value=False),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda _c: [old]),
            ),  # fmt: skip
        ):
            self.assertTrue(season_drafted("tapin", "Everything in  Marvel Rivals Season 5"))
            self.assertFalse(season_drafted("tapin", "Everything in Marvel Rivals Season 6"))

    def test_the_marquee_franchises_are_on_the_calendar(self):
        from core.series.countdown import series_rows

        subjects = {r["subject"] for r in series_rows("tapin") if r.get("kind") == "season"}
        self.assertEqual(subjects, {"Fortnite", "Marvel Rivals", "Black Ops 7", "Apex Legends",
                                    "Overwatch"})  # fmt: skip
        for row in series_rows("tapin"):
            if row.get("kind") == "season":
                self.assertIn("{season}", row["topic"])


# ---- #1981: an NVENC fallback says why ------------------------------------------------------------

STDERR = (
    "frame=  120 fps= 40 q=19.0 size=1024kB time=00:00:04.00\n"
    "[h264_nvenc @ 000001] OpenEncodeSessionEx failed: out of memory (10): (no details)\n"
    "[vost#0:0/h264_nvenc @ 000002] Error while opening encoder - maybe incorrect parameters\n"
    "frame=  121 fps= 40 q=19.0 size=1030kB time=00:00:04.03\n"
)


class NvencReasonTests(unittest.TestCase):
    def test_the_last_error_line(self):
        reason = video.encoder.nvenc_error(STDERR)
        self.assertTrue(reason.startswith("[vost#0:0/h264_nvenc"), reason)
        self.assertEqual(video.encoder.nvenc_error(""), "")

    def test_the_shared_fallback_logs_it(self):
        failed = SimpleNamespace(returncode=1, stderr=STDERR)
        done = SimpleNamespace(returncode=0, stderr="")
        runner = MagicMock(side_effect=[failed, done])
        with self.assertLogs("content_machine.video.encoder", level="WARNING") as logs:
            video.encoder.run_ffmpeg_with_nvenc_fallback(
                ["ffmpeg", "-i", "a", "-c:v", "h264_nvenc", "-preset", "p4", "o.mp4"], runner=runner
            )
        self.assertIn("Error while opening encoder", "\n".join(logs.output))
        self.assertIn("libx264", runner.call_args_list[1].args[0])

    def test_the_render_fallback_logs_it(self):
        def run(cmd, **_kwargs):
            if "h264_nvenc" in cmd:
                return SimpleNamespace(returncode=1, stderr=STDERR)
            return SimpleNamespace(returncode=0, stderr="")

        with (
            patch("video.render_video.subprocess.run", side_effect=run),
            self.assertLogs("content_machine.video.encoder", level="WARNING") as logs,
        ):
            done = video.render_video._ffmpeg_run(
                ["ffmpeg", "-i", "a", "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "o.mp4"]
            )
        self.assertEqual(done.returncode, 0)
        self.assertIn("Error while opening encoder", "\n".join(logs.output))


# ---- #1979: the four modules nothing imported -----------------------------------------------------


class RetiredModuleTests(unittest.TestCase):
    def test_they_are_gone(self):
        # The files, not find_spec: an editable install serves a module from the main checkout.
        for name in ("avatar", "reframe", "run_eval_corpus", "backlog_index"):
            self.assertFalse((ROOT / "core" / f"{name}.py").exists(), name)
        self.assertFalse((ROOT / "prompts" / "eval_corpus").exists())
        self.assertNotIn("ultralytics", (ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_the_roadmap_index_names_untagged_rows(self):
        data = core.roadmap_index.counts()
        data["untagged"] = 1
        with patch("core.roadmap_index.untagged_open_items", return_value=["backlog.md:12"]):
            text = core.roadmap_index.render(data)
        self.assertIn("1 open item(s) carry no size: backlog.md:12", text)


if __name__ == "__main__":
    unittest.main()
