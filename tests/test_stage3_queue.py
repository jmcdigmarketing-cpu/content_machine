"""Queue panel, studio snap, retraction toast, VACUUM, and 15 leftovers.

Fail-then-fix on unmodified bbfc2cb. Do not mock the unit under test.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.video_grade import GRADE_VERSION


class TestHudSkipMissingPath(unittest.TestCase):
    def test_missing_hud_null_is_not_picked(self):
        from core.owned_beats import assign_owned_clips
        from video.scene_plan import plan_scenes

        scenes = plan_scenes("Gameplay only please.", "GTA 6 leak", 6.0, max_scenes=1)
        index = {
            "clips": {
                "C:/clips/gta/hud.mp4": {"duration_s": 12.0, "hud": None, "source": "gta"},
            }
        }
        paths = assign_owned_clips(scenes, index, topic="GTA 6 leak")
        self.assertEqual(paths, [])


class TestSqliteVacuum(unittest.TestCase):
    def test_vacuum_shrinks_a_padded_temp_sqlite(self):
        from core.sqlite_vacuum import vacuum_sqlite

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pad.db")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE t (b BLOB)")
            conn.execute("INSERT INTO t VALUES (?)", (b"x" * 200_000,))
            conn.commit()
            conn.execute("DELETE FROM t")
            conn.commit()
            conn.close()
            before = os.path.getsize(path)
            result = vacuum_sqlite(path)
            after = os.path.getsize(path)
        self.assertLess(after, before)
        self.assertEqual(result["after"], after)
        self.assertNotIn("content_os.db", result["path"].replace("\\", "/"))

    def test_ops_reliability_vacuum_uses_the_given_path(self):
        from scripts.ops import COMMANDS

        self.assertIn("reliability", COMMANDS)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ops.db")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE t (b BLOB)")
            conn.execute("INSERT INTO t VALUES (?)", (b"y" * 80_000,))
            conn.commit()
            conn.execute("DELETE FROM t")
            conn.commit()
            conn.close()
            before = os.path.getsize(path)
            ns = type(
                "NS",
                (),
                {"html": False, "channel": "tapin", "vacuum": True, "path": path},
            )()
            code = COMMANDS["reliability"][1](ns)
            after = os.path.getsize(path)
        self.assertEqual(code, 0)
        self.assertLess(after, before)


class TestRetractionToast(unittest.TestCase):
    def test_hits_toast_once_per_24h_and_never_print_a_secret(self):
        from core.retraction_watch import maybe_toast_retractions

        calls: list[tuple] = []

        def toaster(title: str, body: str, **kwargs: object) -> None:
            calls.append((title, body, kwargs))

        with tempfile.TemporaryDirectory() as tmp:
            stamp = os.path.join(tmp, "retraction_toast.json")
            t0 = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
            self.assertTrue(
                maybe_toast_retractions(
                    ["https://example.test/story: RETRACTION in live body"],
                    stamp_path=stamp,
                    now=t0,
                    toaster=toaster,
                )
            )
            self.assertFalse(
                maybe_toast_retractions(
                    ["https://example.test/story: RETRACTION in live body"],
                    stamp_path=stamp,
                    now=t0 + timedelta(hours=6),
                    toaster=toaster,
                )
            )
            self.assertTrue(
                maybe_toast_retractions(
                    ["https://example.test/story: RETRACTION in live body"],
                    stamp_path=stamp,
                    now=t0 + timedelta(hours=25),
                    toaster=toaster,
                )
            )
        self.assertEqual(len(calls), 2)
        blob = json.dumps(calls)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("API_KEY", blob)

    def test_cli_retraction_watch_still_prints_without_toasting(self):
        from scripts.ops import COMMANDS

        toasted: list[str] = []
        with (
            patch("core.retraction_watch.watch_urls", return_value=["hit: retracted"]),
            patch("core.retraction_watch.pairs_from_trace", return_value=[("https://x.test", "c")]),
            patch("core.review_booth.last_trace", return_value={"selected_topic": "c"}),
            patch(
                "core.retraction_watch.maybe_toast_retractions",
                side_effect=lambda *a, **k: toasted.append("nope") or False,
            ),
        ):
            ns = type("NS", (), {"channel": "tapin"})()
            code = COMMANDS["retraction-watch"][1](ns)
        self.assertEqual(code, 0)
        self.assertEqual(toasted, [])


class TestStudioSnap(unittest.TestCase):
    def test_movable_layer_clamps_into_title_safe_not_chrome(self):
        from core.safe_title_grid import safe_title_rects
        from core.studio_canvas import clamp_layer_into_title_safe

        rects = safe_title_rects(1080, 1920)
        safe = rects["title_safe"]
        chrome = rects["chrome"]
        x, y = clamp_layer_into_title_safe(-40, 1900, 80, 40, safe)
        self.assertGreaterEqual(x, safe[0])
        self.assertGreaterEqual(y, safe[1])
        self.assertLessEqual(x + 80, safe[2])
        self.assertLessEqual(y + 40, safe[3])
        self.assertLessEqual(y + 40, chrome[1])


class TestJobQueue(unittest.TestCase):
    def test_claim_next_honors_payload_sort_key(self):
        from storage.repositories.jobs import JOBS_FILE, JsonJobRepository

        with tempfile.TemporaryDirectory() as tmp:
            jobs_path = os.path.join(tmp, "jobs.json")
            with patch("storage.repositories.jobs.JOBS_FILE", jobs_path):
                repo = JsonJobRepository()
                first = repo.enqueue(
                    {
                        "channel_id": "tapin",
                        "job_type": "render",
                        "payload_json": json.dumps({"sort_key": 2}),
                    }
                )
                second = repo.enqueue(
                    {
                        "channel_id": "tapin",
                        "job_type": "upload",
                        "payload_json": json.dumps({"sort_key": 0}),
                    }
                )
                claimed = repo.claim_next()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, second.id)
        self.assertNotEqual(claimed.id, first.id)

    def test_list_active_jobs_labels_quota_defer_and_exposes_schedule(self):
        from core.job_queue import display_status, list_active_jobs, queue_depth
        from storage.repositories.jobs import JOBS_FILE, JsonJobRepository

        with tempfile.TemporaryDirectory() as tmp:
            jobs_path = os.path.join(tmp, "jobs.json")
            with patch("storage.repositories.jobs.JOBS_FILE", jobs_path):
                repo = JsonJobRepository()
                future = datetime.now(timezone.utc) + timedelta(hours=2)
                repo.enqueue(
                    {
                        "channel_id": "tapin",
                        "job_type": "upload",
                        "payload_json": "{}",
                        "last_error": "quota exhausted until reset",
                        "scheduled_at": future,
                    }
                )
                repo.enqueue(
                    {
                        "channel_id": "tapin",
                        "job_type": "render",
                        "payload_json": "{}",
                    }
                )
                rows = list_active_jobs(repo)
        self.assertEqual(len(rows), 2)
        quota = next(j for j in rows if j.job_type == "upload")
        self.assertEqual(display_status(quota), "awaiting_quota")
        self.assertTrue(quota.scheduled_at)
        self.assertEqual(queue_depth(rows), 2)

    def test_drag_reorder_writes_sort_key_that_claim_next_uses(self):
        from core.job_queue import apply_drag_order
        from storage.repositories.jobs import JOBS_FILE, JsonJobRepository

        with tempfile.TemporaryDirectory() as tmp:
            jobs_path = os.path.join(tmp, "jobs.json")
            with patch("storage.repositories.jobs.JOBS_FILE", jobs_path):
                repo = JsonJobRepository()
                a = repo.enqueue(
                    {"channel_id": "tapin", "job_type": "render", "payload_json": "{}"}
                )
                b = repo.enqueue(
                    {"channel_id": "tapin", "job_type": "upload", "payload_json": "{}"}
                )
                apply_drag_order(repo, [b.id, a.id])
                claimed = repo.claim_next()
        self.assertEqual(claimed.id, b.id)

    def test_ops_queue_panel_is_registered(self):
        from desktop.launch import desktop_mode
        from scripts.ops import COMMANDS

        self.assertIn("queue-panel", COMMANDS)
        self.assertEqual(desktop_mode(["--queue"]), "queue")
        self.assertEqual(desktop_mode(["--review"]), "review")


class TestQueueDepthBadge(unittest.TestCase):
    def test_badge_is_the_integer_from_list_active_jobs(self):
        from core.job_queue import queue_depth_badge
        from storage.repositories.jobs import JobRecord

        jobs = [
            JobRecord(id=1, channel_id="tapin", job_type="render", status="pending"),
            JobRecord(id=2, channel_id="tapin", job_type="upload", status="running"),
        ]
        self.assertEqual(queue_depth_badge(jobs), "2")


class TestBoothChromeCss(unittest.TestCase):
    def test_booth_html_has_blur_bezel_yt_mock_switcher_and_cheatsheet(self):
        from core.html_report import _CSS
        from core.review_booth import booth_html, cheat_sheet_copy
        from core.review_keys import apply_review_key

        html = booth_html(channel_id="tapin", thumb_path="")
        self.assertIn("backdrop-filter", _CSS)
        self.assertIn("phone-bezel", _CSS)
        self.assertIn("yt-mock", _CSS)
        self.assertIn("channel-switcher", html)
        self.assertIn("tapin", html)
        self.assertIn("moneywise", html)
        self.assertIn("cheat-sheet", html)
        self.assertIn("phone-bezel", html)
        self.assertIn("yt-mock", html)
        copy = cheat_sheet_copy()
        self.assertIn("J", copy)
        self.assertIn("K", copy)
        self.assertIn("L", copy)
        self.assertIn(",", copy)
        self.assertIn(".", copy)
        self.assertIn("S", copy)
        pos, paused = apply_review_key("h", position_ms=12_000, duration_ms=20_000, paused=False)
        self.assertEqual(pos, 3000)
        self.assertFalse(paused)
        pos2, _ = apply_review_key("h", position_ms=500, duration_ms=20_000, paused=True)
        self.assertEqual(pos2, 500)


class TestTitleCardWrap(unittest.TestCase):
    def test_two_line_and_three_line_wrap_write_a_still(self):
        from core.title_card_wrap import wrap_title_card, write_title_card_still

        text = "UFC 300 Main Event Purse Leak Tonight"
        two = wrap_title_card(text, max_lines=2)
        three = wrap_title_card(text, max_lines=3)
        self.assertLessEqual(len(two), 2)
        self.assertLessEqual(len(three), 3)
        self.assertGreaterEqual(len(three), len(two))
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "card.png")
            written = write_title_card_still(text, dest, max_lines=2)
            self.assertTrue(os.path.isfile(written))
            self.assertGreater(os.path.getsize(written), 0)


class TestNumericPlausibility(unittest.TestCase):
    def test_ten_x_purse_flags_even_when_the_span_is_in_the_facts(self):
        from core.fact_grounding import find_plausibility_outliers, find_ungrounded_numeric

        facts = "VERIFIED FACTS:\n- $50 million in PPV buys last year\n- purse $5 million"
        script = "The UFC purse is $50 million."
        self.assertEqual(GRADE_VERSION, "v3")
        self.assertEqual(find_ungrounded_numeric(script, facts), [])
        outliers = find_plausibility_outliers(script, facts)
        self.assertTrue(any("50" in item and "million" in item.lower() for item in outliers))
        self.assertEqual(
            find_plausibility_outliers("The UFC purse is $5 million.", facts),
            [],
        )


class TestChannelClock(unittest.TestCase):
    def test_tonight_and_this_weekend_resolve_against_tapin_et(self):
        from core.publish_windows import resolve_relative_clock

        wednesday = datetime(2026, 9, 9, 14, 0, tzinfo=timezone.utc)
        tonight = resolve_relative_clock("tonight", now=wednesday)
        weekend = resolve_relative_clock("this weekend", now=wednesday)
        self.assertIsNotNone(tonight)
        self.assertIsNotNone(weekend)
        self.assertGreaterEqual(tonight.hour, 18)
        self.assertEqual(weekend.weekday(), 5)


class TestCounterfactualLog(unittest.TestCase):
    def test_ignored_recommendation_is_persisted(self):
        from core.counterfactual import record_override

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "overrides.json")
            row = record_override(
                offered="Marvel Rivals patch wishlist",
                chosen="random UFC purse video",
                path=path,
            )
            blob = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(row["offered"], "Marvel Rivals patch wishlist")
        self.assertEqual(blob[-1]["chosen"], "random UFC purse video")


class TestRecencyDecay(unittest.TestCase):
    def test_six_month_old_video_votes_quieter_than_last_week(self):
        from core.best_bet import recency_weight, weighted_engaged_mean

        self.assertLess(recency_weight(180), recency_weight(7) / 2)
        decayed = weighted_engaged_mean([(0.90, 180.0), (0.20, 7.0)])
        raw = (0.90 + 0.20) / 2
        self.assertLess(decayed, raw)
        self.assertLess(abs(decayed - 0.20), abs(decayed - 0.90))


class TestCalibrationDrift(unittest.TestCase):
    def test_worse_window_is_a_line_not_a_silent_skip(self):
        from core.analyst_accuracy import drift_line

        line = drift_line(recent_hit_rate=0.40, older_hit_rate=0.70)
        self.assertIn("drift", line.lower())
        self.assertIn("40%", line.replace(" ", ""))
        self.assertEqual(drift_line(recent_hit_rate=0.80, older_hit_rate=0.70), "")


class TestCompetitorTitleDuplicate(unittest.TestCase):
    def test_word_for_word_competitor_title_is_advisory(self):
        from core.title_overlap import verbatim_competitor_advisory

        note = verbatim_competitor_advisory(
            "Islam Makhachev destroys opponent",
            [{"title": "Islam Makhachev destroys opponent", "channel": "UFC"}],
        )
        self.assertIn("UFC", note)
        lowered = note.lower()
        self.assertTrue("word-for-word" in lowered or "word for word" in lowered)
        self.assertEqual(
            verbatim_competitor_advisory(
                "TapIn take on the Makhachev fight",
                [{"title": "Islam Makhachev destroys opponent", "channel": "UFC"}],
            ),
            "",
        )


class TestTestTimeBudget(unittest.TestCase):
    def test_cheap_subset_ratchet_uses_the_injected_clock(self):
        from core.startup_budget import elapsed_over_budget, measure_callable

        ticks = iter([1.0, 4.5])
        elapsed = measure_callable(lambda: None, clock=lambda: next(ticks))
        self.assertAlmostEqual(elapsed, 3.5)
        self.assertTrue(elapsed_over_budget(elapsed, 1.0))
        self.assertFalse(elapsed_over_budget(0.2, 2.0))


class TestWhySlowStillOmitsWordCount(unittest.TestCase):
    def test_word_count_is_not_ranked_as_a_phase(self):
        from core.why_slow import why_slow_lines

        lines = why_slow_lines({"word_count": 410.0, "tts": 12.0})
        blob = " ".join(lines)
        self.assertNotIn("word_count", blob)
        self.assertIn("tts", blob.lower())


try:
    from PySide6.QtWidgets import QApplication, QGraphicsItem
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]
    QGraphicsItem = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestQueueAndStudioWidgets(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def test_studio_layer_is_movable_guides_are_not(self):
        from PIL import Image

        from desktop.studio import StudioWindow

        with tempfile.TemporaryDirectory() as tmp:
            thumb = Path(tmp) / "thumb.png"
            Image.new("RGB", (320, 180), (30, 30, 30)).save(thumb)
            window = StudioWindow(context={"thumb_path": str(thumb), "channel_id": "tapin"})
        flags = QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        movable = [item for item in window.scene.items() if item.flags() & flags]
        locked = [item for item in window.scene.items() if not (item.flags() & flags)]
        self.assertGreaterEqual(len(movable), 1)
        self.assertGreaterEqual(len(locked), 1)
        window.close()

    def test_queue_window_lists_jobs(self):
        from desktop.queue import QueueWindow
        from storage.repositories.jobs import JobRecord

        jobs = [
            JobRecord(
                id=9,
                channel_id="tapin",
                job_type="render",
                status="pending",
                last_error="",
            )
        ]
        window = QueueWindow(jobs=jobs)
        self.assertIn("render", window.list_widget.item(0).text())
        window.close()

    def test_review_qss_has_no_filter_and_drafted_approve_stays_off(self):
        from desktop.review import ReviewWindow

        window = ReviewWindow(
            context={
                "mp4_path": "",
                "run_id": 75,
                "run_status": "drafted",
                "can_approve": False,
                "refuse_reason": "Run 75 has no MP4 on disk. Status: drafted",
                "grade": "n/a",
                "channel_id": "tapin",
            }
        )
        self.assertNotIn("filter:", window.styleSheet())
        self.assertFalse(window.approve_btn.isEnabled())
        window.close()


if __name__ == "__main__":
    unittest.main()
