"""Wave 16: five defects from live runs 77/78. Each test observed failing on unmodified 9c42605.

Run 77 uploaded with chapters 0:00-0:17 (the first eight sentences - YouTube needs three
chapters of at least ten seconds, so it drops them), with the pre-refinement description,
and with `shorts` / `Forward` / `Billion` tags on a 293-second video. The worker said nothing
when the upload went through. #732: the env fingerprint never saw optional flags.
"""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

RUN77_VARIANT = (
    "GTA 6's Online Economy: A $1 Billion Opportunity? (Forward prediction) - A prediction of "
    "how GTA 6's online features and monetization model will shape the gaming industry's "
    "business landscape."
)
_STAMP = re.compile(r"^(\d+):(\d{2})(?::(\d{2}))?\s+(.+)$")


def _seconds(line: str) -> float:
    match = _STAMP.match(line)
    assert match, line
    a, b, c = match.group(1), match.group(2), match.group(3)
    return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)


def _long_script() -> str:
    # ~1,000 words, like run 77's 1,005-word Extended script.
    return " ".join(
        f"Point {i} about the online economy matters because players spend real money every week."
        for i in range(70)
    )


def _timings(script: str, wps: float = 3.43) -> list[dict]:
    words = re.findall(r"[A-Za-z0-9']+", script)
    return [
        {"word": w, "start": round(i / wps, 3), "end": round(i / wps + 0.25, 3)}
        for i, w in enumerate(words)
    ]


class TestWorkerAnnouncesUploads(unittest.TestCase):
    """Run 77's upload went through with nothing on the console (INFO log, WARNING level)."""

    def test_a_successful_upload_prints_the_video_link(self):
        from jobs import worker
        from publishing.base import PublishResult

        job = SimpleNamespace(id=44, content_run_id=77, attempts=1, max_attempts=3)
        result = PublishResult(video_id="abc123XYZ", status="uploaded")
        out = io.StringIO()
        with (
            patch.object(worker, "get_job_repository", return_value=MagicMock()),
            patch.object(worker, "get_content_run_repository", return_value=MagicMock()),
            patch.object(worker, "_defer_for_quota", return_value=False),
            redirect_stdout(out),
        ):
            worker._finalize_upload_job(job, result)
        text = out.getvalue()
        self.assertIn("44", text)
        self.assertIn("https://youtu.be/abc123XYZ", text)


class TestEnvFingerprintSeesOptionalFlags(unittest.TestCase):
    """#732. `# CAPTION_AUTO_PLACE=` lines never reached `env_sha256`."""

    def test_an_optional_flag_changes_the_fingerprint(self):
        from core.config_diff import env_fingerprint

        with tempfile.TemporaryDirectory() as tmp:
            example = Path(tmp, ".env.example")
            example.write_text("A_KEY=1\n# CAPTION_AUTO_PLACE=true\n", encoding="utf-8")
            off = env_fingerprint(environ={"A_KEY": "x"}, example_path=example)
            on = env_fingerprint(
                environ={"A_KEY": "x", "CAPTION_AUTO_PLACE": "true"}, example_path=example
            )
        self.assertNotEqual(off, on)

    def test_a_trace_from_the_old_scheme_is_not_reported_as_drift(self):
        from core.config_diff import ENV_FINGERPRINT_VERSION, channels_fingerprint, diff_against

        self.assertEqual(ENV_FINGERPRINT_VERSION, 2)
        old = diff_against({"channels_sha256": channels_fingerprint(), "env_sha256": "0" * 64})
        env_line = next(line for line in old if ".env" in line)
        self.assertNotIn("drifted", env_line)
        self.assertIn("scheme", env_line)
        new = diff_against(
            {
                "channels_sha256": channels_fingerprint(),
                "env_sha256": "0" * 64,
                "env_fingerprint_version": ENV_FINGERPRINT_VERSION,
            }
        )
        self.assertIn("drifted", next(line for line in new if ".env" in line))

    def test_traces_stamp_the_fingerprint_version(self):
        from core import run_trace
        from core.config_diff import ENV_FINGERPRINT_VERSION

        with tempfile.TemporaryDirectory() as tmp, patch.object(run_trace, "TRACES_DIR", tmp):
            path = run_trace.write_run_trace(
                run_id=91, channel_id="tapin", input_topic="t", selected_topic="t", status="drafted"
            )
            blob = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(blob.get("env_fingerprint_version"), ENV_FINGERPRINT_VERSION)


