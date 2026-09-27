"""#893: time estimates follow the voice's real pace.

Wave 40 slowed the voice to 0.95 (#890), but every pre-render time still divided words
by the fixed 3.3 words/second, so chapter lines and the description's duration ran about
5% early until real word timings replaced them - and only when a sidecar existed. The
estimates now use `spoken_words_per_second`; the length presets keep the nominal rate
because they size scripts, they do not time them.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _env(speed=None):
    env = {k: v for k, v in os.environ.items() if k != "TTS_SPEED"}
    if speed is not None:
        env["TTS_SPEED"] = speed
    return patch.dict(os.environ, env, clear=True)


class SpokenPaceTests(unittest.TestCase):
    def test_the_rate_follows_the_pace(self):
        from core.script_length import WORDS_PER_SECOND, spoken_words_per_second

        with _env():
            self.assertAlmostEqual(spoken_words_per_second("tapin"), WORDS_PER_SECOND * 0.95)
        with _env("1.0"):
            self.assertAlmostEqual(spoken_words_per_second("tapin"), WORDS_PER_SECOND)

    def test_an_estimated_chapter_lands_at_the_slower_time(self):
        from core.angle_chapters import AngleChapter, chapter_lines

        chapters = [
            AngleChapter(1, "Open", "a", 0),
            AngleChapter(2, "Second", "b", 330),
            AngleChapter(3, "Third", "c", 660),
        ]
        with _env():
            self.assertIn("1:45 Second", chapter_lines(chapters))
        with _env("1.0"):
            self.assertIn("1:40 Second", chapter_lines(chapters))

    def test_the_extended_block_estimate_scales_too(self):
        from core.chapters import chapter_block

        script = " ".join(f"Sentence number {i} has five words." for i in range(120))

        def last_time(block: str) -> int:
            m, s = re.findall(r"^(\d+):(\d\d)", block, re.M)[-1]
            return int(m) * 60 + int(s)

        with _env():
            slow = last_time(chapter_block(script, length_choice="4"))
        with _env("1.0"):
            nominal = last_time(chapter_block(script, length_choice="4"))
        self.assertGreater(slow, nominal)

    def test_the_review_readout_estimates_at_the_pace(self):
        from core.review_booth import duration_readout

        with _env():
            slow = duration_readout(100.0, 330)
        with _env("1.0"):
            nominal = duration_readout(100.0, 330)
        self.assertNotEqual(slow, nominal)


class NoRawRateTests(unittest.TestCase):
    """Only the modules that size scripts may divide by the nominal rate."""

    ALLOWED = frozenset(
        {
            "core/script_length.py",  # the presets' duration hints and the helper itself
            "core/tts.py",  # long-form voice policy sizes a preset, not a run
            "core/seo.py",  # preset maximum for the SEO length hint
            "scripts/bench_script_duration.py",  # re-derives the constant itself
        }
    )

    def test_estimates_use_the_spoken_rate(self):
        offenders = []
        for folder in ("core", "analytics", "video", "publishing", "scripts"):
            for path in (ROOT / folder).rglob("*.py"):
                rel = path.relative_to(ROOT).as_posix()
                if rel in self.ALLOWED:
                    continue
                if re.search(
                    r"/\s*(?:max\()?\s*WORDS_PER_SECOND\b", path.read_text(encoding="utf-8")
                ):
                    offenders.append(rel)
        self.assertEqual(offenders, [], "divide by spoken_words_per_second(channel_id) instead")


if __name__ == "__main__":
    unittest.main()
