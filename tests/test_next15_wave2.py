"""Next-15 wave 2: CI, honesty S, caption auto-place, render smoke.

Every behaviour test below was run against unmodified d1776a0 before the
matching production change. Guards for work already in HEAD were watched
going red with the guarded thing broken (rule 17).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_quota_governor import GovernorCase

FFMPEG = shutil.which("ffmpeg")


class TestCiConcurrencyCancelsSupersededRuns(unittest.TestCase):
    """#715. Unfiltered push+PR runs four jobs plus postgres on every branch,
    and a same-repo PR fires both events. A concurrency group keyed on the
    ref cancels the superseded run instead of stacking them."""

    def test_workflow_has_a_ref_keyed_concurrency_group(self):
        text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        live = "\n".join(
            line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        self.assertIn("concurrency:", live)
        self.assertIn("github.ref", live)
        self.assertIn("cancel-in-progress:", live)


class TestDeadYoutubeRssIdIsNotConfigured(unittest.TestCase):
    """#584. UCq-Fj5jknLsUf-MWSik4vhQ 404s (T-Series typo for McAfee). Same
    treatment as the dead ESPN/MMAJunkie feeds: it is not in the shipped
    config, so ops feeds / competitor-health stop probing it."""

    def test_shipped_tapin_competitors_do_not_include_the_404_id(self):
        from config.competitors import get_competitor_channels

        get_competitor_channels.cache_clear()
        rows = get_competitor_channels("tapin")
        ids = {r.get("id") for r in rows}
        self.assertNotIn("UCq-Fj5jknLsUf-MWSik4vhQ", ids)
        self.assertFalse(any("McAfee" in str(r.get("label") or "") for r in rows))


class TestProjectedCostPrintsBeforeTts(unittest.TestCase):
    """#572. features['cost'] at Proceed? is rendered=False, so TTS (91% of
    run cost) is $0 in the persisted dict. The operator has to see the
    projected total before generate_audio, not after display_summary."""

    def test_report_prints_projected_tts_line(self):
        from core.ui import display_fact_engine_report

        lines: list[str] = []
        display_fact_engine_report(
            {
                "cost": {"llm": 0.01, "tts": 0.0, "total": 0.01},
                "projected_cost": {"llm": 0.01, "tts": 0.27, "total": 0.28},
            },
            print_fn=lines.append,
        )
        blob = "\n".join(lines)
        self.assertIn("0.27", blob)
        self.assertIn("projected", blob.lower())
        self.assertIn("tts", blob.lower())


class TestFreeModeCostProof(unittest.TestCase):
    """#580. A Free/Piper run that still bills TTS is the $0 path lying."""

    def test_zero_tts_prints_billed_zero(self):
        from core.cost_meter import free_mode_cost_proof

        line = free_mode_cost_proof({"tts": 0.0, "llm": 0.0, "total": 0.0})
        self.assertIn("$0.0000", line)
        self.assertNotIn("WARNING", line.upper())

    def test_billed_tts_is_not_reported_as_free(self):
        from core.cost_meter import free_mode_cost_proof

        line = free_mode_cost_proof({"tts": 0.25, "total": 0.25})
        self.assertIn("0.25", line)
        self.assertIn("not $0", line.lower())

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("free-cost", ops.COMMANDS)

    def test_ops_reads_persisted_last_run_cost(self):
        """The verb has to prove what the last run billed, not re-estimate."""
        from scripts import ops

        buf = io.StringIO()
        with (
            patch(
                "core.review_booth.last_trace",
                return_value={"cost": {"tts": 0.0, "llm": 0.0, "total": 0.0}},
            ),
            redirect_stdout(buf),
        ):
            rc = ops.COMMANDS["free-cost"][1](Namespace(channel="tapin"))
        self.assertEqual(rc, 0)
        blob = buf.getvalue().lower()
        self.assertIn("$0.0000", blob)
        self.assertNotIn("not $0", blob)


