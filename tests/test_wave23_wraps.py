"""Wave 23 wraps (331–480 remaining): behavioral tests, no mocks of the unit under test."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from argparse import Namespace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from apis.signal_contract import make_signal
from scripts.ops import COMMANDS
from video.subtitles import split_script_into_lines

_CONTRACT = set(make_signal(connected=True, active=True).keys())


class TestOpsCommandRef(unittest.TestCase):
    def test_markdown_lists_every_live_command(self):
        from core.ops_command_ref import command_ref_markdown

        blob = command_ref_markdown()
        for name in COMMANDS:
            self.assertIn(f"`{name}`", blob)

    def test_docs_file_matches_the_registry(self):
        from core.ops_command_ref import DOCS_PATH, command_ref_markdown

        on_disk = Path(DOCS_PATH).read_text(encoding="utf-8")
        self.assertEqual(on_disk, command_ref_markdown())

    def test_command_is_registered(self):
        self.assertIn("command-ref", COMMANDS)
        self.assertIn("shell", COMMANDS)
        self.assertIn("diff-runs", COMMANDS)
        self.assertIn("publish-dry-run", COMMANDS)


class TestFactIntakeLinter(unittest.TestCase):
    def test_empty_paste_emits_no_warning(self):
        from core.fact_intake import lint_fact_intake

        with self.assertLogs(level="WARNING") as cm:
            logging.getLogger("core.fact_intake").warning("sentinel")
            warns = lint_fact_intake([])
        self.assertEqual(warns, [])
        self.assertEqual([r.getMessage() for r in cm.records], ["sentinel"])

    def test_url_only_duplicate_and_vault_contradiction(self):
        from core.fact_intake import lint_fact_intake

        warns = lint_fact_intake(
            [
                "https://example.com/story",
                "Jones beat Pereira",
                "Jones beat Pereira",
            ],
            vault_claims=["Pereira beat Jones"],
        )
        blob = " ".join(warns).lower()
        self.assertIn("url", blob)
        self.assertIn("duplicate", blob)
        self.assertIn("contradict", blob)

    def test_fetched_article_is_not_url_only(self):
        from unittest.mock import MagicMock, patch

        from core.fact_intake import lint_fact_intake
        from core.link_facts import extract_facts_from_url

        html = (
            "<html><head><title>Jones retains title</title></head><body>"
            "<p>Jon Jones remains the UFC heavyweight champion after a dominant "
            "unanimous decision in Las Vegas on Saturday night against Stipe.</p>"
            "</body></html>"
        )
        with (
            patch("apis.youtube_api.extract_youtube_video_id", return_value=None),
            patch("core.link_facts.requests.get") as mock_get,
        ):
            mock_get.return_value = MagicMock(status_code=200, text=html)
            facts = extract_facts_from_url("https://news.example.com/ufc-jones")
        self.assertTrue(facts)
        self.assertTrue(any(len(f) > 40 for f in facts))
        warns = lint_fact_intake(facts)
        self.assertFalse(any("url-only" in w.lower() for w in warns), warns)


class TestRenderSidecar(unittest.TestCase):
    def test_writes_facts_and_hashes_next_to_mp4(self):
        from core.render_artifacts import write_render_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "clip.mp4"
            mp4.write_bytes(b"fake-mp4-bytes")
            script = "Hook. Jones beat Pereira."
            out = write_render_sidecars(
                str(mp4),
                script=script,
                features={
                    "disputed": True,
                    "disputed_claims": ["x"],
                    "claim_verification": {"claims": [{"claim": "Jones beat Pereira"}]},
                    "source_urls": ["https://tapology.com/x"],
                },
                quality={"ungrounded_count": 0},
            )
            facts = Path(str(mp4).replace(".mp4", ".facts.json"))
            self.assertTrue(facts.is_file())
            data = json.loads(facts.read_text(encoding="utf-8"))
            self.assertTrue(data["disputed"])
            self.assertIn("Jones beat Pereira", json.dumps(data))
            self.assertIn("https://tapology.com/x", json.dumps(data))
            self.assertEqual(len(data["mp4_sha256"]), 64)
            self.assertEqual(len(data["script_sha256"]), 64)
            self.assertEqual(out["mp4_sha256"], data["mp4_sha256"])

    def test_missing_mp4_is_fail_open(self):
        from core.render_artifacts import write_render_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "gone.mp4")
            out = write_render_sidecars(missing, script="x", features={}, quality={})
            self.assertIsNone(out.get("mp4_sha256"))
            self.assertTrue(Path(missing.replace(".mp4", ".facts.json")).is_file())


class TestVoiceConsistency(unittest.TestCase):
    def test_mixed_elevenlabs_and_local_warns_once(self):
        from core.voice_consistency import voice_mix_warning

        with patch.dict(
            os.environ,
            {"TTS_PROVIDER": "elevenlabs", "INTRO_TTS_PROVIDER": "piper"},
            clear=False,
        ):
            msg = voice_mix_warning()
        self.assertIsNotNone(msg)
        self.assertIn("mix", msg.lower())

    def test_single_provider_is_silent(self):
        from core.voice_consistency import voice_mix_warning

        with patch.dict(
            os.environ, {"TTS_PROVIDER": "piper", "INTRO_TTS_PROVIDER": ""}, clear=False
        ):
            self.assertIsNone(voice_mix_warning())


class TestPersonaLinter(unittest.TestCase):
    def test_banned_filler_warns_on_tapin(self):
        from core.persona_lint import lint_persona_script

        hits = lint_persona_script("But here's the thing, the meta is dead.", channel_id="tapin")
        self.assertTrue(hits)

    def test_moneywise_ranges_are_not_flagged(self):
        from core.persona_lint import lint_persona_script

        hits = lint_persona_script(
            "Yields sit in the 5-10% band over 10-15 years.",
            channel_id="moneywise",
        )
        self.assertEqual(hits, [])


class TestCaptionOrphan(unittest.TestCase):
    def test_does_not_orphan_the_last_word(self):
        lines = split_script_into_lines("one two three four five six", max_words=5)
        self.assertGreaterEqual(len(lines[-1].split()), 2)

    def test_three_word_leftover_stays_three(self):
        lines = split_script_into_lines("a b c d e f g h", max_words=5)
        self.assertEqual(len(lines[-1].split()), 3)


class TestShortsEligibility(unittest.TestCase):
    def test_refuses_landscape_and_over_60s(self):
        from core.shorts_eligibility import shorts_refuse_reason

        self.assertIn(
            "60", shorts_refuse_reason(duration_s=61.0, width=1080, height=1920, title="T")
        )
        self.assertIn(
            "9:16", shorts_refuse_reason(duration_s=12.0, width=1920, height=1080, title="T")
        )
        self.assertIsNone(
            shorts_refuse_reason(duration_s=45.0, width=1080, height=1920, title="Ok")
        )

    def test_missing_file_is_fail_open(self):
        from core.shorts_eligibility import shorts_refuse_reason

        self.assertIsNone(
            shorts_refuse_reason(
                file_path="Z:/nope.mp4", duration_s=None, width=None, height=None, title="T"
            )
        )


class TestPublishDryRun(unittest.TestCase):
    def test_payload_has_snippet_and_redacts_tokens(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import dry_run_insert_body, redact_publish_payload

        req = PublishRequest(
            file_path="C:/tmp/out.mp4",
            title="Jones vs Pereira recap",
            description="desc",
            tags=["ufc"],
            category_id="20",
            privacy_status="private",
        )
        body = dry_run_insert_body(req, channel_id="tapin")
        self.assertIn("snippet", body)
        self.assertEqual(body["snippet"]["title"], req.title)
        self.assertNotIn("insert", json.dumps(body).lower())
        red = redact_publish_payload(
            {"snippet": body["snippet"], "access_token": "secret-token-value"}
        )
        self.assertNotIn("secret-token-value", json.dumps(red))

    def test_status_block_matches_what_publish_actually_sends(self):
        """#432 exists so the operator can review the EXACT payload. A hand-built
        status block that omits selfDeclaredMadeForKids (#107) or publishAt
        (#115/#116 windows) makes the dry run a different request than the real
        one, which is the failure it was meant to prevent."""
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import build_video_status, dry_run_insert_body

        req = PublishRequest(
            file_path="C:/tmp/out.mp4",
            title="GTA 6 leak explained",
            description="desc",
            tags=["gta"],
            category_id="20",
            privacy_status="private",
        )
        body = dry_run_insert_body(req, channel_id="tapin")
        self.assertEqual(body["status"], build_video_status(req, channel_id="tapin"))
        self.assertIs(body["status"].get("selfDeclaredMadeForKids"), False)

    def test_dry_run_flag_skips_videos_insert(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import YouTubePublisher

        req = PublishRequest(file_path=__file__, title="T", description="d")
        pub = YouTubePublisher()
        with (
            patch.dict(os.environ, {"PUBLISH_DRY_RUN": "1", "YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch.object(pub, "is_configured", return_value=True),
            patch("publishing.youtube_publisher.get_youtube_service") as svc,
            patch("publishing.youtube_publisher.has_quota_for_upload", return_value=True),
            patch("publishing.youtube_publisher._resolve_prior_upload", return_value=None),
            patch("publishing.youtube_publisher._ensure_publish_log", return_value=1),
            patch("publishing.youtube_publisher.MediaFileUpload"),
        ):
            svc.return_value.videos.return_value.insert.side_effect = AssertionError("insert")
            result = pub.publish(req, channel_id="tapin", content_run_id=1)
        self.assertEqual(result.status, "dry_run")
        svc.return_value.videos.return_value.insert.assert_not_called()


class TestEngagementSurprise(unittest.TestCase):
    def test_residual_is_actual_minus_predicted(self):
        from core.engagement_predictor import surprise_residual

        self.assertAlmostEqual(surprise_residual(0.40, 0.25), 0.15)
        self.assertIsNone(surprise_residual(None, 0.2))


class TestMetricsSyncAnomaly(unittest.TestCase):
    def test_stalled_sync_is_an_incident_fresh_is_quiet(self):
        from core.metrics_sync_health import metrics_sync_incident

        stalled = metrics_sync_incident(uploads=3, last_metrics_age_days=12, stall_days=7)
        self.assertIsNotNone(stalled)
        self.assertIn("sync", stalled.lower())
        self.assertIsNone(metrics_sync_incident(uploads=3, last_metrics_age_days=1, stall_days=7))
        self.assertIsNone(metrics_sync_incident(uploads=0, last_metrics_age_days=99))

    def test_reliability_line_no_warning_when_fresh(self):
        from core.reliability import render

        data = {
            "apify": {},
            "llm": {},
            "signals": {},
            "cache": {},
            "metrics_sync": {"incident": None, "detail": "metrics sync fresh (1d)"},
        }
        with self.assertLogs(level="WARNING") as cm:
            logging.getLogger("core.reliability").warning("sentinel")
            out = render(data)
        self.assertIn("fresh", out.lower())
        self.assertEqual([r.getMessage() for r in cm.records], ["sentinel"])


class TestCostPer1kViews(unittest.TestCase):
    def test_prints_when_views_positive_omits_when_zero(self):
        from core.unit_economics import ChannelEconomics, VideoEconomics, summary_lines

        with_views = ChannelEconomics(
            channel_id="tapin",
            videos=[
                VideoEconomics(run_id=1, title="a", cost_usd=0.50, revenue_usd=None, views=1000)
            ],
        )
        blob = "\n".join(summary_lines(with_views))
        self.assertRegex(blob, r"\$0\.50\s*/\s*1k")
        zero = ChannelEconomics(
            channel_id="tapin",
            videos=[VideoEconomics(run_id=1, title="a", cost_usd=0.50, revenue_usd=None, views=0)],
        )
        self.assertNotIn("/ 1k", "\n".join(summary_lines(zero)))
        self.assertNotIn("/1k", "\n".join(summary_lines(zero)).replace(" ", ""))


class TestSpendAnomaly(unittest.TestCase):
    def test_three_times_median_toasts_cheap_run_does_not(self):
        from core.spend_anomaly import maybe_toast_spend_anomaly

        calls: list[tuple[str, str]] = []

        def fake_toast(title, body, **kwargs):
            calls.append((title, body))
            return True

        with patch("core.win_notify.toast", side_effect=fake_toast):
            self.assertTrue(maybe_toast_spend_anomaly(0.90, [0.30, 0.28, 0.32]))
            self.assertFalse(maybe_toast_spend_anomaly(0.31, [0.30, 0.28, 0.32]))
        self.assertEqual(len(calls), 1)


class TestDiskGrowth(unittest.TestCase):
    def test_projects_days_and_empty_dir_is_honest(self):
        from core.disk_growth import project_days_until_full

        with tempfile.TemporaryDirectory() as tmp:
            empty = project_days_until_full(tmp, free_bytes=10 * 1024**3)
            self.assertIn("empty", empty.lower())
            root = Path(tmp)
            (root / "a.mp4").write_bytes(b"x" * 1000)
            os.utime(root / "a.mp4", (1_700_000_000, 1_700_000_000))
            (root / "b.mp4").write_bytes(b"y" * 2000)
            os.utime(root / "b.mp4", (1_700_086_400, 1_700_086_400))
            line = project_days_until_full(tmp, free_bytes=10_000, now_ts=1_700_172_800)
            self.assertRegex(line.lower(), r"day")


class TestRetentionReportOrder(unittest.TestCase):
    def test_growth_line_comes_after_the_truncated_file_list(self):
        """With >20 candidates the growth summary was appended between the last
        path and "... +N more", so the count read as more growth lines."""
        from core.artifact_retention import retention_report

        with tempfile.TemporaryDirectory() as tmp:
            traces = os.path.join(tmp, "data", "traces")
            os.makedirs(traces)
            for i in range(25):
                with open(os.path.join(traces, f"{i}.json"), "w", encoding="utf-8") as fh:
                    fh.write("{}")
            with patch.dict(
                os.environ, {"OBSIDIAN_VAULT_PATH": "", "ARTIFACT_RETENTION_ROOT": ""}, clear=False
            ):
                report = retention_report(tmp, older_than_days=0)

        lines = [ln for ln in report.splitlines() if "growth" in ln or "more" in ln]
        self.assertEqual(len(lines), 2, report)
        self.assertIn("more", lines[0])
        self.assertIn("growth", lines[1])


class TestDiffRuns(unittest.TestCase):
    def test_joins_grade_cost_ungrounded_disputed(self):
        from core.diff_runs import diff_quality_features

        a = {
            "quality": {"hook_score": 80, "ungrounded_count": 0, "disputed": False},
            "features": {"cost": {"total": 0.31}},
            "grade": "A",
        }
        b = {
            "quality": {"hook_score": 50, "ungrounded_count": 2, "disputed": True},
            "features": {"cost": {"total": 0.40}},
            "grade": "C",
        }
        blob = diff_quality_features(a, b)
        self.assertIn("A", blob)
        self.assertIn("C", blob)
        self.assertIn("0.31", blob)
        self.assertIn("ungrounded", blob.lower())
        self.assertIn("disputed", blob.lower())


class TestOperatorMinutes(unittest.TestCase):
    def test_persist_and_trend_isolated(self):
        from core.operator_minutes import record_publish_minutes, trend_line

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "operator_minutes.json")
            with patch("core.operator_minutes.MINUTES_FILE", path):
                record_publish_minutes("tapin", 12.0)
                record_publish_minutes("tapin", 8.0)
                line = trend_line("tapin")
            self.assertIn("10.0", line)
            self.assertTrue(os.path.isfile(path))


class TestExperimentMde(unittest.TestCase):
    def test_a_multi_arm_lever_cannot_start_at_n2(self):
        from core import experiment_levers
        from core.experiments import start_experiment

        # Read the arm count from the shipped lever, so a lever that gains an arm
        # cannot quietly pass a hardcoded number.
        arms = len(experiment_levers.arms("thumbnail_style"))
        self.assertGreater(arms, 2)

        with tempfile.TemporaryDirectory() as tmp:
            import config.paths as paths

            with (
                patch.object(paths, "EXPERIMENTS_FILE", os.path.join(tmp, "e.json")),
                patch("core.experiments._measured_n", return_value=2),
            ):
                with self.assertRaises(ValueError) as ctx:
                    start_experiment("tapin", "thumbnail_style")
                self.assertIn(str(arms), str(ctx.exception))
                rec = start_experiment("tapin", "hook_style")
                self.assertEqual(rec["lever"], "hook_style")


class TestPostTimingWeekdayHour(unittest.TestCase):
    def test_saturday_9pm_is_not_tuesday_9pm(self):
        import json as _json
        from datetime import datetime, timezone

        from analytics.post_timing import (
            PostScheduleConfig,
            PostSlot,
            learn_slots_from_analytics,
        )
        from storage.repositories.publish_log import PublishLogRecord

        tz = timezone.utc
        # Tuesday 21:00 weak; Saturday 21:00 strong — same hour, different weekday.
        samples = [
            (2025, 1, 7, 21, 0.10),
            (2025, 1, 14, 21, 0.10),
            (2025, 1, 4, 21, 0.50),
            (2025, 1, 11, 21, 0.48),
            (2025, 1, 18, 21, 0.49),
            (2025, 1, 25, 21, 0.47),
            (2025, 2, 1, 12, 0.11),
            (2025, 2, 8, 12, 0.11),
        ]
        rows = [
            PublishLogRecord(
                id=i + 1,
                content_run_id=0,
                channel_id="tapin",
                status="imported",
                metrics_json=_json.dumps({"engaged_rate": rate, "domain": "gaming"}),
                published_at=datetime(y, m, d, hr, 0, tzinfo=tz),
            )
            for i, (y, m, d, hr, rate) in enumerate(samples)
        ]
        static = PostScheduleConfig(timezone="UTC", slots=(PostSlot(0, 12, 0),))
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository") as repo,
            patch("analytics.post_timing._load_static_post_schedule", return_value=static),
        ):
            repo.return_value.list_timed_outcomes.return_value = rows
            learned = learn_slots_from_analytics("tapin", min_samples=8)
        top = learned.slots[0]
        self.assertEqual((top.weekday, top.hour), (5, 21))
        self.assertNotEqual((top.weekday, top.hour), (1, 21))


class TestFreeBackendContract(unittest.TestCase):
    def test_make_signal_keys_on_free_youtube_and_reddit(self):
        from apis import reddit_signal as rds
        from apis import youtube_apify_signal as yas

        yt_items = [
            {
                "title": "Free video",
                "viewCount": 200_000,
                "date": "2026-06-25T12:00:00",
                "channelName": "Free Channel",
                "duration": 50,
                "url": "https://www.youtube.com/watch?v=free",
            }
        ]
        with (
            patch.dict(os.environ, {"SIGNAL_BACKEND": "free", "APIFY_CONTENT_MACHINE_KEY": ""}),
            patch.object(yas, "youtube_available", return_value=True),
            patch.object(yas, "fetch_youtube_free", return_value=yt_items),
        ):
            yt = yas.get_youtube_apify_signal("q")
        self.assertTrue(_CONTRACT.issubset(yt.keys()))
        self.assertIn(yt["status"], {"ok", "inactive"})

        reddit_items = [
            {
                "title": "Pereira UFC 320 megathread",
                "ups": 3000,
                "numComments": 400,
                "subreddit": "ufc",
                "url": "https://www.reddit.com/r/ufc/comments/xyz/",
            }
        ]
        with (
            patch.dict(
                os.environ,
                {
                    "SIGNAL_BACKEND": "free",
                    "APIFY_CONTENT_MACHINE_KEY": "",
                    "REDDIT_CLIENT_ID": "id",
                    "REDDIT_CLIENT_SECRET": "sec",
                },
            ),
            patch.object(rds, "fetch_reddit_free", return_value=reddit_items),
        ):
            rd = rds.get_reddit_signal("Pereira", "tapin")
        self.assertTrue(_CONTRACT.issubset(rd.keys()))


class TestOpsDiffRunsRegistered(unittest.TestCase):
    def test_diff_runs_needs_two_ids(self):
        from scripts.ops import cmd_diff_runs

        buf = StringIO()
        with patch("sys.stdout", buf):
            rc = cmd_diff_runs(Namespace(run_id=None, target=None, channel="tapin"))
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
