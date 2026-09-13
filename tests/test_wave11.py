"""Wave 11: #631, #729, #636, #639 (and #727 if its measurement allows).

Every test here was observed failing on unmodified 608636d for the reason named in
its docstring. Two things only CI can fail -- a real Qt import on the runner and
the coverage step's output -- are simulated locally and proven in CI after push.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

CI_YML = Path(".github/workflows/ci.yml")


def _live_ci() -> str:
    """ci.yml without comment lines, so a commented-out step cannot pass a guard."""
    text = CI_YML.read_text(encoding="utf-8")
    return "\n".join(
        line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    )


def _step_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("- name:") and current:
            blocks.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


class TestCoreCoverageIsReportedInCI(unittest.TestCase):
    """#631. `coverage` sat in `[dev]` and nothing ran it, so which gates in `core/`
    no test executes was only ever found by hand."""

    def test_the_suite_runs_under_coverage(self):
        self.assertIn("coverage run -m unittest discover -s tests -t .", _live_ci())

    def test_the_core_report_is_report_only(self):
        blocks = [b for b in _step_blocks(_live_ci()) if "coverage report" in b]
        self.assertEqual(len(blocks), 1, "expected exactly one coverage report step")
        self.assertIn('--include="core/*"', blocks[0])
        self.assertIn("continue-on-error: true", blocks[0])

    def test_coverage_data_is_not_committable(self):
        ignored = Path(".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".coverage", [line.strip() for line in ignored])


_QT_FILES = [
    "tests/test_review_decode.py",
    "tests/test_review_keys_window.py",
    "tests/test_stage1_run_window.py",
    "tests/test_stage2_look.py",
    "tests/test_stage3_queue.py",
    "tests/test_stage3_ui.py",
    "tests/test_stage4.py",
    "tests/test_wave5_defects.py",
    "tests/test_wave8.py",
    "tests/test_wave10.py",
]


class TestWidgetTestsCannotSkipInCI(unittest.TestCase):
    """#729. CI installs `.[shell,app]`, yet all 23 widget tests skipped there as
    'PySide6 extra not installed' -- the import failed on the runner for another
    reason, the message lied, and `ci.yml` claimed '23 ran, 0 skipped'."""

    def test_the_helper_never_skips_under_ci(self):
        import tests.qt_support as qt

        broken = "libEGL.so.1: cannot open shared object file"
        with patch.object(qt, "QT_IMPORT_ERROR", broken):
            with patch.dict(os.environ, {"CI": "true"}):
                self.assertFalse(qt.should_skip(), "a broken Qt install must error in CI")
            with patch.dict(os.environ, {"CI": ""}):
                self.assertTrue(qt.should_skip())
                self.assertIn("libEGL", qt.skip_reason(), "the skip must say why")

    def test_the_ci_guard_reports_the_real_import_error(self):
        import tests.qt_support as qt

        with patch("importlib.import_module", side_effect=ImportError("libEGL.so.1")):
            problem = qt.qt_import_problem()
        self.assertIsNotNone(problem)
        self.assertIn("libEGL.so.1", problem)

    def test_qt_really_imports_in_ci(self):
        import tests.qt_support as qt

        if not qt.in_ci():
            self.skipTest("not CI; the app extra is optional locally")
        self.assertIsNone(qt.qt_import_problem())

    def test_every_widget_test_file_uses_the_helper(self):
        offenders = []
        for name in _QT_FILES:
            text = Path(name).read_text(encoding="utf-8")
            if "PySide6 extra not installed" in text or "requires_qt" not in text:
                offenders.append(name)
        self.assertEqual(offenders, [], "these still carry the silent skip")

    def test_ci_installs_the_qt_runtime_libraries(self):
        live = _live_ci()
        for package in ("libegl1", "libxkbcommon0"):
            self.assertIn(package, live)

    def test_the_stale_ci_claim_is_gone(self):
        self.assertNotIn("23 ran, 0 skipped", CI_YML.read_text(encoding="utf-8"))


_SECRET = "sk-SENTINEL-9f3a7c21d4e8"
_TOKEN = "ya29.SENTINEL-token-4b7e"


class TestNoSecretReachesATrace(unittest.TestCase):
    """#636. `core/run_trace.py` redacted by key name only, so a secret inside a
    free-text value -- an LLM error echoing the key, a source URL carrying
    `?api_key=`, a topic -- was written to `data/traces` verbatim."""

    def _write(self, tmp: str, **overrides) -> dict:
        import core.run_trace as rt

        calls = [{"provider": "deepseek", "error": f"401 invalid key {_SECRET}"}]
        kwargs = {
            "run_id": 7,
            "channel_id": "tapin",
            "input_topic": f"UFC 320 {_SECRET}",
            "selected_topic": "UFC 320 recap",
            "status": "drafted",
            "features": {
                "source_urls": [f"https://api.example.com/v1/items?api_key={_TOKEN}&q=ufc"]
            },
            "quality": {"note": f"echoed {_SECRET}"},
            "menu_path": f"new video > {_TOKEN}",
        }
        kwargs.update(overrides)
        env = {"DEEPSEEK_API_KEY": _SECRET, "YOUTUBE_ACCESS_TOKEN": _TOKEN, "SHORT_TOKEN": "true"}
        with (
            patch.object(rt, "TRACES_DIR", tmp),
            patch.object(rt, "_llm_calls", return_value=(calls, 0.0)),
            patch.dict(os.environ, env),
        ):
            path = rt.write_run_trace(**kwargs)
        self.assertTrue(path)
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_env_secret_values_never_reach_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = json.dumps(self._write(tmp))
        self.assertNotIn(_SECRET, text)
        self.assertNotIn(_TOKEN, text)

    def test_ordinary_values_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self._write(tmp, input_topic="a true story")
        self.assertEqual(data["selected_topic"], "UFC 320 recap")
        self.assertEqual(
            data["input_topic"], "a true story", "a short env value must not scrub text"
        )
        self.assertIn("q=ufc", data["source_urls"][0])
        self.assertNotIn("api_key=ya29", data["source_urls"][0])

    def test_the_scan_verb_finds_a_leak_without_printing_it(self):
        from argparse import Namespace

        from scripts import ops

        self.assertIn("trace-secrets-scan", ops.COMMANDS)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "1.json").write_text(json.dumps({"x": f"leak {_SECRET}"}), encoding="utf-8")
            Path(tmp, "2.json").write_text(json.dumps({"x": "clean"}), encoding="utf-8")
            with (
                patch("core.trace_secrets.TRACES_DIR", tmp),
                patch.dict(os.environ, {"DEEPSEEK_API_KEY": _SECRET}),
                redirect_stdout(io.StringIO()) as out,
            ):
                code = ops.cmd_trace_secrets_scan(Namespace())
        self.assertEqual(code, 1)
        self.assertIn("1.json", out.getvalue())
        self.assertNotIn(_SECRET, out.getvalue())

    def test_the_scan_verb_is_clean_on_clean_traces(self):
        from argparse import Namespace

        from scripts import ops

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "2.json").write_text(json.dumps({"x": "clean"}), encoding="utf-8")
            with (
                patch("core.trace_secrets.TRACES_DIR", tmp),
                patch.dict(os.environ, {"DEEPSEEK_API_KEY": _SECRET}),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(ops.cmd_trace_secrets_scan(Namespace()), 0)


class TestEnvLint(unittest.TestCase):
    """#639. 402 env keys are read by literal name against 285 key lines in
    `.env.example`, and each wave added a flag documented by hand or not at all.
    Nothing measured the gap, so it could only grow."""

    def test_every_literal_access_form_is_read(self):
        from core.env_lint import scan_reads

        source = "\n".join(
            [
                "import os",
                'a = os.getenv("KEY_GETENV")',
                'b = os.environ.get("KEY_ENVIRON_GET", "x")',
                'c = os.environ["KEY_ENVIRON_INDEX"]',
                'd = flag_enabled("KEY_FLAG_ENABLED", default=True)',
                'e = _flag("KEY_UNDERSCORE_FLAG", False)',
                'f = _env_float("KEY_ENV_FLOAT")',
                "g = os.getenv(name)",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "mod.py").write_text(source, encoding="utf-8")
            Path(tmp, "tests").mkdir()
            Path(tmp, "tests", "test_x.py").write_text(
                'os.getenv("ONLY_IN_TESTS")', encoding="utf-8"
            )
            reads = scan_reads(roots=[Path(tmp)])
        self.assertEqual(
            reads.keys,
            {
                "KEY_GETENV",
                "KEY_ENVIRON_GET",
                "KEY_ENVIRON_INDEX",
                "KEY_FLAG_ENABLED",
                "KEY_UNDERSCORE_FLAG",
                "KEY_ENV_FLOAT",
            },
        )
        self.assertEqual(
            reads.dynamic, 1, "a non-literal read is a blind spot, counted not guessed"
        )

    def test_commented_example_lines_count_as_documented(self):
        from core.env_lint import documented_keys

        with tempfile.TemporaryDirectory() as tmp:
            example = Path(tmp, ".env.example")
            example.write_text(
                "A_KEY=1\n# B_FLAG=true   # optional\n#C_FLAG=\n# not a key: D_THING\n",
                encoding="utf-8",
            )
            self.assertEqual(documented_keys(example), {"A_KEY", "B_FLAG", "C_FLAG"})

    def test_env_fingerprint_keys_are_unchanged(self):
        """Guard: #687's fingerprint must keep ignoring commented lines, or every
        trace's env_sha256 drifts at once."""
        from core.config_diff import env_example_keys

        with tempfile.TemporaryDirectory() as tmp:
            example = Path(tmp, ".env.example")
            example.write_text("A_KEY=1\n# B_FLAG=true\n", encoding="utf-8")
            self.assertEqual(env_example_keys(example), ["A_KEY"])

    def test_no_new_undocumented_key(self):
        from core.env_lint import lint

        report = lint()
        self.assertEqual(
            report.new_undocumented,
            [],
            "document these in .env.example (or, deliberately, add to config/env_lint_baseline.json)",
        )

    def test_the_baseline_only_shrinks(self):
        from core.env_lint import load_baseline, scan_reads

        stale = sorted(load_baseline() - scan_reads().keys)
        self.assertEqual(stale, [], "these are no longer read; drop them from the baseline")

    def test_the_ratchet_catches_a_new_key(self):
        from core import env_lint

        real = env_lint.scan_reads()
        fake = env_lint.EnvReads(
            keys=real.keys | {"BRAND_NEW_UNDOCUMENTED_KEY"}, dynamic=real.dynamic
        )
        with patch.object(env_lint, "scan_reads", return_value=fake):
            self.assertEqual(env_lint.lint().new_undocumented, ["BRAND_NEW_UNDOCUMENTED_KEY"])

    def test_the_ops_verb_fails_only_on_new_keys(self):
        from argparse import Namespace

        from core import env_lint
        from scripts import ops

        self.assertIn("env-lint", ops.COMMANDS)
        clean = env_lint.EnvLint(
            undocumented=["OLD_KEY"], unread=[], dynamic=3, new_undocumented=[]
        )
        dirty = env_lint.EnvLint(
            undocumented=["OLD_KEY", "NEW_KEY"], unread=[], dynamic=3, new_undocumented=["NEW_KEY"]
        )
        with patch("core.env_lint.lint", return_value=clean), redirect_stdout(io.StringIO()):
            self.assertEqual(ops.cmd_env_lint(Namespace()), 0)
        with patch("core.env_lint.lint", return_value=dirty), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ops.cmd_env_lint(Namespace()), 1)
        self.assertIn("NEW_KEY", out.getvalue())


