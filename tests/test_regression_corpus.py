"""Replay every frozen live-run defect (wave 36).

Twice a later change silently undid an earlier fix - #745 replaced the grounding
stopwords ("Why Jason Duval" was a name again), the SRT force_style shrank karaoke
captions (run 77 on YouTube) - because each fix's test pinned one run's strings beside
the code it changed. And fixes reached one module but not its siblings: run 98's
question-word fix reached 1 of 7 tokenizers, #852's entity query 1 of 11 builders.
`tests/regression_corpus.json` holds each defect as a pure call and an expectation;
this replays all of them on every CI run.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from core.regression_corpus import cases_for_file, load_cases, resolve, run_case

ROOT = Path(__file__).resolve().parents[1]


class RegressionCorpusTests(unittest.TestCase):
    def test_every_case_holds(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                ok, got = run_case(case)
                self.assertTrue(ok, f"{case['id']} (#{case['item']}): got {got!r} - {case['why']}")

    def test_ids_are_unique(self):
        ids = [c["id"] for c in load_cases()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_call_resolves(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                self.assertTrue(callable(resolve(case["call"])))

    def test_every_item_exists_in_the_backlog(self):
        backlog = (ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
        numbers = set(re.findall(r"^- \[[ x]\] (?:\*\*)?(\d+)\. ", backlog, flags=re.M))
        for case in load_cases():
            with self.subTest(case=case["id"]):
                self.assertIn(str(case["item"]), numbers)

    def test_every_case_says_why(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                self.assertTrue(str(case.get("why") or "").strip())
                self.assertTrue(case.get("expect"))

    def test_cases_for_file_maps_modules_to_paths(self):
        ids = {c["id"] for c in cases_for_file("apis/rss_feeds.py")}
        self.assertIn("run98-rss-tokens", ids)
        self.assertNotIn("run98-tts-concat-absolute", ids)


class RunCaseTests(unittest.TestCase):
    def test_a_broken_expectation_fails(self):
        case = {
            "id": "x",
            "call": "apis.topic_tokens:content_tokens",
            "args": ["what does this mean"],
            "expect": {"includes_all": ["what"]},
        }
        ok, _got = run_case(case)
        self.assertFalse(ok)

    def test_a_raising_call_is_a_failure_not_a_crash(self):
        case = {
            "id": "x",
            "call": "apis.topic_tokens:content_tokens",
            "args": [1, 2, 3],
            "expect": {"truthy": True},
        }
        ok, got = run_case(case)
        self.assertFalse(ok)
        self.assertIn("raised", str(got))

    def test_select_zero_is_an_index(self):
        """Wave 67: `select: 0` was read as "no select", so a case on a tuple's first item
        checked the whole tuple - a `not_contains` on it could never fail."""
        case = {
            "id": "x",
            "call": "core.script_length:trim_overlength",
            "args": ["One sentence here. Two sentence here."],
            "kwargs": {"max_words": 0},
            "select": 0,
            "expect": {"contains": "Two sentence"},
        }
        ok, got = run_case(case)
        self.assertTrue(ok, got)
        self.assertIsInstance(got, str)

    def test_unknown_expectation_is_a_failure(self):
        case = {
            "id": "x",
            "call": "apis.topic_tokens:content_tokens",
            "args": ["a"],
            "expect": {"nope": 1},
        }
        self.assertFalse(run_case(case)[0])

    def test_ops_verb_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("regressions", COMMANDS)


if __name__ == "__main__":
    unittest.main()
