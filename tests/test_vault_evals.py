"""Candidate 329 P1: make vault subject-relevance a number instead of an argument.

Whether a vault bullet is about the same subject as the topic had been argued three
times and measured zero times, so every change traded a false positive for a false
negative with no way to say whether it helped. This harness scores the **shipped**
decision path against frozen labelled cases from live-run 71.

Baseline recorded at the time of writing: **precision 0.667, recall 0.667** — one
off-topic bullet attached (the shared-token "Wolverine Rage" case, which P0 surfaces
flagged rather than dropping) and one on-topic bullet missed (a follow-up with no
entities of its own). P2's scorer has to beat that, measured, not argued.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import vault_evals


class TestFixtureSetIsUsable(unittest.TestCase):
    def test_cases_load(self):
        cases = vault_evals.load_cases()
        self.assertGreaterEqual(len(cases), 6)

    def test_every_case_is_labelled_and_complete(self):
        for case in vault_evals.load_cases():
            for key in ("id", "topic", "corpus", "bullet", "expected", "why"):
                self.assertIn(key, case, f"{case.get('id')} missing {key}")
            self.assertIsInstance(case["expected"], bool)

    def test_both_labels_are_represented(self):
        labels = {bool(c["expected"]) for c in vault_evals.load_cases()}
        self.assertEqual(labels, {True, False}, "a one-sided set cannot measure both errors")

    def test_config_is_valid_json(self):
        # It was briefly reformatted as Python (trailing commas) and silently loaded as
        # zero cases — an eval set that reports nothing looks exactly like a passing one.
        with open(vault_evals.EVALS_CONFIG, encoding="utf-8") as f:
            json.load(f)


class TestScoring(unittest.TestCase):
    def test_perfect_agreement_scores_one(self):
        cases = [{"id": "a", "expected": True}, {"id": "b", "expected": False}]
        with patch.object(vault_evals, "decide", side_effect=lambda c: bool(c["expected"])):
            result = vault_evals.score(cases)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 1.0)

    def test_a_leak_lowers_precision(self):
        cases = [{"id": "a", "expected": True}, {"id": "b", "expected": False}]
        with patch.object(vault_evals, "decide", return_value=True):
            result = vault_evals.score(cases)
        self.assertEqual(result["false_positive"], 1)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1.0)

    def test_a_miss_lowers_recall(self):
        cases = [{"id": "a", "expected": True}, {"id": "b", "expected": False}]
        with patch.object(vault_evals, "decide", return_value=False):
            result = vault_evals.score(cases)
        self.assertEqual(result["false_negative"], 1)
        self.assertEqual(result["recall"], 0.0)

    def test_a_raising_case_is_skipped_not_counted_as_correct(self):
        cases = [{"id": "a", "expected": True}, {"id": "b", "expected": True}]
        with patch.object(vault_evals, "decide", side_effect=[RuntimeError("boom"), True]):
            result = vault_evals.score(cases)
        self.assertEqual(result["cases"], 1, "a crash must not silently score as a pass")


class TestItScoresTheShippedPath(unittest.TestCase):
    """The eval is worthless if it grades a reimplementation instead of the real code."""

    def test_decide_runs_the_real_loader(self):
        with patch("core.obsidian_facts.load_fact_records", return_value=[]) as loader:
            vault_evals.decide(
                {"topic": "t", "note_stem": "n", "note_headings": "h", "bullet": "b"}
            )
        loader.assert_called_once()

    def test_the_unambiguous_case_is_attached_today(self):
        case = next(c for c in vault_evals.load_cases() if c["id"] == "run71-gta-direct")
        self.assertTrue(vault_evals.decide(case), "a scorer missing this is broken")

    def test_the_run71_leak_is_still_excluded_today(self):
        case = next(c for c in vault_evals.load_cases() if c["id"] == "run71-marvel-rivals")
        self.assertFalse(vault_evals.decide(case), "the gap Cursor closed must stay closed")


class TestReportAndPersistence(unittest.TestCase):
    def test_render_is_ascii_safe(self):
        text = vault_evals.render(vault_evals.score([{"id": "a", "expected": True}]))
        self.assertEqual([c for c in text if ord(c) > 127], [])

    def test_save_and_compare_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(vault_evals, "EVALS_DIR", str(Path(tmp) / "vault_evals")):
                self.assertIn("Need two", vault_evals.compare_latest())
                vault_evals.save({"timestamp": "2026-01-01T00:00:00", "precision": 0.5})
                vault_evals.save({"timestamp": "2026-01-02T00:00:00", "precision": 0.9})
                out = vault_evals.compare_latest()
        self.assertIn("precision", out)


if __name__ == "__main__":
    unittest.main()