class TestCaptionPlacementIsOptInAgain(unittest.TestCase):
    """#727. Measured on labelled real footage: on 50 Pexels stock clips with no
    overlay, the default-on detector moved captions to the top of 2 (px34 a yellow
    shirt on pink, px39 a suit on white) -- #718's original harm on finished renders.
    Operator call 2026-09-13: back to opt-in until stock footage reads 0/50."""

    def test_unset_means_captions_stay_at_the_bottom(self):
        from video.caption_place import choose_caption_anchor

        with patch("video.caption_place.bottom_band_overlay", return_value=True):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CAPTION_AUTO_PLACE", None)
                self.assertEqual(choose_caption_anchor("clip.mp4"), "bottom")

    def test_opting_in_still_works(self):
        from video.caption_place import choose_caption_anchor

        with (
            patch("video.caption_place.bottom_band_overlay", return_value=True),
            patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}),
        ):
            self.assertEqual(choose_caption_anchor("clip.mp4"), "top")

    def test_ops_caption_anchor_says_it_is_off(self):
        from argparse import Namespace

        from PIL import Image

        from scripts import ops

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "still.png"
            Image.new("RGB", (270, 480), (40, 40, 40)).save(path)
            with redirect_stdout(io.StringIO()) as out:
                ops.cmd_caption_anchor(Namespace(path=str(path)))
        self.assertIn("off by default", out.getvalue())


