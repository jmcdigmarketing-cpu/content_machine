"""#671 visual angles, Stage 3 review keys, #416 owned beat cuts.

Fail-then-fix: AskBridge has no choice list; J/K/L helper is missing; clip
index is not mapped onto scene-plan beats.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch


class TestAngleChoicesOnTheBridge(unittest.TestCase):
    def tearDown(self):
        from core.ask_bridge import set_current_bridge

        set_current_bridge(None)

    def test_display_variants_posts_titles_the_window_can_list(self):
        from core.ask_bridge import AskBridge, set_current_bridge
        from core.ui import display_variants

        bridge = AskBridge()
        set_current_bridge(bridge)
        evaluated = [
            ("GTA 6 leak looks real this time", 80.0, {}),
            ("Rockstar walked the June date back", 70.0, {}),
        ]
        display_variants(evaluated, print_fn=lambda *_a, **_k: None)
        titles = bridge.choices()
        self.assertEqual(titles[0], "GTA 6 leak looks real this time")
        self.assertEqual(titles[1], "Rockstar walked the June date back")

    def test_guard_without_set_choices_the_list_stays_empty(self):
        from core.ask_bridge import AskBridge, set_current_bridge
        from core.ui import display_variants

        bridge = AskBridge()
        set_current_bridge(bridge)
        saved = AskBridge.set_choices
        try:
            delattr(AskBridge, "set_choices")
            display_variants(
                [("GTA 6 leak looks real this time", 80.0, {})],
                print_fn=lambda *_a, **_k: None,
            )
            self.assertEqual(bridge.choices(), [])
        finally:
            AskBridge.set_choices = saved


class TestReviewKeyHelper(unittest.TestCase):
    def test_j_k_l_are_back_pause_forward(self):
        from core.review_keys import apply_review_key

        pos, paused = apply_review_key("j", position_ms=12_000, duration_ms=60_000, paused=False)
        self.assertEqual(pos, 7_000)
        self.assertFalse(paused)
        pos, paused = apply_review_key("k", position_ms=7_000, duration_ms=60_000, paused=False)
        self.assertTrue(paused)
        self.assertEqual(pos, 7_000)
        pos, paused = apply_review_key("l", position_ms=7_000, duration_ms=60_000, paused=True)
        self.assertEqual(pos, 12_000)
        self.assertTrue(paused)

    def test_approve_command_matches_the_booth(self):
        from core.review_keys import approve_command

        ctx = {"approve_cmd": "py -m scripts.ops requeue-upload --run-id 71"}
        self.assertEqual(approve_command(ctx), "py -m scripts.ops requeue-upload --run-id 71")
        self.assertIn("requeue-upload", approve_command({"run_id": 71}))


class TestOwnedBeatCuts(unittest.TestCase):
    def test_two_indexed_clips_cover_the_beats_without_stock(self):
        from core.owned_beats import assign_owned_clips
        from video.scene_plan import plan_scenes

        scenes = plan_scenes(
            "The leak dropped Friday night. Rockstar walked it back by morning.",
            "GTA 6 leak",
            10.0,
            max_scenes=2,
        )
        index = {
            "clips": {
                "C:/clips/gta/a.mp4": {
                    "duration_s": 8.0,
                    "hud": False,
                    "source": "gta",
                },
                "C:/clips/gta/b.mp4": {
                    "duration_s": 8.0,
                    "hud": False,
                    "source": "gta",
                },
            }
        }
        paths = assign_owned_clips(scenes, index, topic="GTA 6 leak")
        self.assertEqual(len(paths), len(scenes))
        self.assertTrue(all(p.endswith(".mp4") for p in paths))

    def test_empty_index_keeps_the_current_single_loop(self):
        from core.owned_beats import assign_owned_clips
        from video.scene_plan import plan_scenes

        scenes = plan_scenes("A short script about the leak.", "GTA 6 leak", 6.0)
        self.assertEqual(assign_owned_clips(scenes, {"clips": {}}, topic="GTA 6 leak"), [])

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

    def test_missing_files_keep_the_single_loop(self):
        from core.owned_beats import try_owned_beat_background

        index = {
            "clips": {
                "C:/clips/gta/missing.mp4": {
                    "duration_s": 12.0,
                    "hud": None,
                    "source": "gta",
                },
            }
        }
        with patch("core.owned_beats.load_clip_index", return_value=index):
            self.assertIsNone(
                try_owned_beat_background(
                    "GTA 6 leak",
                    "Gameplay only please.",
                    "tapin",
                    duration=6.0,
                )
            )

    def test_render_asks_owned_beats_before_stock_and_does_not_enable_scene_match(self):
        src = Path("video/render_video.py").read_text(encoding="utf-8")
        owned = src.find("try_owned_beat_background")
        stock = src.find("get_scene_matched_background")
        self.assertGreater(owned, 0)
        self.assertGreater(stock, owned)
        self.assertNotIn('os.environ["SCENE_MATCHED_BROLL"]', src)


class TestOpsReviewRoomRegistered(unittest.TestCase):
    def test_verb_is_in_the_live_registry(self):
        from scripts.ops import COMMANDS

        self.assertIn("review-room", COMMANDS)
        self.assertIn("booth", COMMANDS)


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None  # type: ignore[misc, assignment]


@unittest.skipUnless(QApplication is not None, "PySide6 extra not installed")
class TestStage3Widgets(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QApplication.instance() is None:
            QApplication([])

    def test_angle_list_shows_bridge_choices(self):
        from core.ask_bridge import AskBridge, AskRequest
        from desktop.window import RunWindow

        window = RunWindow()
        window._bridge.set_choices(["GTA 6 leak looks real this time", "Walked back"])
        window._show_request(
            AskRequest(prompt="  Choose 1-5 (Enter = best): ", kind="choice", gate="angles")
        )
        self.assertGreaterEqual(window.angle_list.count(), 2)
        self.assertIn("GTA 6 leak", window.angle_list.item(0).text())
        window.close()

    def test_review_window_uses_token_qss_and_empty_copy_without_mp4(self):
        from desktop.review import ReviewWindow

        window = ReviewWindow(context={"mp4": "", "grade": "n/a", "approve_cmd": "ops booth"})
        qss = window.styleSheet()
        self.assertTrue(qss.strip())
        self.assertIn("design_tokens.json", qss)
        self.assertIn("No last mp4", window.empty_label.text())
        window.close()

    def test_review_window_reads_gather_booth_keys(self):
        from desktop.review import ReviewWindow

        window = ReviewWindow(
            context={
                "mp4_path": "",
                "grade": "A (92)",
                "authenticity": "pass",
                "cost": "tts $0.00",
                "approve_cmd": "py -m scripts.ops requeue-upload --run-id 71",
                "channel_id": "tapin",
            }
        )
        self.assertIn("design_tokens.json", window.styleSheet())
        self.assertIn("No last mp4", window.empty_label.text())
        window.close()
