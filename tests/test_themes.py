"""Tests for the terminal theme registry (core/themes.py) and themed UI helpers."""

import unittest
from unittest.mock import patch

from core import themes


class TestRegistry(unittest.TestCase):
    def test_all_six_skins_plus_default_and_plain(self):
        for name in ("default", "plain", "onepiece", "zelda", "pokemon", "dbz", "jjba"):
            self.assertIn(name, themes.THEMES)

    def test_every_theme_has_frames_and_meter_chars(self):
        for theme in themes.THEMES.values():
            self.assertTrue(theme.spinner_frames)
            self.assertEqual(len(theme.meter_chars), 2)

    def test_celebration_keys_exist_in_bonus_art(self):
        from core.ui import _BONUS_ART

        for theme in themes.THEMES.values():
            if theme.celebration_key:
                self.assertIn(theme.celebration_key, _BONUS_ART, theme.name)


class TestResolution(unittest.TestCase):
    def tearDown(self):
        themes._channel_theme = ""

    def test_defaults_to_default_theme(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": ""}):
            self.assertEqual(themes.active_theme().name, "default")

    def test_env_override(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "jjba"}):
            self.assertEqual(themes.active_theme().name, "jjba")

    def test_unknown_env_falls_back(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "narnia"}):
            self.assertEqual(themes.active_theme().name, "default")

    def test_channel_theme_used_when_env_unset(self):
        class _P:
            ui_theme = "zelda"

        with patch("config.channels.get_channel_profile", return_value=_P()):
            themes.set_channel_theme("tapin")
        with patch.dict("os.environ", {"CONTENT_UI_THEME": ""}):
            self.assertEqual(themes.active_theme().name, "zelda")

    def test_env_beats_channel_theme(self):
        class _P:
            ui_theme = "zelda"

        with patch("config.channels.get_channel_profile", return_value=_P()):
            themes.set_channel_theme("tapin")
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz"}):
            self.assertEqual(themes.active_theme().name, "dbz")


class TestColorDepth(unittest.TestCase):
    def test_forced_16(self):
        with patch.dict("os.environ", {"CONTENT_UI_COLOR_DEPTH": "16", "WT_SESSION": "x"}):
            self.assertEqual(themes.color_depth(), 16)

    def test_windows_terminal_detected_as_256(self):
        with patch.dict(
            "os.environ", {"CONTENT_UI_COLOR_DEPTH": "auto", "WT_SESSION": "abc"}, clear=False
        ):
            self.assertEqual(themes.color_depth(), 256)

    def test_role_color_switches_with_depth(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz", "CONTENT_UI_COLOR_DEPTH": "256"}):
            self.assertIn("38;5;", themes.role_color("primary"))
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz", "CONTENT_UI_COLOR_DEPTH": "16"}):
            self.assertNotIn("38;5;", themes.role_color("primary"))

    def test_plain_theme_has_no_role_colors(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "plain"}):
            self.assertEqual(themes.role_color("primary"), "")


class TestMeter(unittest.TestCase):
    def test_meter_renders_filled_and_empty(self):
        with (
            patch.dict("os.environ", {"CONTENT_UI_THEME": "default"}),
            patch.object(themes, "_unicode_ok", return_value=True),
        ):
            out = themes.meter(3, 10, width=10)
        self.assertIn("3/10", out)
        self.assertEqual(out.count("▓"), 3)
        self.assertEqual(out.count("░"), 7)

    def test_meter_clamps_overflow(self):
        with (
            patch.dict("os.environ", {"CONTENT_UI_THEME": "default"}),
            patch.object(themes, "_unicode_ok", return_value=True),
        ):
            out = themes.meter(15, 10, width=10)
        self.assertEqual(out.count("▓"), 10)

    def test_meter_zero_cap_degrades(self):
        self.assertEqual(themes.meter(2, 0), "2/0")

    def test_meter_ascii_fallback_on_cp1252(self):
        with (
            patch.dict("os.environ", {"CONTENT_UI_THEME": "zelda"}),
            patch.object(themes, "_unicode_ok", return_value=False),
        ):
            out = themes.meter(2, 5, width=5)
        self.assertIn("#", out)
        self.assertNotIn("❤", out)

    def test_zelda_hearts(self):
        with (
            patch.dict("os.environ", {"CONTENT_UI_THEME": "zelda"}),
            patch.object(themes, "_unicode_ok", return_value=True),
        ):
            out = themes.meter(2, 5, width=5)
        self.assertIn("❤", out)
        self.assertIn("♡", out)


