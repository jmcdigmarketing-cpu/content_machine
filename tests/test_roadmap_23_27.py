from __future__ import annotations

import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from config.channels import get_channel_profiles
from config.validate_channels import validate_channel
from video.render_video import build_render_ffmpeg_command


class Test23GeneratedEndCard(unittest.TestCase):
    def test_outro_binds_an_installed_font_instead_of_fontconfig_default(self):
        from video.channel_outro import build_outro_concat_command

        with patch("video.channel_outro._font_file", return_value=r"C:\Windows\Fonts\arialbd.ttf"):
            cmd = build_outro_concat_command(
                body_path="body.mp4",
                output_path="out.mp4",
                card={
                    "duration": 1.5,
                    "text": "TAP IN",
                    "bg": "#000000",
                    "fg": "#ffffff",
                },
            )
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn(r"fontfile='C\:/Windows/Fonts/arialbd.ttf'", graph)

    def test_shipped_channels_have_valid_end_cards(self):
        profiles = get_channel_profiles()
        for channel_id in ("tapin", "moneywise"):
            card = profiles[channel_id].end_card
            self.assertTrue(card["enabled"])
            self.assertGreater(card["duration"], 0)
            self.assertTrue(card["text"])

    def test_validation_rejects_bad_end_card(self):
        errors, _ = validate_channel(
            "bad",
            {
                "end_card": {
                    "enabled": True,
                    "duration": 0,
                    "text": "",
                    "bg": "black",
                    "fg": "#fff",
                }
            },
        )
        self.assertTrue(any("end_card.duration" in error for error in errors))
        self.assertTrue(any("end_card.text" in error for error in errors))
        self.assertTrue(any("end_card.bg" in error for error in errors))

    def test_outro_restores_body_when_ffmpeg_raises(self):
        from video.channel_outro import append_channel_outro

        with tempfile.TemporaryDirectory() as td:
            body = Path(td, "body.mp4")
            body.write_bytes(b"real-body")
            with (
                patch(
                    "video.channel_outro.resolve_end_card",
                    return_value={
                        "enabled": True,
                        "duration": 1.0,
                        "text": "Tap in",
                        "bg": "#000000",
                        "fg": "#ffffff",
                    },
                ),
                patch("video.encoder.subprocess.run", side_effect=OSError("ffmpeg missing")),
            ):
                with self.assertRaises(OSError):
                    append_channel_outro(str(body), channel_id="tapin")
            self.assertEqual(body.read_bytes(), b"real-body")

    def test_failed_outro_is_attempted_but_never_reported_successful(self):
        from video.channel_outro import append_channel_outro

        captured: list[str] = []
        with tempfile.TemporaryDirectory() as td:
            body = Path(td, "body.mp4")
            body.write_bytes(b"real-body")
            with (
                patch(
                    "video.channel_outro.resolve_end_card",
                    return_value={
                        "enabled": True,
                        "duration": 1.0,
                        "text": "Tap in",
                        "bg": "#000000",
                        "fg": "#ffffff",
                    },
                ),
                patch(
                    "video.encoder.subprocess.run",
                    return_value=SimpleNamespace(returncode=1, stderr="bad concat"),
                ),
            ):
                with self.assertRaises(RuntimeError):
                    append_channel_outro(
                        str(body),
                        channel_id="tapin",
                        command_callback=lambda kind, _argv: captured.append(kind),
                    )
        self.assertEqual(captured, ["outro_attempt"])

    def test_nonzero_and_empty_output_restore_body_and_remove_temp(self):
        from video.channel_outro import append_channel_outro

        for mode in ("nonzero", "empty"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                body = Path(td, "body.mp4")
                body.write_bytes(b"real-body")

                def fake_run(cmd, *, failure_mode=mode, **_kwargs):
                    if failure_mode == "empty":
                        Path(cmd[-1]).write_bytes(b"")
                        return SimpleNamespace(returncode=0, stderr="")
                    Path(cmd[-1]).write_bytes(b"partial")
                    return SimpleNamespace(returncode=1, stderr="failed")

                with (
                    patch(
                        "video.channel_outro.resolve_end_card",
                        return_value={
                            "enabled": True,
                            "duration": 1.0,
                            "text": "Tap in",
                            "bg": "#000000",
                            "fg": "#ffffff",
                        },
                    ),
                    patch("video.encoder.subprocess.run", side_effect=fake_run),
                ):
                    with self.assertRaises(RuntimeError):
                        append_channel_outro(str(body), channel_id="tapin")
                self.assertEqual(body.read_bytes(), b"real-body")
                self.assertFalse(Path(str(body) + ".body.outro.tmp.mp4").exists())


class Test24GroundedLowerThirds(unittest.TestCase):
    def test_selects_only_public_safe_grounded_labels(self):
        from video.lower_thirds import select_grounded_labels

        labels = select_grounded_labels(
            "Mateusz Gamrot faces Nova Strike. Rockstar Games responds.",
            "Verified: Mateusz Gamrot won. Rockstar Games published the update.",
            max_labels=2,
        )
        self.assertEqual(labels, ["Mateusz Gamrot", "Rockstar Games"])
        self.assertNotIn("Nova Strike", labels)

    def test_public_label_requires_the_exact_phrase_in_one_supplied_fact(self):
        from video.lower_thirds import select_grounded_labels

        labels = select_grounded_labels(
            "Rockstar Games responds.",
            "Rockstar announced a delay.\nThe Games report covers another company.",
        )
        self.assertEqual(labels, [])

    def test_ass_uses_real_word_timing_and_escapes_text(self):
        from video.lower_thirds import build_lower_thirds_ass

        words = [
            {"word": "Rockstar", "start": 1.25, "end": 1.7},
            {"word": "Games", "start": 1.7, "end": 2.1},
        ]
        ass = build_lower_thirds_ass(["Rockstar {Games}"], words)
        self.assertIn("0:00:01.25", ass)
        self.assertIn(r"Rockstar \(Games\)", ass)

    def test_missing_timings_preserves_render_command(self):
        base = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="voice.mp3",
            output_path="out.mp4",
            subtitle_path="captions.srt",
            duration=12,
        )
        with_labels_but_no_timing = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="voice.mp3",
            output_path="out.mp4",
            subtitle_path="captions.srt",
            duration=12,
            lower_thirds_path=None,
        )
        self.assertEqual(base, with_labels_but_no_timing)