class TestDescriptionFoldPreview(unittest.TestCase):
    """#595. YouTube hides everything past the fold (~100 chars / first
    two lines). A dry-render has to show what viewers see without opening
    Studio."""

    def test_long_description_splits_at_the_fold(self):
        from core.description_fold import fold_preview

        body = (
            "Jon Jones beat Pereira at UFC 320 in a five-round war. "
            "Here is the breakdown of the takedown that ended it, plus "
            "what it means for the heavyweight division next."
        )
        above, below = fold_preview(body)
        self.assertLessEqual(len(above), 110)
        self.assertTrue(below)
        self.assertIn(above, body)
        self.assertTrue(body.endswith(below) or below in body)

    def test_short_description_has_nothing_below_the_fold(self):
        from core.description_fold import fold_preview

        above, below = fold_preview("Short hook.")
        self.assertEqual(above, "Short hook.")
        self.assertEqual(below, "")

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("desc-fold", ops.COMMANDS)


class TestWeeklyOperatorDigest(unittest.TestCase):
    """#452. Three decisions this week, written to a file. next_actions
    already exist; the digest is the cap + vault write, not a new agent."""

    def test_digest_caps_at_three_decisions(self):
        from analytics.weekly_report import operator_digest

        report = {
            "ready": True,
            "channel_id": "tapin",
            "next_actions": [f"do thing {i}" for i in range(6)],
        }
        text = operator_digest(report)
        self.assertEqual(text.count("do thing"), 3)
        self.assertIn("do thing 0", text)
        self.assertNotIn("do thing 5", text)

    def test_not_ready_writes_nothing(self):
        from analytics.weekly_report import operator_digest, write_operator_digest

        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                self.assertEqual(operator_digest({"ready": False, "next_actions": ["x"]}), "")
                self.assertIsNone(write_operator_digest("tapin", {"ready": False}))

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("digest", ops.COMMANDS)