class TestThemedPhase(unittest.TestCase):
    def test_phase_translated(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz"}):
            self.assertEqual(themes.themed_phase("Fetching signals"), "Scouter scanning")

    def test_unknown_phase_passthrough(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz"}):
            self.assertEqual(themes.themed_phase("Custom step"), "Custom step")

    def test_default_theme_no_translation(self):
        with patch.dict("os.environ", {"CONTENT_UI_THEME": "default"}):
            self.assertEqual(themes.themed_phase("Fetching signals"), "Fetching signals")


class TestScoreHype(unittest.TestCase):
    def test_over_9000_line_on_high_score(self):
        from core.ui_theme import score_badge

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz"}):
            badge = score_badge(95)
        self.assertIn("OVER 9000", badge)

    def test_no_hype_below_threshold(self):
        from core.ui_theme import score_badge

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "dbz"}):
            badge = score_badge(72)
        self.assertNotIn("OVER 9000", badge)


class TestSpinnerTheming(unittest.TestCase):
    def test_spinner_picks_theme_frames(self):
        from core.ui import DiscoverySpinner

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "pokemon"}):
            spinner = DiscoverySpinner("Test")
        self.assertEqual(spinner._frames, list(themes.THEMES["pokemon"].spinner_frames))

    def test_spinner_reports_themed_stage(self):
        from core.ui import DiscoverySpinner

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "jjba"}):
            spinner = DiscoverySpinner("Test")
            spinner.report("Scoring variants", 2, 5)
            self.assertEqual(spinner._current_stage(0.0), "ORA ORA scoring variants 2/5")


class TestSectionGlyph(unittest.TestCase):
    def test_zelda_discovery_glyph(self):
        from core.ascii_art import section_glyph

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "zelda", "CONTENT_UI_ASCII": "true"}):
            self.assertIn("▲", section_glyph("Discovery"))

    def test_plain_theme_no_glyph(self):
        from core.ascii_art import section_glyph

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "plain", "CONTENT_UI_ASCII": "true"}):
            self.assertEqual(section_glyph("Discovery"), "")


class TestMascotPanel(unittest.TestCase):
    def test_themed_inline_mascot_used(self):
        from core.ascii_art import _theme_mascot_lines

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "jjba"}):
            lines = _theme_mascot_lines()
        self.assertTrue(any("ゴ" in ln for ln in lines))

    def test_plain_theme_no_mascot(self):
        from core.ascii_art import _theme_mascot_lines

        with patch.dict("os.environ", {"CONTENT_UI_THEME": "plain"}):
            self.assertEqual(_theme_mascot_lines(), ())


class TestMilestone(unittest.TestCase):
    def _repo_with(self, count: int):
        class _Repo:
            def list_uploaded_for_channel(self, _cid):
                return [object()] * count

        return _Repo()

    def test_milestone_printed_at_threshold(self):
        out = []
        from core import ui

        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=self._repo_with(10),
        ):
            ui.maybe_print_milestone("tapin", print_fn=out.append)
        self.assertTrue(any("#10" in ln for ln in out))

    def test_no_milestone_between_thresholds(self):
        out = []
        from core import ui

        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=self._repo_with(7),
        ):
            ui.maybe_print_milestone("tapin", print_fn=out.append)
        self.assertEqual(out, [])

    def test_fail_open_on_storage_error(self):
        out = []
        from core import ui

        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            side_effect=RuntimeError,
        ):
            ui.maybe_print_milestone("tapin", print_fn=out.append)
        self.assertEqual(out, [])


class TestDailyBriefBatch(unittest.TestCase):
    def test_daily_brief_registered_with_expected_steps(self):
        from scripts import ops

        self.assertIn("daily-brief", ops.COMMANDS)
        with patch.object(ops, "_run_batch", return_value=0) as run:
            ops.COMMANDS["daily-brief"][1](object())
        run.assert_called_once()
        steps = run.call_args[0][0]
        self.assertEqual(steps, ["daily-sync", "coach", "health", "reliability", "status"])


if __name__ == "__main__":
    unittest.main()
