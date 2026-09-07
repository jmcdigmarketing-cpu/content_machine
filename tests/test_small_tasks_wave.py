"""Behavioral coverage for the 2026-08-25 ten-small-task wave."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from config.channels import get_channel_profiles
from core import review_booth
from publishing.base import PublishRequest
from scripts import ops
from video.render_video import build_render_ffmpeg_command


class TestShippedMoneyWisePersona(unittest.TestCase):
    def test_shipped_moneywise_persona_reaches_human_context(self):
        from core.channel_persona import human_context_block

        get_channel_profiles.cache_clear()
        block = human_context_block("moneywise")
        self.assertIn("CHANNEL PERSONA", block)
        self.assertIn("Tone:", block)
        self.assertIn("Audience:", block)


class TestPromptVersionHash(unittest.TestCase):
    def test_prompt_source_change_changes_version(self):
        from core.content_engine import prompt_version_for_sources

        before = prompt_version_for_sources(["system prompt", "user prompt"])
        after = prompt_version_for_sources(["system prompt changed", "user prompt"])
        self.assertNotEqual(before, after)
        self.assertRegex(before, r"^content_engine_v7-[0-9a-f]{12}$")

    def test_generated_package_uses_live_prompt_hash(self):
        from core.content_engine import current_prompt_version

        first = current_prompt_version()
        second = current_prompt_version()
        self.assertEqual(first, second)
        self.assertRegex(first, r"^content_engine_v7-[0-9a-f]{12}$")

    def test_source_fallback_does_not_hash_runtime_addresses(self):
        from core import content_engine

        with patch.object(content_engine.inspect, "getsource", side_effect=OSError("no source")):
            version = content_engine.current_prompt_version()
            blob = content_engine._prompt_source_blob()
        self.assertRegex(version, r"^content_engine_v7-[0-9a-f]{12}$")
        self.assertNotIn("0x", blob)


class TestReviewBoothPublicSurface(unittest.TestCase):
    def test_title_description_duration_and_caption_track_are_visible(self):
        title = "A" * 101
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "video.mp4"
            mp4.write_bytes(b"placeholder")
            html = review_booth.booth_html(
                mp4_path=str(mp4),
                title=title,
                description="The first line viewers see.\nMore details.",
                duration_readout="Spoken 72.4s · estimated 68.2s",
                captions_href="booth.vtt",
            )
        self.assertIn("101 / 100", html)
        self.assertIn("over by 1", html)
        self.assertIn("The first line viewers see.", html)
        self.assertNotIn("More details.", html)
        self.assertIn("Spoken 72.4s", html)
        self.assertIn("<track kind='captions'", html)

    def test_existing_srt_is_converted_to_html5_vtt(self):
        with tempfile.TemporaryDirectory() as tmp:
            srt = Path(tmp) / "video.srt"
            vtt = Path(tmp) / "booth.vtt"
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,500\n<script>alert(1)</script> & accurate.\n",
                encoding="utf-8",
            )
            review_booth._srt_to_vtt(str(srt), str(vtt))
            text = vtt.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("WEBVTT"))
        self.assertIn("00:00:00.000 --> 00:00:01.500", text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; accurate.", text)
        self.assertNotIn("<script>", text)

    def test_public_metadata_and_caption_url_are_html_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "video.mp4"
            mp4.write_bytes(b"placeholder")
            html = review_booth.booth_html(
                mp4_path=str(mp4),
                title="<script>title</script>",
                description="<img src=x onerror=alert(1)>",
                captions_href="booth.vtt?' onerror='alert(1)",
            )
        self.assertNotIn("<script>title</script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("src='booth.vtt?' onerror=", html)
        self.assertIn("&lt;script&gt;title&lt;/script&gt;", html)

    def test_context_reads_real_stored_public_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "spoken.mp3"
            video = Path(tmp) / "rendered.mp4"
            audio.write_bytes(b"audio")
            video.write_bytes(b"video")
            record = SimpleNamespace(
                title="Stored title",
                description="Stored first line\nsecond",
                script_preview="one two three four",
                timings_json='{"word_count": 4}',
                mp3_path=str(audio),
            )
            with (
                patch.object(review_booth, "last_trace", return_value={"run_id": 9, "quality": {}}),
                patch(
                    "core.win_shell.last_media_file",
                    side_effect=lambda kind, **_kwargs: str(video) if kind == "mp4" else None,
                ),
                patch(
                    "storage.repositories.content_runs.get_content_run_repository"
                ) as repo_factory,
                patch(
                    "video.render_video._probe_video_duration",
                    side_effect=lambda path: 61.2 if path == str(audio) else 63.4,
                ) as probe,
            ):
                repo_factory.return_value.get.return_value = record
                ctx = review_booth.gather_booth_context("tapin")
        self.assertEqual(ctx["title"], "Stored title")
        self.assertEqual(ctx["description"], "Stored first line\nsecond")
        self.assertIn("Spoken 61.2s", ctx["duration_readout"])
        probe.assert_called_once_with(str(audio))


class TestThumbnailSafeArea(unittest.TestCase):
    def test_bottom_chrome_activity_is_flagged_and_reported(self):
        from core.thumbnail_safe_area import inspect_thumbnail, render_check

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "thumb.png"
            image = Image.new("RGB", (1280, 720), "navy")
            draw = ImageDraw.Draw(image)
            for x in range(0, 1280, 20):
                draw.rectangle((x, 620, x + 10, 719), fill="white")
            image.save(path)
            check = inspect_thumbnail(path)
        self.assertFalse(check.bottom_quiet)
        self.assertIn("bottom 20%", render_check(check))
        self.assertIn("HEURISTIC", render_check(check))
        self.assertNotIn("SAFE", render_check(check))

    def test_checker_is_wired_to_thumbnail_generation_path(self):
        from core import pipeline
        from core.thumbnail_safe_area import render_check

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.png"
            Image.new("RGB", (1280, 720), "navy").save(path)
            thumb = SimpleNamespace(path=str(path), provider="pillow", detail="generated")
            with (
                patch.dict(
                    os.environ,
                    {"CONTENT_RENDER_PROGRESS": "0", "THUMBNAIL_MODE": "auto"},
                    clear=False,
                ),
                patch.object(
                    pipeline,
                    "media_paths_for_topic",
                    return_value=("voice.mp3", "publish.mp4", "output/video/publish.mp4"),
                ),
                patch.object(pipeline, "generate_audio"),
                patch.object(
                    pipeline,
                    "render_vertical_video",
                    return_value=("output/video/publish.mp4", "background"),
                ),
                patch("assets.flux_thumbnail.generate_thumbnail", return_value=thumb),
                patch(
                    "core.output_paths.ensure_channel_output_dirs",
                    return_value={"thumbnails": tmp},
                ),
                patch("assets.flux_thumbnail.list_channel_thumbnails", return_value=[str(path)]),
                patch("assets.thumbnail_scorer.maybe_score_after_render", return_value=None),
                patch(
                    "core.thumbnail_safe_area.render_check",
                    wraps=render_check,
                ) as reported,
            ):
                _mp3, _mp4, thumb_path = pipeline.run_media_only(
                    "topic",
                    "short script",
                    channel_id="tapin",
                    content_run_id=None,
                )
        self.assertEqual(thumb_path, str(path))
        checked = reported.call_args.args[0]
        self.assertTrue(checked.bottom_quiet)
        rendered = render_check(checked)
        self.assertIn("QUIET", rendered)
        self.assertNotIn("SAFE", rendered)


class TestPerChannelCaptionSkin(unittest.TestCase):
    def test_shipped_skin_controls_real_ffmpeg_caption_filter(self):
        from video.render_video import render_vertical_video

        asset = MagicMock(path="C:/tmp/bg.mp4", provider="local", attribution="")
        rendered = MagicMock(returncode=0, stderr="")
        captured: list[str] = []
        with (
            patch("assets.manager.get_scene_matched_background", return_value=None),
            patch("video.render_video.get_background_asset", return_value=asset),
            patch("video.render_video.generate_subtitle_file", return_value="C:/tmp/subs.ass"),
            patch("video.render_video._probe_video_duration", return_value=60.0),
            patch("video.render_video._resolve_music_bed", return_value=None),
            patch("video.render_video._ffmpeg_run", return_value=rendered) as ffmpeg_run,
            patch("video.render_video._render_extra_formats", return_value=[]),
            patch("video.render_video.os.makedirs"),
            patch("video.render_video.is_render_progress_enabled", return_value=False),
            patch("video.channel_intro.resolve_intro_path", return_value=None),
        ):
            render_vertical_video(
                "C:/tmp/voice.mp3",
                "topic",
                "out.mp4",
                "script",
                channel_id="moneywise",
                command_callback=lambda _kind, argv: captured.extend(argv),
            )
        joined = " ".join(captured or ffmpeg_run.call_args.args[0])
        self.assertIn("force_style=", joined)
        self.assertIn("PrimaryColour=&H00A9E7F7&", joined)
        self.assertIn("BorderStyle=3", joined)


class TestDraftRenderPreset(unittest.TestCase):
    def test_draft_is_480p_ultrafast_publish_stays_1080p_fast(self):
        base = {
            "background_path": "bg.mp4",
            "mp3_path": "voice.mp3",
            "output_path": "out.mp4",
            "subtitle_path": "subs.srt",
            "duration": 10,
        }
        draft = " ".join(build_render_ffmpeg_command(**base, render_preset="draft"))
        publish = " ".join(build_render_ffmpeg_command(**base))
        self.assertIn("scale=480:854", draft)
        self.assertIn("-preset ultrafast", draft)
        self.assertIn("scale=1080:1920", publish)
        self.assertIn("-preset fast", publish)

    def test_draft_burns_safe_area_guides_publish_does_not(self):
        """#502. Guides are for review. A publish argv that carries them ships
        yellow boxes into YouTube.
        """
        base = {
            "background_path": "bg.mp4",
            "mp3_path": "voice.mp3",
            "output_path": "out.mp4",
            "subtitle_path": "subs.srt",
            "duration": 10,
        }
        draft = " ".join(build_render_ffmpeg_command(**base, render_preset="draft"))
        publish = " ".join(build_render_ffmpeg_command(**base))
        self.assertIn("drawbox", draft)
        self.assertNotIn("drawbox", publish)

    def test_real_preview_operator_command_is_registered(self):
        self.assertIn("render-preview", ops.COMMANDS)

    def test_draft_media_path_cannot_replace_publish_media(self):
        from core import pipeline

        with (
            patch.dict(
                os.environ,
                {"CONTENT_RENDER_PROGRESS": "0", "THUMBNAIL_MODE": "auto"},
                clear=False,
            ),
            patch.object(
                pipeline,
                "media_paths_for_topic",
                return_value=("voice.mp3", "publish.mp4", "output/video/publish.mp4"),
            ),
            patch.object(pipeline, "generate_audio"),
            patch.object(
                pipeline,
                "render_vertical_video",
                return_value=("output/video/publish_preview.mp4", "background"),
            ) as render,
            patch.object(pipeline, "update_content_run_media") as update,
            patch.object(pipeline, "record_render_assets") as record,
        ):
            _mp3, mp4, thumb = pipeline.run_media_only(
                "topic",
                "short script",
                channel_id="tapin",
                content_run_id=7,
                render_preset="draft",
            )
        self.assertTrue(mp4.endswith("publish_preview.mp4"))
        self.assertTrue(_mp3.endswith("voice_preview.mp3"))
        self.assertEqual(thumb, "")
        self.assertEqual(render.call_args.kwargs["render_preset"], "draft")
        self.assertEqual(render.call_args.args[0], "voice_preview.mp3")
        update.assert_not_called()
        record.assert_not_called()

    def test_preview_file_is_rejected_by_upload_boundary(self):
        from youtube.upload import upload_video

        with tempfile.TemporaryDirectory() as tmp:
            preview = Path(tmp) / "candidate_preview.mp4"
            preview.write_bytes(b"preview")
            result = upload_video(
                PublishRequest(
                    file_path=str(preview),
                    title="Preview",
                    description="Must not upload",
                ),
                channel_id="tapin",
            )
        self.assertEqual(result.status, "blocked")
        self.assertIn("preview", (result.detail or "").lower())


class TestDryRunArtifactRetention(unittest.TestCase):
    def test_retention_command_is_dry_run_only_even_with_apply_flag(self):
        self.assertIn("artifact-retention", ops.COMMANDS)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "drafts" / "old.mp4"
            victim.parent.mkdir()
            victim.write_bytes(b"x" * 20)
            args = SimpleNamespace(apply=True)
            with patch.dict(
                os.environ,
                {
                    "ARTIFACT_RETENTION_ROOT": str(root),
                    "OUTPUT_MAX_FILES": "0",
                    "ARTIFACT_RETENTION_DAYS": "0",
                },
                clear=False,
            ):
                code = ops.COMMANDS["artifact-retention"][1](args)
            self.assertEqual(code, 0)
            self.assertTrue(victim.exists())


if __name__ == "__main__":
    unittest.main()