class TestCaptionAnchorPrintsTheLiveThresholds(unittest.TestCase):
    """Found by running `ops caption-anchor` on px34 after #727: it printed
    'needs >= 0.25' while the threshold was 0.18. The operator's own measuring tool
    reported a bar the detector no longer used, because the numbers were typed in."""

    def test_the_needs_figures_come_from_the_module(self):
        from argparse import Namespace

        from scripts import ops
        from video import caption_place as cp

        reading = {
            "spatial": "ok",
            "metrics": (1.0, 1.0),
            "step": True,
            "motion": "ok",
            "excess": 0.5,
            "overlay": True,
        }
        with (
            patch.object(cp, "_MIN_SPREAD", 0.456),
            patch.object(cp, "_MIN_STEP_SHARE", 0.789),
            patch.object(cp, "_MIN_STATIC_EXCESS", 0.123),
            patch("video.caption_place.overlay_reading", return_value=reading),
            redirect_stdout(io.StringIO()) as out,
        ):
            ops.cmd_caption_anchor(Namespace(path="clip.mp4"))
        text = out.getvalue()
        for figure in ("needs >= 0.46", "needs >= 0.79", "needs >= 0.12"):
            self.assertIn(figure, text)


class TestRealScoreBarsAreRecovered(unittest.TestCase):
    """#727. Six real NBA 2K score bars were missed on the cropped frame; four fell on
    temporal excess 0.19-0.22 against a 0.25 threshold. Measured on 30 labelled bars,
    50 stock clips and 12 hybrids: 0.18 recovers 22 -> 26 bars and adds no new TOP
    anywhere (per-block spatial candidates added 5-17 stock false positives)."""

    def test_a_measured_miss_now_counts(self):
        from video.caption_place import frames_show_static_overlay

        with patch("video.caption_place.temporal_reading", return_value=(0.5, 0.19)):
            self.assertTrue(frames_show_static_overlay(object(), object()))

    def test_scenery_level_excess_still_does_not(self):
        from video.caption_place import frames_show_static_overlay

        with patch("video.caption_place.temporal_reading", return_value=(0.5, 0.15)):
            self.assertFalse(frames_show_static_overlay(object(), object()))


if __name__ == "__main__":
    unittest.main()