class TestSubscribersGainedReachBestBet(GovernorCase):
    """#362. youtube_metrics already parses subscribersGained. best-bet
    ranked on engaged-rate and never mentioned subs, so a video that
    converted subscribers looked identical to one that farmed views."""

    def test_winning_domain_rationale_names_subscriber_gain(self):
        from core.best_bet import get_best_bet

        entries = [
            {
                "topic": f"nba thing {i}",
                "engaged_rate": 0.11,
                "composite_score": 50,
                "domain": "nba",
                "subscribers_gained": 2,
                "age_days": 3.0,
            }
            for i in range(6)
        ]
        with (
            patch("core.best_bet._build_entries", return_value=entries),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bet = get_best_bet("tapin")
        self.assertIsNotNone(bet)
        assert bet is not None
        self.assertIn("12 subscriber", bet.rationale)

    def test_zero_subs_does_not_invent_a_conversion_line(self):
        from core.best_bet import get_best_bet

        entries = [
            {
                "topic": f"nba thing {i}",
                "engaged_rate": 0.11,
                "composite_score": 50,
                "domain": "nba",
                "subscribers_gained": 0,
                "age_days": 3.0,
            }
            for i in range(6)
        ]
        with (
            patch("core.best_bet._build_entries", return_value=entries),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bet = get_best_bet("tapin")
        self.assertIsNotNone(bet)
        assert bet is not None
        self.assertNotIn("subscriber", bet.rationale)


class TestTopicSaturationIndex(unittest.TestCase):
    """#364. Competitor snapshots already store recent_videos. Being the
    seventh channel to cover a story in 48h is a scoring input, not a
    number that dies on the helper."""

    def test_counts_matching_videos_inside_the_window(self):
        from analytics.competitor_context import topic_saturation

        now = datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)
        snap = {
            "competitors": [
                {
                    "label": "A",
                    "recent_videos": [
                        {
                            "title": "UFC 320 Jones vs Pereira recap",
                            "published_at": "2026-09-09T12:00:00+00:00",
                        },
                        {
                            "title": "UFC 320 weigh-ins",
                            "published_at": "2026-09-08T10:00:00+00:00",
                        },
                    ],
                },
                {
                    "label": "B",
                    "recent_videos": [
                        {
                            "title": "UFC 320 results",
                            "published_at": "2026-09-01T12:00:00+00:00",
                        },
                        {
                            "title": "GTA 6 leak",
                            "published_at": "2026-09-09T12:00:00+00:00",
                        },
                    ],
                },
            ]
        }
        count = topic_saturation("tapin", "UFC 320 Jones", snapshot=snap, now=now, window_hours=48)
        self.assertEqual(count, 2)

    def test_prompt_block_names_the_count(self):
        from analytics.competitor_context import get_competitor_prompt_block

        # The block reads the real clock, so the fixture must too. Pinned to
        # 2026-09-09 it went red three days later: the video aged past 48h.
        now = datetime.now(timezone.utc)
        snap = {
            "synced_at": now.isoformat(),
            "competitors": [
                {
                    "label": "A",
                    "recent_videos": [
                        {
                            "title": "UFC 320 Jones recap",
                            "published_at": now.isoformat(),
                        }
                    ],
                }
            ],
        }
        with patch(
            "analytics.competitor_context.load_competitor_snapshot",
            return_value=snap,
        ):
            block = get_competitor_prompt_block("tapin", "UFC 320 Jones")
        self.assertIn("1 competitor", block.lower())
        self.assertIn("48h", block)

    def test_dossier_prints_saturation_from_quality(self):
        from core.run_ledger import render_dossier
        from storage.repositories.content_runs import ContentRunRecord

        record = ContentRunRecord(
            id=81,
            channel_id="tapin",
            input_topic="UFC 320",
            selected_topic="UFC 320",
            status="completed",
            composite_score=1.0,
            quality_json=json.dumps({"topic_saturation": 7}),
        )
        with patch("storage.repositories.content_runs.get_content_run_repository") as repo:
            repo.return_value.get.return_value = record
            blob = render_dossier(81)
        self.assertIn("7 competitor", blob.lower())


class TestWikipediaLastRevisionTripwire(unittest.TestCase):
    """#336. Pageviews cannot tell 'the world moved after my cutoff'. A
    last-revision timestamp on the same article is the cheap tripwire
    the June UFC-250 failure lacked."""

    @patch("apis.wikipedia_pageviews_api.get_cached", return_value=None)
    @patch("apis.wikipedia_pageviews_api.set_cache")
    @patch("apis.wikipedia_pageviews_api._fetch_last_revision")
    @patch("apis.wikipedia_pageviews_api._fetch_pageviews")
    def test_signal_carries_last_revision(self, mock_views, mock_rev, _cache, _cached):
        mock_views.return_value = {
            "article": "UFC_250",
            "views": [100, 120, 130, 400, 500, 600, 620, 640],
        }
        mock_rev.return_value = "2026-09-09T12:00:00Z"
        from apis.wikipedia_pageviews_api import get_wikipedia_pageviews_signal

        sig = get_wikipedia_pageviews_signal("UFC 250")
        self.assertEqual((sig.get("data") or {}).get("last_revision"), "2026-09-09T12:00:00Z")
        self.assertIn("edited", (sig.get("status_detail") or "").lower())

    def test_health_block_prints_a_fresh_edit(self):
        from core.ui import display_signal_health

        now = datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)
        lines: list[str] = []

        def capture(*a, **_k):
            lines.append(a[0] if a else "")

        with patch("core.ui.SIGNAL_ORDER", ["wikipedia"]):
            display_signal_health(
                {
                    "wikipedia": {
                        "connected": True,
                        "active": True,
                        "status": "ok",
                        "data": {"last_revision": "2026-09-09T16:00:00Z", "article": "UFC_250"},
                    }
                },
                print_fn=capture,
                ask=False,
                now=now,
            )
        blob = "\n".join(lines).lower()
        self.assertIn("wikipedia", blob)
        self.assertIn("edited", blob)


