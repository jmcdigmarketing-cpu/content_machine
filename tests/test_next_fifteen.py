"""The fifteen open items taken when Claude had not queued a new list.

Each test calls the real function. Network, clock, and the filesystem are
the only things stood in.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image


class MenuKeyTests(unittest.TestCase):
    def test_one_key_is_the_choice_and_enter_is_empty(self):
        from core.console_input import menu_line

        got = menu_line(
            "  Select 1-6 [1]: ",
            input_fn=lambda _prompt: "SHOULD NOT RUN",
            read_char=lambda: "6",
            print_fn=lambda *_a, **_k: None,
        )
        self.assertEqual(got, "6")
        blank = menu_line(
            "  Select 1-6 [1]: ",
            input_fn=lambda _prompt: "SHOULD NOT RUN",
            read_char=lambda: "\r",
            print_fn=lambda *_a, **_k: None,
        )
        self.assertEqual(blank, "")

    def test_a_scripted_answer_stays_a_whole_line(self):
        from core.console_input import menu_line

        got = menu_line("  Select 1-6 [1]: ", input_fn=lambda _prompt: "2")
        self.assertEqual(got, "2")

    def test_startup_takes_the_key_the_reader_returns(self):
        from core.ui import prompt_startup_mode

        with patch("core.intelligence_report.intelligence_mode_enabled", return_value=False):
            mode = prompt_startup_mode(
                print_fn=lambda *_a, **_k: None,
                input_fn=lambda _prompt: "6",
            )
        self.assertEqual(mode, "overnight_review")


class TopicRecallTests(unittest.TestCase):
    def test_enter_keeps_the_last_topic_for_that_channel(self):
        from core.ui import recall_topic, remember_topic, resolve_topic_answer

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "topics.json")
            with patch.dict(os.environ, {"TOPIC_RECALL_FILE": path}):
                remember_topic("tapin", "How the 0-4 Chargers can turn it around")
                self.assertEqual(
                    resolve_topic_answer("", "tapin"),
                    "How the 0-4 Chargers can turn it around",
                )
                self.assertEqual(
                    resolve_topic_answer("Titans at Colts", "tapin"), "Titans at Colts"
                )
                self.assertEqual(recall_topic("tapin"), "Titans at Colts")
                self.assertEqual(recall_topic("moneywise"), "")

    def test_the_prompt_names_the_recalled_topic(self):
        from core.ui import remember_topic, topic_prompt

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "topics.json")
            with patch.dict(os.environ, {"TOPIC_RECALL_FILE": path}):
                self.assertEqual(topic_prompt("tapin"), "  Topic: ")
                remember_topic("tapin", "Titans at Colts")
                self.assertIn("Titans at Colts", topic_prompt("tapin"))


class QuietModeTests(unittest.TestCase):
    def test_quiet_hides_the_breakdown_and_keeps_the_report(self):
        from core.ui import display_fact_engine_report, display_signal_breakdown

        signals = {"youtube": {"connected": True, "active": True, "score": 40}}
        lines: list[str] = []

        def say(*args, **_kwargs):
            lines.append(" ".join(str(arg) for arg in args))

        with patch.dict(os.environ, {"CONTENT_UI_QUIET": "1"}):
            display_signal_breakdown(signals, print_fn=say)
            display_fact_engine_report(
                {"sentence_rhythm": ["uniform sentence length"]},
                print_fn=say,
            )
        self.assertFalse(any("Signal breakdown" in line for line in lines))
        self.assertTrue(any("uniform sentence length" in line for line in lines))

    def test_the_breakdown_is_printed_when_quiet_is_off(self):
        from core.ui import display_signal_breakdown

        lines: list[str] = []

        def say(*args, **_kwargs):
            lines.append(" ".join(str(arg) for arg in args))

        with patch.dict(os.environ, {"CONTENT_UI_QUIET": ""}):
            display_signal_breakdown(
                {"youtube": {"connected": True, "active": True, "score": 40}},
                print_fn=say,
            )
        self.assertTrue(any("Signal breakdown" in line for line in lines))

    def test_the_flag_is_consumed_from_argv(self):
        from core.ui import consume_quiet_flag, quiet_on

        with patch.dict(os.environ, {"CONTENT_UI_QUIET": ""}):
            kept = consume_quiet_flag(["main.py", "--quiet", "--art"])
            self.assertEqual(kept, ["main.py", "--art"])
            self.assertTrue(quiet_on())


class GateBellTests(unittest.TestCase):
    def test_a_gate_on_a_tty_rings_once(self):
        from core.ask import gate_bell

        self.assertEqual(gate_bell("  Select 1-6 [1]: ", tty=True, no_color=False), "\a")

    def test_a_fact_prompt_and_a_piped_run_stay_quiet(self):
        from core.ask import gate_bell

        self.assertEqual(gate_bell("  Fact 1: ", tty=True, no_color=False), "")
        self.assertEqual(gate_bell("  Proceed? [y = render]: ", tty=False, no_color=False), "")
        self.assertEqual(gate_bell("  Select 1-6 [1]: ", tty=True, no_color=True), "")

    def test_the_terminal_backend_writes_the_bell(self):
        from core.ask import TerminalBackend

        written: list[str] = []

        class Out:
            def isatty(self) -> bool:
                return True

            def write(self, text: str) -> None:
                written.append(text)

            def flush(self) -> None:
                return None

        with (
            patch("sys.stdout", Out()),
            patch("builtins.input", return_value="1"),
            patch.dict(os.environ, {"NO_COLOR": ""}),
        ):
            self.assertEqual(TerminalBackend().ask_text("  Select 1-6 [1]: "), "1")
        self.assertIn("\a", "".join(written))


class OscLinkTests(unittest.TestCase):
    def test_a_youtube_url_and_a_path_are_links_on_a_tty(self):
        from core.ui import linkify

        text = linkify(
            r"file: C:\dev\content_machine\output\tapin\v.mp4  YouTube: https://youtu.be/abc123",
            tty=True,
        )
        self.assertIn("\033]8;;https://youtu.be/abc123", text)
        self.assertIn("abc123", text)
        self.assertIn("\033]8;;file:///", text)
        self.assertIn("v.mp4", text)

    def test_plain_text_off_a_tty(self):
        from core.ui import linkify

        raw = "YouTube: https://youtu.be/abc123 (public)"
        self.assertEqual(linkify(raw, tty=False), raw)

    def test_a_run_id_links_to_its_trace(self):
        from core.ui import linkify

        text = linkify("run 155 waits", tty=True)
        self.assertIn("run 155", text)
        self.assertIn("\033]8;;file:///", text)
        self.assertIn("155.json", text)

    def test_video_lines_link_when_asked(self):
        from core.batch_review import video_lines

        run = SimpleNamespace(mp4_path=r"C:\dev\content_machine\output\tapin\v.mp4")
        public = SimpleNamespace(
            youtube_video_id="abc123", privacy_status="public", content_run_id=126
        )
        with (
            patch("core.batch_review._run_record", return_value=run),
            patch("core.batch_review._publish_row", return_value=public),
            patch("publishing.crosspost.run_state_line", return_value=""),
        ):
            text = "\n".join(video_lines(126, "tapin", tty=True))
        self.assertIn("\033]8;;https://youtu.be/abc123", text)
        self.assertIn("https://youtu.be/abc123", text)


class ReadingLevelTests(unittest.TestCase):
    EASY = (
        "The cat sat on the mat. The dog ran to the park. "
        "The sun was hot. The kids had fun. The day was good."
    )
    HARD = (
        "The phenomenological reconstitution of epistemological frameworks "
        "necessitates interdisciplinary hermeneutical methodologies. "
        "Contemporaneous quantification of sociocultural paradigmatic "
        "transformations remains methodologically intractable."
    )

    def test_a_simple_script_grades_easier_than_a_dense_one(self):
        from core.script_craft import reading_grade

        easy = reading_grade(self.EASY)
        hard = reading_grade(self.HARD)
        self.assertIsNotNone(easy)
        self.assertIsNotNone(hard)
        self.assertLess(easy, 8)
        self.assertGreater(hard, 12)
        self.assertGreater(hard, easy)

    def test_a_target_the_script_misses_is_on_the_check(self):
        from core.script_craft import script_check

        check = script_check(script=self.HARD, reading_target=6)
        self.assertFalse(check["ok"])
        self.assertTrue(any("reading grade" in why for why in check["why"]))

    def test_shipped_tapin_has_no_target_so_a_hard_script_is_not_blocked(self):
        """The grade is recorded. TapIn does not declare a target, so the check
        does not fail a script for it. A number measured on real scripts would
        close the gap by setting channels.json reading_level."""
        from config.channels import channel_reading_target
        from core.script_craft import script_check

        self.assertIsNone(channel_reading_target("tapin"))
        check = script_check(script=self.HARD)
        self.assertTrue(check["ok"])
        self.assertFalse(any("reading grade" in why for why in check["why"]))

    def test_the_report_prints_the_grade(self):
        from core.ui import display_fact_engine_report

        lines: list[str] = []
        display_fact_engine_report({"reading_grade": 6.2}, print_fn=lines.append)
        self.assertTrue(any("6.2" in line for line in lines))


class AudienceRegionTests(unittest.TestCase):
    def test_the_channel_language_wins_over_the_env_and_does_not_geo_block(self):
        from core.youtube_meta import apply_snippet_defaults

        with patch.dict(os.environ, {"YOUTUBE_DEFAULT_LANGUAGE": "fr"}):
            out = apply_snippet_defaults(
                {"title": "Titans at Colts"},
                topic="Titans at Colts",
                channel_id="tapin",
            )
        self.assertEqual(out["defaultLanguage"], "en")
        self.assertEqual(out["defaultAudioLanguage"], "en")
        self.assertNotIn("regionRestriction", out)

    def test_the_dry_run_names_the_region_outside_the_insert_body(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import dry_run_insert_body

        body = dry_run_insert_body(
            PublishRequest(file_path="out.mp4", title="Titans at Colts", description=""),
            channel_id="tapin",
        )
        self.assertEqual(body["audience"]["region"], "US")
        self.assertNotIn("regionRestriction", json.dumps(body["snippet"]))
        self.assertNotIn("regionRestriction", json.dumps(body["status"]))


class RestoreDrillTests(unittest.TestCase):
    def test_a_backed_up_trace_comes_back(self):
        from core.moat_backup import apply_plan, plan, restore_into

        with tempfile.TemporaryDirectory() as tmp:
            traces = os.path.join(tmp, "traces")
            os.makedirs(traces)
            with open(os.path.join(traces, "1.json"), "w", encoding="utf-8") as handle:
                handle.write('{"topic": "Titans at Colts"}')
            backup = os.path.join(tmp, "backup")
            into = os.path.join(tmp, "restored")
            with (
                patch("core.moat_backup.TRACES_DIR", traces),
                patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": "", "DATABASE_URL": ""}),
            ):
                apply_plan(plan(backup), apply=True)
                names = restore_into(backup, into)
            restored = os.path.join(into, "traces", "1.json")
            with open(restored, encoding="utf-8") as handle:
                self.assertIn("Titans at Colts", handle.read())
            self.assertTrue(any(name.endswith("1.json") for name in names))


class OpenIndexTests(unittest.TestCase):
    def test_a_ticked_item_leaves_the_list(self):
        from core.roadmap_index import open_numbered

        lines = [
            "- [ ] 489. **Single-key menu mode** `[S]`",
            "- [x] 490. **Progress ETA** `[S]`",
        ]
        self.assertEqual([number for number, _title in open_numbered(lines)], [489])
        lines[0] = lines[0].replace("[ ]", "[x]", 1)
        self.assertEqual(open_numbered(lines), [])

    def test_the_index_prints_the_open_numbers(self):
        from core.roadmap_index import render

        text = render()
        self.assertIn("reprint a past run", text)


class ThumbnailFitTests(unittest.TestCase):
    def test_a_narrow_plate_wraps_and_the_first_line_is_larger(self):
        from assets.thumbnail_compose import compose_thumbnail

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "plate.jpg")
            plate = compose_thumbnail(
                Image.new("RGB", (280, 200), (12, 14, 28)),
                "Los Angeles Chargers Super Bowl Path After The Denver Loss",
                dest,
            )
        self.assertEqual(plate.refused, "")
        self.assertGreaterEqual(len(plate.line_sizes), 2)
        self.assertGreater(plate.line_sizes[0], plate.line_sizes[1])
        _x0, _y0, x1, y1 = plate.text_box
        self.assertLessEqual(x1, plate.width - plate.margin)
        self.assertLessEqual(y1, plate.height - plate.margin)


class PaletteTests(unittest.TestCase):
    def test_moneywise_is_not_painted_in_tapin_white(self):
        from assets.thumbnail_compose import compose_thumbnail

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "plate.jpg")
            plate = compose_thumbnail(
                Image.new("RGB", (1280, 720), (18, 22, 42)),
                "Rates moved",
                dest,
                channel_id="moneywise",
            )
        self.assertEqual(plate.refused, "")
        self.assertEqual(plate.fill, (0xF7, 0xE7, 0xA9))
        self.assertNotEqual(plate.fill, (255, 255, 255))

    def test_a_pair_under_the_contrast_line_is_not_used(self):
        from assets.thumbnail_compose import compose_thumbnail

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "plate.jpg")
            plate = compose_thumbnail(
                Image.new("RGB", (1280, 720), (0xF7, 0xE7, 0xA9)),
                "Rates moved",
                dest,
                channel_id="moneywise",
            )
        self.assertNotEqual(plate.fill, (0xF7, 0xE7, 0xA9))


class ExplainTests(unittest.TestCase):
    def test_the_narrative_uses_the_trace_fields(self):
        from core.run_trace import explain_trace

        text = explain_trace(
            {
                "run_id": 155,
                "status": "rendered",
                "input_topic": "Titans at Colts",
                "selected_topic": "Titans can stop the run",
                "timings": {"signals_and_variants": 12.5, "variant_scoring": 3.0},
                "quality": {"grade": "B"},
                "cost": {"total": 0.42},
            }
        )
        self.assertIn("Titans at Colts", text)
        self.assertIn("Titans can stop the run", text)
        self.assertIn("rendered", text)
        self.assertIn("12.5", text)
        self.assertIn("0.42", text)
        self.assertIn("B", text)

    def test_a_missing_run_is_one_sentence(self):
        from core.run_trace import explain_trace

        self.assertEqual(explain_trace(None), "No run with that id.")


class OpeningReuseTests(unittest.TestCase):
    def test_a_repeated_opening_is_dropped_once_and_the_count_is_kept(self):
        from core.authenticity import drop_reused_opening

        script = "The Chargers can turn it around this year. The rest of this one is new."
        recent = ["The Chargers can turn it around this year. An older video said it."]
        new, report = drop_reused_opening(script, recent)
        self.assertEqual(report["before"], 1)
        self.assertTrue(report["dropped"])
        self.assertNotIn("turn it around", new.split(".")[0])
        self.assertIn("The rest of this one is new", new)

    def test_a_fresh_opening_is_unchanged(self):
        from core.authenticity import drop_reused_opening

        script = "Herbert threw for three hundred yards. Tap in for more."
        new, report = drop_reused_opening(script, ["The Chargers can turn it around this year."])
        self.assertEqual(new, script)
        self.assertEqual(report["before"], 0)
        self.assertFalse(report["dropped"])

    def test_a_script_from_eight_days_ago_does_not_count(self):
        from core.authenticity import scripts_within

        now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        rows = [
            ("The Chargers can turn it around this year.", now - timedelta(days=8)),
            ("Herbert threw for three hundred yards.", now - timedelta(days=2)),
        ]
        kept = scripts_within(rows, now=now, days=7)
        self.assertEqual(kept, ["Herbert threw for three hundred yards."])


class TimedPinTests(unittest.TestCase):
    def test_an_enabled_pin_waits_for_the_peak(self):
        from youtube.pin_comment import maybe_pin_top_answer

        service = MagicMock()
        monday = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "YOUTUBE_PIN_COMMENT": "true",
                "PIN_COMMENT_FILE": os.path.join(tmp, "pins.json"),
            }
            with patch.dict(os.environ, env):
                result = maybe_pin_top_answer(
                    service,
                    video_id="vid1",
                    topic="GTA 6 leak",
                    channel_id="tapin",
                    questions=["When does GTA 6 actually release on PlayStation?"],
                    now=monday,
                )
        self.assertEqual(result.status, "scheduled")
        service.commentThreads.assert_not_called()
        self.assertIn("T", result.detail or "")

    def test_a_due_pin_is_posted_once(self):
        from youtube.pin_comment import maybe_pin_top_answer, post_due

        service = MagicMock()
        service.commentThreads.return_value.insert.return_value.execute.return_value = {
            "id": "thread1"
        }
        monday = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
        later = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pins.json")
            with patch.dict(os.environ, {"YOUTUBE_PIN_COMMENT": "true", "PIN_COMMENT_FILE": path}):
                maybe_pin_top_answer(
                    service,
                    video_id="vid1",
                    topic="GTA 6 leak",
                    channel_id="tapin",
                    questions=["When does GTA 6 actually release on PlayStation?"],
                    now=monday,
                )
                posted = post_due(service, now=later)
        self.assertEqual(posted, 1)
        insert = service.commentThreads.return_value.insert
        insert.assert_called_once()
        body = insert.call_args.kwargs["body"]
        text = body["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
        self.assertIn("GTA", text)


class FeedFallbackTests(unittest.TestCase):
    def test_a_feed_wide_404_keeps_what_the_free_path_returned(self):
        from analytics.competitor_sync import sync_competitors
        from analytics.youtube_rss import FeedProbe

        channels = [
            {"id": "UCaaaa", "label": "MMA"},
            {"id": "UCbbbb", "label": "NFL"},
        ]
        probes = {
            "UCaaaa": FeedProbe([], 404),
            "UCbbbb": FeedProbe([], 404),
        }

        def fetch(channel_id: str, *, max_results: int = 8) -> list[dict]:
            del max_results
            if channel_id == "UCaaaa":
                return [{"title": "UFC card this weekend", "video_id": "aaaaaaaaaaa"}]
            return []

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "competitors.json")
            with (
                patch("analytics.competitor_sync.get_competitor_channels", return_value=channels),
                patch("analytics.competitor_sync.competitors_data_path", return_value=path),
                patch("analytics.competitor_sync.ensure_data_dir"),
                patch(
                    "analytics.youtube_rss.probe_channel_feed",
                    side_effect=lambda cid, **_kw: probes[cid],
                ),
                patch("apis.youtube_quota.record_usage") as recorded,
            ):
                snap = sync_competitors("tapin", uploads_free=fetch)
        self.assertEqual(snap["sync_method"], "yt-dlp")
        by_id = {row["youtube_channel_id"]: row for row in snap["competitors"]}
        self.assertEqual(by_id["UCaaaa"]["recent_videos"][0]["title"], "UFC card this weekend")
        self.assertEqual(by_id["UCaaaa"]["source"], "yt-dlp")
        self.assertEqual(by_id["UCbbbb"]["recent_videos"], [])
        self.assertEqual(by_id["UCbbbb"]["source"], "rss")
        recorded.assert_not_called()

    def test_an_empty_free_path_still_says_the_feed_is_down(self):
        from analytics.competitor_sync import sync_competitors
        from analytics.youtube_rss import FeedProbe

        channels = [{"id": "UCaaaa", "label": "MMA"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "competitors.json")
            with (
                patch("analytics.competitor_sync.get_competitor_channels", return_value=channels),
                patch("analytics.competitor_sync.competitors_data_path", return_value=path),
                patch("analytics.competitor_sync.ensure_data_dir"),
                patch(
                    "analytics.youtube_rss.probe_channel_feed",
                    return_value=FeedProbe([], 404),
                ),
                patch("apis.youtube_quota.record_usage") as recorded,
            ):
                snap = sync_competitors("tapin", uploads_free=lambda *_a, **_k: [])
        self.assertEqual(snap.get("feed_down"), 404)
        self.assertEqual(snap["competitors"][0]["recent_videos"], [])
        self.assertNotEqual(snap.get("sync_method"), "yt-dlp")
        recorded.assert_not_called()


if __name__ == "__main__":
    unittest.main()
