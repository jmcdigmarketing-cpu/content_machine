"""The grand audit of 2026-10-17 - what it found that a test can hold.

- #1247: a bare `python -m unittest` from the repo root walks the packages in name order;
  `publishing/__init__` and `storage/__init__` import `config.settings` - which loads `.env` and
  freezes `Settings.database_url` - before `tests/__init__.py` can blank it. On 2026-10-16 that
  ran the suite against the operator's Postgres: 133 fake upload rows, and real job 59 marked
  failed.
- Decision 60 (the operator: "keep overnight renders waiting for me"): an overnight render is
  queued unlisted with no publish time, and only an operator's action makes a video public.
- Decision 61 (the operator: keep the current look): `bef5a56` (#497) swapped TapIn's grade -
  saturation 1.18, contrast 1.08, brightness 0.01, on every published video - for a near-flat
  2-point colour file.
- #532: Home's changelog stamped "last launch" on every fill, so Refresh emptied it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from config.paths import ROOT_DIR

_SENTINEL = "postgresql://sentinel.invalid/content_os"


def _child(code: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("CONTENT_SUITE", None)
    env["DATABASE_URL"] = _SENTINEL  # what the operator's .env sets
    env["CONTENT_SKIP_DOTENV"] = "1"  # the real .env is never read here
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


# ---- #1247: the suite never reaches the real database ---------------------------------------


class SuiteGuardTests(unittest.TestCase):
    def test_settings_loaded_first_and_the_suite_refuses_to_load(self):
        # What discovery from the repo root does: `storage` sorts before `tests`.
        out = _child("import storage, tests")
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertIn("discover -s tests -t .", out.stderr)

    def test_the_right_way_still_blanks_the_url(self):
        out = _child("import tests, config.settings as s; print(repr(s.Settings.database_url))")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "''")


class DatabaseRefusalTests(unittest.TestCase):
    def test_a_network_database_is_refused_while_the_suite_runs(self):
        from storage.db import suite_database_refusal

        self.assertTrue(suite_database_refusal(_SENTINEL, {"CONTENT_SUITE": "1"}))

    def test_the_ci_test_database_and_a_temp_sqlite_file_are_not(self):
        from storage.db import suite_database_refusal

        ci = "postgresql://postgres:test@localhost:5432/content_machine_test"
        environ = {"CONTENT_SUITE": "1", "CONTENT_TEST_DATABASE_URL": ci}
        self.assertEqual(suite_database_refusal(ci, environ), "")
        self.assertEqual(suite_database_refusal("sqlite:///C:/tmp/x.db", environ), "")

    def test_outside_the_suite_nothing_is_refused(self):
        from storage.db import suite_database_refusal

        self.assertEqual(suite_database_refusal(_SENTINEL, {}), "")

    def test_the_suite_marks_itself(self):
        self.assertEqual(os.environ.get("CONTENT_SUITE"), "1")

    def test_a_frozen_real_url_is_not_configured(self):
        from config.settings import Settings
        from storage import db

        with patch.object(Settings, "database_url", _SENTINEL):
            self.assertFalse(db.is_database_configured())
            db.get_engine.cache_clear()
            with patch("storage.db.create_engine") as engine:
                with self.assertRaises(RuntimeError):
                    db.get_engine()
            engine.assert_not_called()
        db.get_engine.cache_clear()


# ---- decision 60: overnight renders wait for the operator -------------------------------------


class OvernightWaitsTests(unittest.TestCase):
    def test_an_overnight_render_is_queued_unlisted_with_no_publish_time(self):
        from core import batch_review

        with patch("analytics.queue_manager.requeue_content_run", return_value=60) as requeue:
            batch_review._queue_unlisted(157, "tapin")
        kwargs = requeue.call_args.kwargs
        self.assertEqual(kwargs.get("privacy_status"), "unlisted")
        self.assertIsNone(kwargs.get("youtube_publish_at"))

    def test_only_an_operator_action_makes_a_video_public(self):
        allowed = {
            "scripts/ops.py",  # `ops go-public`
            "publishing/go_public.py",  # its own module; `watch_and_publish` asks first
            "core/review_bind.py",  # #1064: the app's Go public button, once claims are settled
        }
        callers = set()
        for folder in ("analytics", "apis", "assets", "config", "core", "desktop", "jobs",
                       "publishing", "scripts", "sports", "storage", "video", "youtube"):  # fmt: skip
            for path in Path(ROOT_DIR, folder).rglob("*.py"):
                if "apply_go_public(" in path.read_text(encoding="utf-8", errors="replace"):
                    callers.add(path.relative_to(ROOT_DIR).as_posix())
        self.assertLessEqual(callers, allowed | {p for p in callers if p.startswith("desktop/")})


# ---- decision 61: TapIn keeps its look --------------------------------------------------------


class ColourTests(unittest.TestCase):
    def test_tapin_renders_with_its_grade_not_the_flat_file(self):
        from video.render_video import (
            _resolve_color_grade,
            _resolve_color_lut,
            build_render_ffmpeg_command,
        )

        self.assertIsNone(_resolve_color_lut("tapin"))
        grade = _resolve_color_grade("tapin")
        self.assertEqual(grade, {"saturation": 1.18, "contrast": 1.08, "brightness": 0.01})
        cmd = build_render_ffmpeg_command(background_path="bg.mp4", mp3_path="voice.mp3",
                                          output_path="out.mp4", subtitle_path="captions.srt",
                                          duration=12.5, color_grade=grade)  # fmt: skip
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("eq=saturation=1.1800:contrast=1.0800:brightness=0.0100", graph)
        self.assertNotIn("lut3d=", graph)

    def test_moneywise_keeps_its_grade_too(self):
        from video.render_video import _resolve_color_lut

        self.assertIsNone(_resolve_color_lut("moneywise"))


# ---- #532: the changelog survives a Refresh ---------------------------------------------------


class ChangelogTests(unittest.TestCase):
    def test_a_refresh_shows_the_same_changes(self):
        from desktop import home

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "launch_state.json"
            state.write_text(json.dumps({"tapin": {"last_launch": "2026-10-16T00:00:00+00:00"}}))
            git = MagicMock(return_value=SimpleNamespace(returncode=0, stdout="One\nTwo\n"))
            with patch.object(home, "_LAUNCH_SEEN", {}), patch("subprocess.run", git):
                first = home.changelog_since_last_launch("tapin", state_path=state)
                second = home.changelog_since_last_launch("tapin", state_path=state)
        self.assertEqual(first, ["One", "Two"])
        self.assertEqual(second, first)
        git.assert_called_once()

    def test_git_opens_no_console_window_on_windows(self):
        from desktop import home

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "launch_state.json"
            state.write_text(json.dumps({"tapin": {"last_launch": "2026-10-16T00:00:00+00:00"}}))
            git = MagicMock(return_value=SimpleNamespace(returncode=0, stdout=""))
            with patch.object(home, "_LAUNCH_SEEN", {}), patch("subprocess.run", git):
                home.changelog_since_last_launch("tapin", state_path=state)
        flags = git.call_args.kwargs.get("creationflags", 0)
        self.assertEqual(flags, getattr(subprocess, "CREATE_NO_WINDOW", 0))


if __name__ == "__main__":
    unittest.main()