class TestPublishDeadmanSwitch(unittest.TestCase):
    """#605. Nothing uploads if the operator has not been at the keyboard
    in N days. Opt-in, fail-closed when armed, like human-presence."""

    def test_stale_heartbeat_blocks_publish(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import YouTubePublisher

        req = PublishRequest(file_path=__file__, title="x", description="", tags=[])
        stale = datetime.now(timezone.utc) - timedelta(days=10)
        with (
            patch.dict(os.environ, {"PUBLISH_DEADMAN_DAYS": "7"}),
            patch(
                "core.human_presence.last_human_at",
                return_value=stale.timestamp(),
            ),
            patch(
                "publishing.youtube_publisher.YouTubePublisher.is_configured",
                return_value=True,
            ),
            patch("publishing.youtube_publisher.get_youtube_service") as svc,
        ):
            result = YouTubePublisher().publish(req, channel_id="tapin")
        self.assertEqual(result.status, "blocked")
        self.assertIn("dead", (result.detail or "").lower())
        svc.assert_not_called()

    def test_unset_env_does_not_block(self):
        from core.publish_deadman import deadman_block_reason

        with patch.dict(os.environ, {"PUBLISH_DEADMAN_DAYS": ""}, clear=False):
            os.environ.pop("PUBLISH_DEADMAN_DAYS", None)
            self.assertIsNone(deadman_block_reason(last_human_at=None))


class TestThumbnailConfirmAfterSet(unittest.TestCase):
    """#599. thumbnails.set returning 200 is not proof the custom thumb
    applied. A videos.list that still shows the default is a silent miss."""

    def test_set_without_a_custom_thumb_is_unverified(self):
        from youtube.thumbnails import set_video_thumbnail

        mock_service = MagicMock()
        mock_service.thumbnails.return_value.set.return_value.execute.return_value = {}
        mock_service.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "thumbnails": {"default": {"url": "https://i.ytimg.com/vi/x/default.jpg"}}
                    }
                }
            ]
        }
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            Path(path).write_bytes(b"fakejpeg")
            with (
                patch("youtube.thumbnails.has_quota_for_thumbnail", return_value=True),
                patch("youtube.thumbnails.record_thumbnail_usage"),
                patch("youtube.thumbnails.MediaFileUpload"),
            ):
                result = set_video_thumbnail(mock_service, "vid1", path)
        finally:
            os.unlink(path)
        self.assertEqual(result.status, "unverified")
        mock_service.videos.return_value.list.assert_called()

    def test_set_with_maxres_is_confirmed(self):
        from youtube.thumbnails import set_video_thumbnail

        mock_service = MagicMock()
        mock_service.thumbnails.return_value.set.return_value.execute.return_value = {}
        mock_service.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "thumbnails": {
                            "maxres": {"url": "https://i.ytimg.com/vi/vid1/maxresdefault.jpg"}
                        }
                    }
                }
            ]
        }
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            Path(path).write_bytes(b"fakejpeg")
            with (
                patch("youtube.thumbnails.has_quota_for_thumbnail", return_value=True),
                patch("youtube.thumbnails.record_thumbnail_usage"),
                patch("youtube.thumbnails.MediaFileUpload"),
            ):
                result = set_video_thumbnail(mock_service, "vid1", path)
        finally:
            os.unlink(path)
        self.assertEqual(result.status, "set")
        mock_service.videos.return_value.list.assert_called()


class TestPublishRollbackDryRun(unittest.TestCase):
    """#437. Unlist + correction description + dossier. Default is dry-run;
    the YouTube client is never constructed unless --apply and upload is on."""

    def test_plan_is_unlisted_with_correction_copy(self):
        from publishing.rollback import rollback_plan

        body = rollback_plan("abc123", correction="Source walked this back.")
        self.assertEqual(body["id"], "abc123")
        self.assertEqual(body["status"]["privacyStatus"], "unlisted")
        self.assertIn("walked this back", body["snippet"]["description"])

    def test_dry_run_never_builds_a_youtube_client(self):
        from publishing.rollback import apply_rollback

        with tempfile.TemporaryDirectory() as vault:
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault}):
                with patch("youtube.oauth.get_youtube_service") as svc:
                    result = apply_rollback(
                        "abc123",
                        correction="Source walked this back.",
                        channel_id="tapin",
                        dry_run=True,
                    )
            self.assertEqual(result.status, "dry_run")
            svc.assert_not_called()
            self.assertTrue(result.dossier_path, "dry-run still writes the dossier")
            notes = list(Path(vault).rglob("*.md"))
            self.assertTrue(notes, "dry-run still writes the dossier")

    def test_ops_verb_is_registered(self):
        from scripts import ops

        self.assertIn("rollback-publish", ops.COMMANDS)