class Test25ChannelColorGrade(unittest.TestCase):
    def test_shipped_grades_are_distinct(self):
        profiles = get_channel_profiles()
        self.assertNotEqual(profiles["tapin"].color_grade, profiles["moneywise"].color_grade)

    def test_grade_is_after_crop_before_captions(self):
        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="voice.mp3",
            output_path="out.mp4",
            subtitle_path="captions.srt",
            duration=12,
            color_grade={"saturation": 1.1, "contrast": 1.05, "brightness": 0.01},
        )
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertLess(graph.index("crop="), graph.index("eq="))
        self.assertLess(graph.index("eq="), graph.index("subtitles="))

    def test_identity_grade_is_byte_equivalent_to_absent_grade(self):
        kwargs = {
            "background_path": "bg.mp4",
            "mp3_path": "voice.mp3",
            "output_path": "out.mp4",
            "subtitle_path": "captions.srt",
            "duration": 12,
        }
        self.assertEqual(
            build_render_ffmpeg_command(**kwargs),
            build_render_ffmpeg_command(
                **kwargs,
                color_grade={"saturation": 1.0, "contrast": 1.0, "brightness": 0.0},
            ),
        )


class Test26HookMotion(unittest.TestCase):
    def test_motion_uses_first_real_caption_cue_only(self):
        from video.hook_motion import first_caption_motion_filter

        words = [
            {"word": "This", "start": 0.1, "end": 0.4},
            {"word": "lands.", "start": 0.4, "end": 0.9},
            {"word": "Later", "start": 1.1, "end": 1.4},
        ]
        filt = first_caption_motion_filter(words, {"enabled": True, "zoom": 1.08})
        self.assertIn("0.900", filt)
        self.assertIn("1.0800", filt)

    def test_no_timing_preserves_command(self):
        base = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="voice.mp3",
            output_path="out.mp4",
            subtitle_path="captions.srt",
            duration=12,
        )
        no_timing = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="voice.mp3",
            output_path="out.mp4",
            subtitle_path="captions.srt",
            duration=12,
            hook_motion_filter="",
        )
        self.assertEqual(base, no_timing)

    def test_motion_skips_non_cues_and_uses_first_real_timed_word(self):
        from video.hook_motion import first_caption_motion_filter

        words = [
            {"word": "", "start": None, "end": None},
            {"word": "Real", "start": 0.2, "end": 0.5},
            {"word": "cue.", "start": 0.5, "end": 0.8},
            {"word": "Later", "start": 1.0, "end": 1.2},
        ]
        filt = first_caption_motion_filter(words, {"enabled": True, "zoom": 1.08})
        self.assertIn("0.800", filt)


