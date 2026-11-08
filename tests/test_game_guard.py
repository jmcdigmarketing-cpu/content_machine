"""#2025 (the operator, 2026-11-08: "I am experiencing lag in games ... certain it isnt connection"):
the overnight run caught up at 10:16 AM, while a game was being played, and would have rendered up
to three videos; the fast lane and the 1 PM step render too. Background work waits while a game
runs, and a render runs below normal priority."""

from __future__ import annotations

import os
import subprocess
import unittest
from unittest.mock import patch

STEAM_GAME = (
    "GTA5_Enhanced.exe",
    r"D:\SteamLibrary\steamapps\common\Grand Theft Auto V\GTA5_Enhanced.exe",
)
LAUNCHER = (
    "EpicGamesLauncher.exe",
    r"C:\Program Files\Epic Games\Launcher\Portal\EpicGamesLauncher.exe",
)
WALLPAPER = ("wallpaper64.exe", r"C:\Steam\steamapps\common\wallpaper_engine\wallpaper64.exe")
EDITOR = ("Code.exe", r"C:\Program Files\Microsoft VS Code\Code.exe")


class GameRunningTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, {"GAME_GUARD": "true", "GAME_PROCESSES": "", "GAME_IGNORE": ""})
        p.start()
        self.addCleanup(p.stop)

    def test_a_game_from_a_library_folder_is_seen(self):
        from jobs.game_guard import game_running

        self.assertIn("GTA5_Enhanced.exe", game_running(processes=[EDITOR, STEAM_GAME], state=1))

    def test_modded_minecraft_is_seen(self):
        from jobs.game_guard import game_running

        java = ("javaw.exe", r"C:\Users\me\curseforge\minecraft\Install\runtime\java-runtime-gamma"
                             r"\windows-x64\java-runtime-gamma\bin\javaw.exe")  # fmt: skip
        self.assertIn("javaw.exe", game_running(processes=[java], state=1))
        other_java = ("javaw.exe", r"C:\Program Files\Java\jdk-21\bin\javaw.exe")
        self.assertEqual(game_running(processes=[other_java], state=1), "")

    def test_a_launcher_an_always_on_wallpaper_and_an_editor_are_not_games(self):
        from jobs.game_guard import game_running

        self.assertEqual(game_running(processes=[LAUNCHER, WALLPAPER, EDITOR], state=1), "")

    def test_a_known_game_name_anywhere_is_seen(self):
        from jobs.game_guard import game_running

        cod = ("cod.exe", r"C:\Program Files (x86)\Call of Duty\_retail_\cod.exe")
        self.assertIn("cod.exe", game_running(processes=[cod], state=1))
        with patch.dict(os.environ, {"GAME_PROCESSES": "MyIndieGame.exe"}):
            self.assertIn(
                "MyIndieGame.exe", game_running(processes=[("MyIndieGame.exe", "")], state=1)
            )
        with patch.dict(os.environ, {"GAME_IGNORE": "cod.exe"}):
            self.assertEqual(game_running(processes=[cod], state=1), "")

    def test_a_full_screen_app_counts(self):
        from jobs.game_guard import game_running

        self.assertIn("full-screen", game_running(processes=[EDITOR], state=3))  # D3D full screen
        self.assertIn("full-screen", game_running(processes=[EDITOR], state=2))  # busy full screen
        self.assertEqual(game_running(processes=[EDITOR], state=5), "")  # accepts notifications

    def test_off_with_the_switch_and_in_the_suite(self):
        from jobs.game_guard import game_running

        with patch.dict(os.environ, {"GAME_GUARD": "false"}):
            self.assertEqual(game_running(processes=[STEAM_GAME], state=3), "")


class WaitWhileGamingTests(unittest.TestCase):
    def test_it_waits_for_the_game_to_close(self):
        from jobs.game_guard import wait_while_gaming

        seen = iter(["GTA5_Enhanced.exe is running", "GTA5_Enhanced.exe is running", ""])
        slept: list[float] = []
        clock = iter(range(0, 10_000, 300))
        got = wait_while_gaming("overnight", check=lambda: next(seen), sleep=slept.append,
                                clock=lambda: next(clock), max_hours=6)  # fmt: skip
        self.assertEqual(got, "")
        self.assertEqual(len(slept), 2)

    def test_it_gives_up_after_its_hours_and_says_why(self):
        from jobs.game_guard import wait_while_gaming

        clock = iter(range(0, 100_000, 3600))
        got = wait_while_gaming("overnight", check=lambda: "cod.exe is running",
                                sleep=lambda _s: None, clock=lambda: next(clock), max_hours=6)  # fmt: skip
        self.assertEqual(got, "cod.exe is running")


class GatesTests(unittest.TestCase):
    def test_the_fast_lane_and_the_1_pm_step_wait_for_a_game(self):
        from datetime import datetime, timezone

        import jobs.fast_lane as fast_lane
        import jobs.midday as midday

        now = datetime(2026, 11, 8, 18, 30, tzinfo=timezone.utc)  # 1:30 PM EST
        with (
            patch.object(fast_lane, "units_left", return_value=9000),
            patch.object(fast_lane, "on_battery", return_value=False),
            patch.object(fast_lane, "overnight_running", return_value=False),
            patch("core.spaced_queue.day_full", return_value=""),
            patch("jobs.game_guard.game_running", return_value="cod.exe is running"),
            patch.dict(os.environ, {"FAST_LANE": "true", "MIDDAY": "true"}),
        ):
            self.assertEqual(fast_lane.blocked("tapin", now=now, store={}),
                             "a game is running (cod.exe is running)")  # fmt: skip
            self.assertEqual(midday.blocked("tapin", now=now, store={}),
                             "a game is running (cod.exe is running)")  # fmt: skip

    def test_overnight_waits_and_gives_up_without_drafting(self):
        import core.overnight as overnight

        with (
            patch("core.overnight_pause.is_paused", return_value=False),
            patch("jobs.game_guard.wait_while_gaming", return_value="cod.exe is running") as wait,
            patch.object(overnight, "_run_overnight_body") as body,
            patch.object(overnight, "_sign_in_line", return_value=""),
        ):
            result = overnight.run_overnight("tapin")
        body.assert_not_called()
        wait.assert_called_once()
        self.assertIn("a game ran", result.pause_line)

    def test_a_render_runs_below_normal_priority(self):
        import video.render_video as render_video

        ok = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(render_video.subprocess, "run", return_value=ok) as run:
            render_video._ffmpeg_run(["ffmpeg", "-i", "a.mp4", "o.mp4"], duration_sec=10.0)
        self.assertEqual(run.call_args.kwargs["creationflags"],
                         getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))  # fmt: skip


if __name__ == "__main__":
    unittest.main()
