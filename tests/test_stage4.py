"""Stage 4 next 15: review-room honesty, mechanical studio, cheap leftovers.

Fail-then-fix on HEAD 4a82992. Do not mock the unit under test.
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestReviewBindHonesty(unittest.TestCase):
    def test_drafted_run_75_does_not_pair_leftover_gta_mp4(self):
        from core.review_bind import bind_review_media

        with tempfile.TemporaryDirectory() as tmp:
            leftover = Path(tmp) / "gta_vi_trailer_leak_gameplay_20260815_204915.mp4"
            leftover.write_bytes(b"not-a-real-mp4")
            bound = bind_review_media(
                run_id=75,
                run_status="drafted",
                run_mp4="",
                leftover_mp4=str(leftover),
            )
        self.assertEqual(bound["mp4_path"], "")
        self.assertFalse(bound["can_approve"])
        self.assertIn("75", bound["refuse_reason"])
        self.assertIn("drafted", bound["refuse_reason"].lower())
        self.assertNotIn(str(leftover), bound["mp4_path"])

    def test_rendered_run_with_a_file_wins_over_a_leftover(self):
        from core.review_bind import bind_review_media

        with tempfile.TemporaryDirectory() as tmp:
            run_file = Path(tmp) / "run71.mp4"
            leftover = Path(tmp) / "gta_vi_trailer_leak_gameplay_20260815_204915.mp4"
            run_file.write_bytes(b"run")
            leftover.write_bytes(b"old")
            bound = bind_review_media(
                run_id=71,
                run_status="rendered",
                run_mp4=str(run_file),
                leftover_mp4=str(leftover),
            )
        self.assertEqual(os.path.abspath(bound["mp4_path"]), os.path.abspath(run_file))
        self.assertTrue(bound["can_approve"])
        self.assertEqual(bound["refuse_reason"], "")

    def test_published_run_with_a_file_can_queue_approve(self):
        from core.review_bind import queued_approve_command

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "run72.mp4"
            mp4.write_bytes(b"x")
            cmd = queued_approve_command(
                {
                    "run_id": 72,
                    "run_status": "published",
                    "mp4_path": str(mp4),
                    "can_approve": True,
                    "approve_cmd": "py -m scripts.ops requeue-upload --run-id 72",
                }
            )
        self.assertIsNotNone(cmd)
        self.assertIn("requeue-upload --run-id 72", cmd or "")

    def test_queued_approve_is_none_for_drafted_run_75(self):
        from core.review_bind import queued_approve_command

        ctx = {
            "run_id": 75,
            "run_status": "drafted",
            "mp4_path": "",
            "can_approve": False,
            "approve_cmd": "py -m scripts.ops requeue-upload --run-id 75",
        }
        self.assertIsNone(queued_approve_command(ctx))

    def test_gather_booth_context_refuses_leftover_with_drafted_75(self):
        from core.review_booth import gather_booth_context

        with tempfile.TemporaryDirectory() as tmp:
            leftover = Path(tmp) / "gta_vi_trailer_leak_gameplay_20260815_204915.mp4"
            leftover.write_bytes(b"not-a-real-mp4")
            record = SimpleNamespace(
                status="drafted",
                mp4_path="",
                title="",
                description="",
                timings_json="{}",
                mp3_path="",
            )
            repo = MagicMock()
            repo.get.return_value = record

            def fake_media(kind: str = "mp4", *, channel_id: str | None = None):
                del channel_id
                if str(kind).lower() in {"mp4", "video", "webm", "mov"}:
                    return str(leftover)
                return None

            with (
                patch("core.win_shell.last_media_file", side_effect=fake_media),
                patch(
                    "core.review_booth.last_reviewable_trace",
                    return_value={"run_id": 75, "status": "drafted", "quality": {}, "cost": {}},
                ),
                patch(
                    "storage.repositories.content_runs.get_content_run_repository",
                    return_value=repo,
                ),
            ):
                ctx = gather_booth_context("tapin")
        self.assertEqual(ctx["mp4_path"], "")
        self.assertFalse(ctx.get("can_approve"))
        self.assertIn("75", ctx.get("refuse_reason", ""))
        self.assertNotIn("requeue-upload --run-id 75", ctx.get("approve_cmd") or "")


class TestQssDropsCssFilter(unittest.TestCase):
    def test_build_qss_never_emits_filter(self):
        from core.chrome import build_qss, themed_css

        plain = build_qss("tapin")
        chroma = build_qss("tapin", reduced_chroma=True)
        self.assertNotIn("filter:", plain)
        self.assertNotIn("filter:", chroma)
        html = themed_css("tapin")
        self.assertIn("body.reduced-chroma", html)
        self.assertIn("filter: saturate(0.45)", html)


class TestReviewAutoplay(unittest.TestCase):
    def test_start_review_player_calls_play_when_the_file_exists(self):
        from core.review_player import start_review_player

        class FakePlayer:
            def __init__(self) -> None:
                self.source = None
                self.played = False

            def setSource(self, url) -> None:
                self.source = url

            def play(self) -> None:
                self.played = True

        player = FakePlayer()
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp) / "clip.mp4"
            mp4.write_bytes(b"x")
            self.assertTrue(start_review_player(player, str(mp4)))
        self.assertTrue(player.played)
        self.assertIsNotNone(player.source)

    def test_start_review_player_skips_missing_files(self):
        from core.review_player import start_review_player

        class FakePlayer:
            def __init__(self) -> None:
                self.played = False

            def play(self) -> None:
                self.played = True

        player = FakePlayer()
        self.assertFalse(start_review_player(player, "C:/missing/run75.mp4"))
        self.assertFalse(player.played)


class TestSaveCurrentFrame(unittest.TestCase):
    def test_png_source_is_copied_into_the_stills_folder(self):
        from PIL import Image

        from core.review_still import save_review_frame

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "frame.png"
            dest = Path(tmp) / "stills" / "review.png"
            Image.new("RGB", (16, 16), (10, 20, 30)).save(src)
            written = save_review_frame(str(src), str(dest), position_ms=0)
            self.assertTrue(os.path.isfile(written))
            with Image.open(written) as img:
                self.assertEqual(img.size, (16, 16))


class TestFrameStep(unittest.TestCase):
    def test_comma_and_period_move_one_frame_not_five_seconds(self):
        from core.review_keys import apply_review_key

        back, _paused = apply_review_key(
            ",",
            position_ms=1_000,
            duration_ms=60_000,
            paused=False,
            fps=30,
        )
        fwd, _paused = apply_review_key(
            ".",
            position_ms=1_000,
            duration_ms=60_000,
            paused=False,
            fps=30,
        )
        self.assertEqual(back, 1_000 - 33)
        self.assertEqual(fwd, 1_000 + 33)
        jump, _paused = apply_review_key(
            "l",
            position_ms=1_000,
            duration_ms=60_000,
            paused=False,
        )
        self.assertEqual(jump, 6_000)


class TestWhySlowIgnoresNonPhaseKeys(unittest.TestCase):
    def test_word_count_is_not_ranked_as_a_phase(self):
        from core.why_slow import why_slow_lines

        lines = why_slow_lines(
            {
                "word_count": 410.0,
                "script": 4.0,
                "tts": 1.2,
            }
        )
        blob = "\n".join(lines)
        self.assertNotIn("word_count", blob)
        self.assertIn("script", blob)
        self.assertIn("4.0s", blob)


class TestHudNoneIsProbedWhenTheFileExists(unittest.TestCase):
    def test_hud_none_on_a_real_hud_png_is_skipped(self):
        from PIL import Image

        from core.owned_beats import assign_owned_clips
        from video.scene_plan import plan_scenes

        scenes = plan_scenes("Gameplay only please.", "GTA 6 leak", 6.0, max_scenes=1)
        with tempfile.TemporaryDirectory() as tmp:
            hud = Path(tmp) / "hud.png"
            clean = Path(tmp) / "clean.png"
            img = Image.new("RGB", (64, 64), (20, 80, 20))
            for x in range(64):
                for y in range(8):
                    img.putpixel((x, y), (255, x * 4 % 256, 40))
            img.save(hud)
            Image.new("RGB", (64, 64), (20, 80, 20)).save(clean)
            index = {
                "clips": {
                    str(hud): {"duration_s": 12.0, "hud": None, "source": "gta"},
                    str(clean): {"duration_s": 12.0, "hud": None, "source": "gta"},
                }
            }
            paths = assign_owned_clips(scenes, index, topic="GTA 6 leak")
        self.assertEqual(paths, [str(clean)])

    def test_missing_hud_null_path_is_skipped(self):
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


class TestStartupBudget(unittest.TestCase):
    def test_measure_import_reports_the_clock_delta(self):
        from core.startup_budget import measure_import

        ticks = iter([10.0, 12.5])
        elapsed = measure_import(
            "does.not.matter",
            clock=lambda: next(ticks),
            importer=lambda _name: None,
        )
        self.assertAlmostEqual(elapsed, 2.5)

    def test_elapsed_over_budget_fails_the_ratchet(self):
        from core.startup_budget import elapsed_over_budget

        self.assertTrue(elapsed_over_budget(9.0, 0.5))
        self.assertFalse(elapsed_over_budget(0.01, 2.0))

    def test_core_chrome_fresh_import_stays_under_budget(self):
        from core.startup_budget import budget_for, measure_import_fresh

        elapsed = measure_import_fresh("core.chrome")
        self.assertLess(elapsed, budget_for("core.chrome"))
        self.assertGreaterEqual(elapsed, 0.0)


class TestEnvFingerprint(unittest.TestCase):
    def test_same_keys_different_values_hash_the_same_and_never_embed_secrets(self):
        from core.config_diff import env_canonical, env_fingerprint

        a = {"DEEPSEEK_API_KEY": "sk-secret-a", "OPENROUTER_API_KEY": "or-a"}
        b = {"DEEPSEEK_API_KEY": "sk-secret-b", "OPENROUTER_API_KEY": "or-b"}
        self.assertEqual(env_fingerprint(environ=a), env_fingerprint(environ=b))
        blob = env_canonical(environ=a)
        self.assertNotIn("sk-secret-a", blob)
        self.assertNotIn("or-a", blob)
        self.assertIn("DEEPSEEK_API_KEY=set", blob)

    def test_missing_versus_set_disagrees(self):
        from core.config_diff import env_fingerprint

        present = {"DEEPSEEK_API_KEY": "x"}
        empty = {"DEEPSEEK_API_KEY": ""}
        self.assertNotEqual(env_fingerprint(environ=present), env_fingerprint(environ=empty))


class TestSchemaRevisionOnLedger(unittest.TestCase):
    def test_persist_quality_stamps_alembic_head(self):
        from core.run_quality import persist_quality
        from storage.alembic_runner import current_revision

        repo = MagicMock()
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=repo,
        ):
            persist_quality(7, {"hook_score": 55})
        _run_id, data = repo.update.call_args[0]
        payload = json.loads(data["quality_json"])
        self.assertEqual(payload["hook_score"], 55)
        self.assertEqual(payload["schema_revision"], current_revision())

    def test_write_run_trace_stamps_schema_and_env_next_to_channels(self):
        from core import run_trace
        from storage.alembic_runner import current_revision

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(run_trace, "TRACES_DIR", tmp):
                path = run_trace.write_run_trace(
                    run_id=81,
                    channel_id="tapin",
                    input_topic="t",
                    selected_topic="t",
                    status="drafted",
                )
                self.assertIsNotNone(path)
                blob = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertTrue(blob.get("channels_sha256"))
        self.assertEqual(blob.get("schema_revision"), current_revision())
        self.assertTrue(blob.get("env_sha256"))
        self.assertNotIn("sk-", json.dumps(blob))


class TestDocsLintInPreCommit(unittest.TestCase):
    def test_pre_commit_calls_the_existing_command_ref_check(self):
        from core.ops_command_ref import check_command_ref

        yaml_text = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")
        self.assertIn("ops-command-ref", yaml_text)
        self.assertIn("check_command_ref", yaml_text)
        self.assertEqual(check_command_ref(), 0)


class TestStudioSlice(unittest.TestCase):
    def test_ops_studio_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("studio", COMMANDS)
        self.assertIn("review-room", COMMANDS)

    def test_desktop_mode_reads_studio_flag(self):
        from desktop.launch import desktop_mode

        self.assertEqual(desktop_mode(["--studio"]), "studio")
        self.assertEqual(desktop_mode(["--review"]), "review")
        self.assertEqual(desktop_mode([]), "run")

    def test_safe_title_grid_covers_the_bottom_chrome_band(self):
        from core.safe_title_grid import safe_title_rects

        rects = safe_title_rects(1080, 1920)
        chrome = rects["chrome"]
        self.assertEqual(chrome[1], int(1920 * 0.8))
        self.assertEqual(chrome[3], 1920)
        self.assertLess(rects["title_safe"][1], chrome[1])

    def test_studio_overlay_uses_inspect_thumbnail(self):
        from PIL import Image

        from core.studio_canvas import studio_overlay_for

        with tempfile.TemporaryDirectory() as tmp:
            thumb = Path(tmp) / "thumb.png"
            Image.new("RGB", (320, 180), (30, 30, 30)).save(thumb)
            overlay = studio_overlay_for(str(thumb))
        self.assertIn("bottom_quiet", overlay)
        self.assertIn("rects", overlay)
        self.assertIn("chrome", overlay["rects"])

    def test_caption_specimen_faces_come_from_shipped_tapin_skin(self):
        from core.font_specimen import specimen_faces, write_font_pick

        faces = specimen_faces("tapin")
        self.assertIn("Impact", faces)
        self.assertIn("Arial", faces)
        self.assertEqual(len(faces), 3)
        with tempfile.TemporaryDirectory() as tmp:
            note = Path(tmp) / "font_pick.txt"
            channels = Path(tmp) / "channels.json"
            channels.write_text("{}", encoding="utf-8")
            written = write_font_pick("Impact", str(note))
            self.assertTrue(os.path.isfile(written))
            self.assertIn("Impact", Path(written).read_text(encoding="utf-8"))
            self.assertEqual(channels.read_text(encoding="utf-8"), "{}")

    def test_waveform_under_the_player_is_drawn_from_existing_audio(self):
        from core.player_waveform import under_player_waveform

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "voice.wav"
            png = Path(tmp) / "wave.png"
            with wave.open(str(wav), "wb") as fh:
                fh.setnchannels(1)
                fh.setsampwidth(2)
                fh.setframerate(8000)
                fh.writeframes(struct.pack("<h", 1200) * 800)
            written = under_player_waveform(str(wav), str(png))
            self.assertTrue(os.path.isfile(written))
            self.assertGreater(os.path.getsize(written), 0)


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestReviewWindowHonesty(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def test_drafted_approve_does_not_popen_requeue(self):
        from desktop.review import ReviewWindow

        window = ReviewWindow(
            context={
                "mp4_path": "",
                "run_id": 75,
                "run_status": "drafted",
                "can_approve": False,
                "refuse_reason": "Run 75 has no MP4 on disk. Status: drafted",
                "approve_cmd": "py -m scripts.ops requeue-upload --run-id 75",
                "grade": "n/a",
                "channel_id": "tapin",
            }
        )
        self.assertFalse(window.approve_btn.isEnabled())
        self.assertIn("75", window.empty_label.text())
        with patch("desktop.review.subprocess.Popen") as popen:
            window._approve()
        popen.assert_not_called()
        window.close()


if __name__ == "__main__":
    unittest.main()