class TestLongVideoTags(unittest.TestCase):
    """Run 77 (293 s) was tagged shorts, plus Forward / Billion / Opportunity."""

    def test_shorts_tags_drop_when_the_preset_runs_past_three_minutes(self):
        from core.seo import drop_shorts_tags

        tags = ["GTA6", "shorts", "#Shorts", "YouTubeShorts", "esports"]
        self.assertEqual(drop_shorts_tags(tags, "4"), ["GTA6", "esports"])
        self.assertEqual(drop_shorts_tags(tags, "3"), ["GTA6", "esports"])
        self.assertEqual(drop_shorts_tags(tags, "2"), tags)

    def test_an_extended_package_has_no_shorts_or_lens_word_tags(self):
        from core.content_engine import generate_content_package

        # Run 77's model returned 13 tags; the first eight, verbatim.
        run77_llm_tags = [
            "GTA6", "GTA6Online", "RockstarGames", "GTA6ReleaseDate",
            "GTA6Multiplayer", "GTA6Predictions", "GTAOnline", "TakeTwo",
        ]  # fmt: skip
        payload = {"script": "GTA 6 Online has no release date yet. " * 30, "tags": run77_llm_tags}
        with (
            patch("core.content_engine.enrich_facts", return_value="- GTA 6 Online has no date"),
            patch("core.content_engine._call_content_llm", return_value=payload),
            patch("core.content_engine._expand_script", side_effect=lambda **k: k["script"]),
            patch(
                "core.content_engine._relength_after_postprocessing",
                side_effect=lambda script, **k: (script, list(k.get("ungrounded") or [])),
            ),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="GTA 6 Online"),
            patch("core.content_engine._maybe_improve_hook", side_effect=lambda s: s),
            patch("core.content_engine._maybe_inject_insight", side_effect=lambda s, *_a, **_k: s),
        ):
            package = generate_content_package(
                RUN77_VARIANT, {}, (1000, 2000), "2026-09-13", channel_id="tapin", length_choice="4"
            )
        lowered = [t.lower() for t in package["tags"]]
        self.assertNotIn("shorts", lowered)
        for junk in ("forward", "billion", "opportunity", "prediction"):
            self.assertNotIn(junk, lowered, package["tags"])


class TestExtendedChaptersAreValidOnYouTube(unittest.TestCase):
    """Run 77 stored 0:00 0:02 0:05 0:06 0:13 0:14 0:16 0:17 - the first eight sentences."""

    def _assert_valid(self, block: str, duration: float) -> list[str]:
        lines = block.splitlines()
        self.assertGreaterEqual(len(lines), 3, block)
        self.assertTrue(lines[0].startswith("0:00 "), block)
        stamps = [_seconds(line) for line in lines]
        for earlier, later in pairwise(stamps):
            self.assertGreaterEqual(later - earlier, 10, block)
        self.assertGreater(stamps[-1], duration * 0.6, block)
        return lines

    def test_word_timed_chapters_span_the_whole_video(self):
        from core.chapters import chapter_block

        script = _long_script()
        words = _timings(script)
        duration = words[-1]["end"]
        lines = self._assert_valid(
            chapter_block(script, duration=duration, length_choice="4", word_timings=words),
            duration,
        )
        points = [int(re.search(r"Point (\d+)", line).group(1)) for line in lines]
        self.assertEqual(points, sorted(points))
        self.assertGreater(points[-1], 40)

    def test_estimated_chapters_are_valid_and_labelled_where_they_sit(self):
        """Without timings the old block spread its times evenly but still labelled the first
        eight sentences, so 4:16 read "Point 7"."""
        from core.chapters import chapter_block

        lines = self._assert_valid(
            chapter_block(_long_script(), duration=293.0, length_choice="4"), 293.0
        )
        points = [int(re.search(r"Point (\d+)", line).group(1)) for line in lines]
        self.assertGreater(points[-1], 40, lines)

    def test_too_short_for_three_ten_second_chapters_emits_none(self):
        from core.chapters import chapter_block

        script = "One short line. Another short line. A third short line."
        self.assertEqual(chapter_block(script, duration=20.0, length_choice="4"), "")

    def test_angle_chapters_closer_than_ten_seconds_are_not_emitted(self):
        from core.angle_chapters import AngleChapter, chapter_lines

        script = _long_script()
        words = _timings(script, wps=1.0)
        chapters = [
            AngleChapter(index=0, title="One", angle="One", word_start=0),
            AngleChapter(index=1, title="Two", angle="Two", word_start=4),
            AngleChapter(index=2, title="Three", angle="Three", word_start=200),
            AngleChapter(index=3, title="Four", angle="Four", word_start=400),
        ]
        lines = chapter_lines(chapters, word_timings=words).splitlines()
        self.assertEqual([line.split(" ", 1)[1] for line in lines], ["One", "Three", "Four"])


class TestUploadUsesTheRefinedDescription(unittest.TestCase):
    """main.py / auto_generate enqueued `result.description`; TTS refinement only reached the DB."""

    def test_current_description_prefers_the_stored_row(self):
        from core.chapters import current_description

        repo = SimpleNamespace(get=lambda run_id: SimpleNamespace(description="0:00 refined"))
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            self.assertEqual(current_description(77, "0:00 stale"), "0:00 refined")
            self.assertEqual(current_description(None, "0:00 stale"), "0:00 stale")

    def test_an_unreadable_store_keeps_the_in_memory_description(self):
        from core.chapters import current_description

        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            side_effect=RuntimeError("db down"),
        ):
            self.assertEqual(current_description(77, "in memory"), "in memory")

    def test_both_upload_callers_read_it(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("main.py", os.path.join("scripts", "auto_generate.py")):
            with self.subTest(caller=name):
                self.assertIn("current_description(", (root / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
