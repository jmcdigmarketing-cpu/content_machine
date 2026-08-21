"""Leave-the-terminal wave: HTML dumps, toasts, Explorer, booth, blockers."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import file_lock, html_report, output_paths, publish_blockers, review_booth, win_notify
from core.script_length import trim_overlength
from core.win_shell import last_media_file, reveal_in_explorer


class TestHtmlReport(unittest.TestCase):
    def test_themed_page_escapes_and_has_min_type(self):
        page = html_report.themed_page("T <x>", html_report.pre_body("a < b"), subtitle="sub")
        self.assertIn("font-size: 16px", page)
        self.assertIn("T &lt;x&gt;", page)
        self.assertIn("a &lt; b", page)
        self.assertNotIn("<x>", page)

    def test_dump_pre_writes_utf8_without_opening(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}):
                path = html_report.dump_pre("Reliability", "Apify ON", filename="rel.html")
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("Apify ON", text)
            self.assertIn("Content OS", text)


class TestQuotaChipAndToasts(unittest.TestCase):
    def test_chip_lines_from_snapshot(self):
        snap = {
            "youtube": {"used": 0, "limit": 10000, "remaining": 10000},
            "elevenlabs": {"chars_used": 1000},
            "apify": {"exhausted": True, "reason": "402 credits"},
        }
        with patch.dict(os.environ, {"ELEVENLABS_MONTHLY_CHAR_BUDGET": "100000"}):
            with patch("apis.youtube_quota.uploads_remaining", return_value=6):
                lines = win_notify.quota_chip_lines(snap)
        blob = " | ".join(lines)
        self.assertIn("uploads left", blob)
        self.assertIn("ElevenLabs", blob)
        self.assertIn("Apify: OFF", blob)

    def test_toast_disabled_in_suite(self):
        self.assertFalse(win_notify.toast_enabled())
        self.assertFalse(win_notify.toast("t", "b", key="x"))

    def test_notify_breaker_is_fail_open(self):
        win_notify.notify_breaker("Apify", "402")  # must not raise


class TestExplorerAndPaths(unittest.TestCase):
    def test_last_media_picks_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "video")
            os.makedirs(video)
            older = os.path.join(video, "a.mp4")
            newer = os.path.join(video, "b.mp4")
            with open(older, "w", encoding="utf-8") as fh:
                fh.write("1")
            os.utime(older, (1, 1))
            with open(newer, "w", encoding="utf-8") as fh:
                fh.write("2")
            with patch(
                "core.output_paths.ensure_channel_output_dirs",
                return_value={"video": video, "thumbnails": video},
            ):
                self.assertEqual(last_media_file("mp4"), os.path.abspath(newer))

    def test_reveal_missing_is_false(self):
        self.assertFalse(reveal_in_explorer(""))
        self.assertFalse(reveal_in_explorer(os.path.join("nope", "missing.mp4")))

    def test_max_path_clips_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_topic = "x" * 300
            with patch.dict(os.environ, {"WIN_MAX_PATH": "180"}):
                with patch(
                    "core.output_paths.ensure_channel_output_dirs",
                    return_value={
                        "root": tmp,
                        "audio": tmp,
                        "video": tmp,
                        "thumbnails": tmp,
                    },
                ):
                    mp3, name, mp4 = output_paths.media_paths_for_topic(
                        long_topic, channel_id="tapin", timestamp="20260821_000000"
                    )
            unclipped = f"{'x' * 300}_20260821_000000.mp4"
            self.assertLess(len(name), len(unclipped))
            self.assertTrue(name.endswith(".mp4"))
            self.assertTrue(mp3.endswith(".mp3"))
            self.assertTrue(os.path.basename(mp4).endswith(".mp4"))

    def test_long_prefix_only_when_over_limit(self):
        short = os.path.abspath("out.mp4")
        self.assertEqual(output_paths.windows_long_prefix(short), short)


class TestFileLock(unittest.TestCase):
    def test_detects_winerror_32(self):
        err = OSError(22, "locked")
        err.winerror = 32
        self.assertTrue(file_lock.is_lock_error(err))
        self.assertTrue(
            file_lock.is_lock_error(
                None,
                "The process cannot access the file " "because it is being used by another process",
            )
        )
        self.assertFalse(file_lock.is_lock_error(None, "amix failed"))

    def test_retry_then_succeeds(self):
        n = {"i": 0}

        def flaky():
            n["i"] += 1
            if n["i"] < 3:
                raise PermissionError("being used by another process")
            return "ok"

        self.assertEqual(file_lock.retry_locked(flaky, attempts=5, delay=0.0), "ok")
        self.assertEqual(n["i"], 3)


class TestScriptTrim(unittest.TestCase):
    def test_drops_padding_not_hook(self):
        hook = "Topuria walks in as champion."
        pad = "Anyway that is all I have. In conclusion this is filler. Basically yes."
        script = hook + " " + pad
        with patch.dict(os.environ, {"SCRIPT_TRIM": "true"}):
            out, removed = trim_overlength(script, max_words=8, min_words=3)
        self.assertGreater(removed, 0)
        self.assertIn("Topuria", out)
        self.assertLessEqual(len(out.split()), 8)

    def test_does_not_clip_single_sentence(self):
        one = "This is one very long sentence without a period that keeps going on and on"
        with patch.dict(os.environ, {"SCRIPT_TRIM": "true"}):
            out, removed = trim_overlength(one, max_words=3, min_words=1)
        self.assertEqual(removed, 0)
        self.assertEqual(out, one)

    def test_env_off(self):
        script = "Hook. Anyway filler. In conclusion more filler."
        with patch.dict(os.environ, {"SCRIPT_TRIM": "false"}):
            out, removed = trim_overlength(script, max_words=2, min_words=1)
        self.assertEqual(removed, 0)
        self.assertEqual(out, script)


class TestPublishBlockers(unittest.TestCase):
    def test_ready_sentence_when_gates_clear(self):
        with (
            patch("core.thin_facts.thin_facts_abort_reason", return_value=None),
            patch("core.render_gate.block_reason_from_quality", return_value=None),
            patch("core.authenticity.gate_mode", return_value="warn"),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch("core.cadence.cadence_status") as cad,
            patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value=None),
        ):
            cad.return_value.ok = True
            line = publish_blockers.blocking_publish_sentence(
                channel_id="tapin", quality={"authenticity_verdict": "ok"}, fact_count=8
            )
        self.assertIn("Nothing is blocking", line)

    def test_thin_facts_is_first_reason(self):
        with patch(
            "core.thin_facts.thin_facts_abort_reason",
            return_value="thin facts: 1 verified line(s)",
        ):
            line = publish_blockers.blocking_publish_sentence(fact_count=1)
        self.assertIn("thin facts", line)


class TestBoothAndLightbox(unittest.TestCase):
    def test_lightbox_without_file(self):
        html = review_booth.lightbox_html(None)
        self.assertIn("No thumbnail", html)

    def test_thin_facts_screen(self):
        html = review_booth.thin_facts_html("thin facts: 0", fact_count=0)
        self.assertIn("Thin-facts abort", html)
        self.assertIn("$0.31", html)

    def test_booth_approve_mentions_requeue(self):
        html = review_booth.booth_html(
            run_id=12, grade="B (80)", authenticity="ok", cost="tts $0.31"
        )
        self.assertIn("requeue-upload --run-id 12", html)
        self.assertIn("Reject", html)

    def test_write_booth_uses_html_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}):
                with patch.object(review_booth, "gather_booth_context", return_value={}):
                    path = review_booth.write_booth("tapin", open_browser=False)
            self.assertTrue(path.endswith("booth.html"))
            self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