class TestAutomaticCaptionPlacement(unittest.TestCase):
    """#713. A cue at default MarginV covers a bottom score bug. Detect
    the busy band and move the cue. No operator timeline."""

    def _png(self, dest: Path, *, busy_bottom: bool) -> Path:
        from PIL import Image

        img = Image.new("RGB", (64, 128), (12, 12, 12))
        pixels = img.load()
        y0, y1 = (96, 128) if busy_bottom else (0, 32)
        for y in range(y0, y1):
            for x in range(64):
                pixels[x, y] = ((x * 13 + y * 7) % 256, (x * 5) % 256, (y * 11) % 256)
        img.save(dest)
        return dest

    def test_busy_bottom_band_reads_as_a_spatial_step(self):
        # #721: a still cannot prove an overlay (no second frame), so the anchor
        # stays bottom for it; the spatial detector is what this fixture exercises.
        from video.caption_place import choose_caption_anchor, overlay_reading

        with tempfile.TemporaryDirectory() as tmp:
            path = self._png(Path(tmp) / "busy.png", busy_bottom=True)
            self.assertTrue(overlay_reading(str(path))["step"])
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                self.assertEqual(choose_caption_anchor(str(path)), "bottom")

    def test_quiet_bottom_stays_at_default_bottom(self):
        from video.caption_place import choose_caption_anchor

        with tempfile.TemporaryDirectory() as tmp:
            path = self._png(Path(tmp) / "quiet.png", busy_bottom=False)
            self.assertEqual(choose_caption_anchor(str(path)), "bottom")

    def test_karaoke_header_uses_top_alignment_when_asked(self):
        from video.caption_timing import build_ass_karaoke

        words = [{"word": "Hello", "start": 0.0, "end": 0.4}]
        bottom = build_ass_karaoke(words, max_words=2)
        top = build_ass_karaoke(words, max_words=2, anchor="top")
        self.assertIn(",2,80,80,260,1", bottom)
        self.assertIn(",8,80,80,260,1", top)
        self.assertNotIn(",8,80,80,260,1", bottom)

    def test_generate_subtitle_file_passes_the_anchor(self):
        from video.subtitles import generate_subtitle_file

        words = [{"word": "Hello", "start": 0.0, "end": 0.4}]
        with tempfile.TemporaryDirectory() as tmp:
            bg = self._png(Path(tmp) / "busy.png", busy_bottom=True)
            out = Path(tmp) / "captions.ass"
            with (
                patch("video.subtitles.caption_style", return_value="karaoke"),
                patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}),
                # #721: detector verdict fixed; this tests subtitles -> anchor wiring.
                patch("video.caption_place.bottom_band_overlay", return_value=True),
            ):
                path = generate_subtitle_file(
                    "Hello",
                    1.0,
                    words=words,
                    output_path=str(out),
                    background_path=str(bg),
                )
            text = Path(path).read_text(encoding="utf-8")
        self.assertIn(",8,80,80,260,1", text)


class TestRenderSmokeInCi(unittest.TestCase):
    """#415. #24/#26 shipped dead on Windows because CI never ran ffmpeg
    against the production subtitle filter. A 2s synthetic through
    build_render_ffmpeg_command is the gate."""

    def test_ci_installs_ffmpeg(self):
        text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        live = "\n".join(
            line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        self.assertIn("ffmpeg", live.lower())
        self.assertIn("apt-get", live)

    def test_missing_ffmpeg_under_ci_is_a_failure(self):
        from video.render_smoke import require_ffmpeg

        with patch.dict(os.environ, {"CI": "true"}), patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                require_ffmpeg()

    @unittest.skipUnless(FFMPEG, "ffmpeg is required for the 2s synthetic smoke")
    def test_production_command_encodes_a_two_second_file(self):
        from video.render_smoke import smoke_render_synthetic
        from video.render_video import _probe_video_duration

        with tempfile.TemporaryDirectory() as tmp:
            out = smoke_render_synthetic(tmp)
            self.assertTrue(out.is_file())
            duration = _probe_video_duration(str(out))
        self.assertIsNotNone(duration)
        assert duration is not None
        self.assertGreater(duration, 1.5)
        self.assertLess(duration, 3.5)


class TestUnreadablePageGuardStillHolds(unittest.TestCase):
    """#714. Tick leftover: d1776a0 already refuses to file a vanished
    claim on an empty body. This is the measurement that keeps the tick honest."""

    def test_empty_body_does_not_file(self):
        from tests.test_review6_defects import TestUnreadableSourceIsNotAVanishedClaim

        TestUnreadableSourceIsNotAVanishedClaim().test_an_empty_body_does_not_file_a_correction()


if __name__ == "__main__":
    unittest.main()