class Test27ThumbnailPick(unittest.TestCase):
    def test_dual_requires_active_format_experiment_or_override(self):
        from core.thumbnail_pick import dual_thumbnail_enabled

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("core.experiments.active_experiment", return_value={"lever": "hook_style"}),
        ):
            os.environ.pop("THUMBNAIL_DUAL", None)
            self.assertFalse(dual_thumbnail_enabled("tapin"))
        with patch.dict(os.environ, {"THUMBNAIL_DUAL": "true"}):
            self.assertTrue(dual_thumbnail_enabled("tapin"))

    def test_pick_validates_candidate_and_assigns_only_then(self):
        from core.thumbnail_pick import pick_thumbnail

        with tempfile.TemporaryDirectory() as td:
            chosen = Path(td, "face_forward.jpg")
            chosen.write_bytes(b"jpeg")
            features = {
                "thumbnail_candidates": [
                    {
                        "path": str(chosen),
                        "arm": "face_forward",
                        "provider": "pillow",
                        "features": {"layout": "subject-led"},
                    }
                ]
            }
            with (
                patch("core.run_features.load_features", return_value=features),
                patch("core.run_features.merge_features") as merge,
                patch("core.experiments.record_assignment") as assign,
                patch("storage.repositories.assets.get_asset_repository") as assets,
            ):
                assets.return_value.create.return_value = SimpleNamespace(id=1)
                result = pick_thumbnail(71, str(chosen), channel_id="tapin")
            self.assertEqual(result["arm"], "face_forward")
            assign.assert_called_once_with("tapin", 71, "thumbnail_format", "face_forward")
            merge.assert_called_once()
            assets.return_value.create.assert_called_once()

    def test_dual_unpicked_blocks_publish(self):
        from core.thumbnail_pick import ensure_thumbnail_ready

        with patch(
            "core.run_features.load_features",
            return_value={"thumbnail_candidates": [{"path": "a.jpg"}, {"path": "b.jpg"}]},
        ):
            with self.assertRaisesRegex(RuntimeError, "pick-thumbnail"):
                ensure_thumbnail_ready(71)

    def test_youtube_never_falls_back_to_newest_mtime(self):
        from youtube.thumbnails import resolve_thumbnail_path

        with tempfile.TemporaryDirectory() as td:
            newest = Path(td, "newest.jpg")
            newest.write_bytes(b"x")
            with patch("youtube.thumbnails.get_asset_repository") as repo:
                repo.return_value.list_for_run.return_value = []
                with patch("core.thumbnail_pick.ensure_thumbnail_ready", return_value=None):
                    self.assertIsNone(resolve_thumbnail_path(channel_id="tapin", content_run_id=71))

    def test_booth_renders_side_by_side_pick_controls(self):
        from core.review_booth import thumbnail_picker_html

        html = thumbnail_picker_html(
            71,
            [
                {"path": "a.jpg", "arm": "text_on"},
                {"path": "b.jpg", "arm": "face_forward"},
            ],
        )
        self.assertIn("text_on", html)
        self.assertIn("face_forward", html)
        self.assertIn("method='post'", html.lower())

    def test_booth_post_rejects_a_run_other_than_the_displayed_run(self):
        from core.review_booth import parse_thumbnail_pick_post

        with self.assertRaisesRegex(ValueError, "displayed run"):
            parse_thumbnail_pick_post(b"run_id=72&arm=text_on", expected_run_id=71)

    def test_served_booth_uses_http_routes_for_both_candidate_images(self):
        from core.review_booth import thumbnail_candidate_routes

        with tempfile.TemporaryDirectory() as td:
            first = Path(td, "first.jpg")
            second = Path(td, "second.png")
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            routes, hrefs = thumbnail_candidate_routes(
                [{"path": str(first)}, {"path": str(second)}]
            )
        self.assertEqual(hrefs, ["/thumbnail-candidate-0.jpg", "/thumbnail-candidate-1.png"])
        self.assertEqual(set(routes), set(hrefs))

    def test_dual_fallback_reports_pre_and_post_cost_evidence(self):
        from assets.flux_thumbnail import generate_dual_thumbnails

        paid_failure = SimpleNamespace(
            path=None,
            status="failed",
            detail="provider failed after request",
            provider="",
        )
        pillow_success = SimpleNamespace(
            path="fallback.jpg",
            status="generated",
            detail="Pillow",
            provider="pillow",
        )
        with (
            tempfile.TemporaryDirectory() as td,
            patch.dict(os.environ, {"IDEOGRAM_API_KEY": "configured"}, clear=False),
            patch("assets.flux_thumbnail._ideogram_thumbnail", return_value=paid_failure),
            patch("assets.flux_thumbnail._pillow_thumbnail", return_value=pillow_success),
            patch("assets.flux_thumbnail.is_flux_configured", return_value=False),
        ):
            candidates = generate_dual_thumbnails(
                "topic",
                "title",
                td,
                content_run_id=71,
                channel_id="tapin",
            )
        evidence = candidates[0]["cost"]
        self.assertIn("pre_fallback_usd", evidence)
        self.assertIn("post_fallback_usd", evidence)
        self.assertEqual(evidence["post_fallback_usd"], 0.0)

    def test_requeue_carries_the_picked_thumbnail_path(self):
        from scripts import requeue_upload

        run = SimpleNamespace(
            id=71,
            channel_id="tapin",
            mp4_path="video.mp4",
            title="Title",
            selected_topic="Topic",
            description="Description",
            tags_json="[]",
        )
        args = Namespace(
            channel="tapin",
            run_id=71,
            any_channel=False,
            queue=True,
            retry_failed_quota=False,
        )
        with (
            patch("scripts.requeue_upload.argparse.ArgumentParser.parse_args", return_value=args),
            patch("scripts.requeue_upload._lookup_run", return_value=(run, None)),
            patch("scripts.requeue_upload._resolve_mp4_path", return_value="video.mp4"),
            patch("scripts.requeue_upload._is_uploaded", return_value=False),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch("core.thumbnail_pick.ensure_thumbnail_ready", return_value="picked.jpg"),
            patch(
                "scripts.requeue_upload.enqueue_upload_job",
                return_value=SimpleNamespace(id=9),
            ) as enqueue,
        ):
            self.assertEqual(requeue_upload.main([]), 0)
        self.assertEqual(enqueue.call_args.kwargs["thumbnail_path"], "picked.jpg")


if __name__ == "__main__":
    unittest.main()
