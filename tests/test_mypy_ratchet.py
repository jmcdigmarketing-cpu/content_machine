"""The mypy ratchet only ever tightens (#833). Parse/compare logic, no mypy run."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.mypy_ratchet import TARGETS, parse_error_count, verdict


class TestParse(unittest.TestCase):
    def test_reads_the_summary_line(self):
        out = "core/x.py:1: error: boom  [attr-defined]\nFound 135 errors in 89 files (checked 351 source files)\n"
        self.assertEqual(parse_error_count(out), 135)

    def test_singular_and_clean(self):
        self.assertEqual(parse_error_count("Found 1 error in 1 file (checked 3 source files)\n"), 1)
        self.assertEqual(parse_error_count("Success: no issues found in 351 source files\n"), 0)

    def test_no_summary_is_an_error_not_a_zero(self):
        # A crashed mypy must not read as "0 errors" and pass the ratchet.
        with self.assertRaises(ValueError):
            parse_error_count("Traceback (most recent call last): ...\n")


class TestVerdict(unittest.TestCase):
    def test_rising_fails(self):
        code, line = verdict(136, 135)
        self.assertEqual(code, 1)
        self.assertIn("> baseline", line)

    def test_equal_passes(self):
        self.assertEqual(verdict(135, 135)[0], 0)

    def test_falling_passes_and_asks_to_lower(self):
        code, line = verdict(120, 135)
        self.assertEqual(code, 0)
        self.assertIn("lower the baseline", line)


class TestWiring(unittest.TestCase):
    def test_ci_runs_the_ratchet_and_holds_no_second_directory_list(self):
        # The directory list lives in TARGETS and nowhere else: ci.yml calls the script
        # instead of naming packages, so the two cannot drift apart again.
        ci = (Path(__file__).resolve().parent.parent / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python scripts/mypy_ratchet.py", ci)
        self.assertNotRegex(
            ci, r"run: mypy ", "ci.yml names mypy packages; TARGETS is the one list"
        )
        self.assertGreaterEqual(len(TARGETS), 6)

    def test_baseline_file_is_committed_and_numeric(self):
        path = Path(__file__).resolve().parent.parent / "mypy_baseline.txt"
        self.assertTrue(
            path.exists(), "mypy_baseline.txt missing — py scripts/mypy_ratchet.py --update"
        )
        self.assertGreaterEqual(int(path.read_text(encoding="utf-8").strip()), 0)


if __name__ == "__main__":
    unittest.main()
