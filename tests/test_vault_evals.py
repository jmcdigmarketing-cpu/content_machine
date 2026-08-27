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
            for key in ("id", "topic", "corpus", "bullet", "expected", "why", "source"):
                self.assertIn(key, case, f"{case.get('id')} missing {key}")
            self.assertIsInstance(case["expected"], bool)

    def test_both_labels_are_represented(self):
        labels = {bool(c["expected"]) for c in vault_evals.load_cases()}
        self.assertEqual(labels, {True, False}, "a one-sided set cannot measure both errors")

    def test_holdout_has_both_labels_across_multiple_real_runs(self):
        holdout = [c for c in vault_evals.load_cases() if c.get("split") == "holdout"]
        self.assertGreaterEqual(len({c.get("source") for c in holdout}), 2)
        self.assertEqual({bool(c["expected"]) for c in holdout}, {True, False})
        self.assertTrue(all(str(c.get("source") or "").startswith("live-run ") for c in holdout))

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

    def test_a_raising_case_invalidates_the_run(self):
        cases = [{"id": "a", "expected": True}, {"id": "b", "expected": True}]
        with patch.object(vault_evals, "decide", side_effect=[RuntimeError("boom"), True]):
            result = vault_evals.score(cases)
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["attempted"], 2)

    def test_zero_cases_is_invalid(self):
        result = vault_evals.score([])
        self.assertFalse(result["valid"])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])

    def test_both_modes_are_reported_from_the_same_cases(self):
        result = vault_evals.score_modes(vault_evals.load_cases())
        self.assertEqual(set(result["modes"]), {"legacy", "scored"})
        self.assertEqual(result["modes"]["legacy"]["attempted"], len(vault_evals.load_cases()))
        self.assertEqual(result["modes"]["scored"]["attempted"], len(vault_evals.load_cases()))
        self.assertEqual(result["rubric_version"], "v1")

    def test_p3_gate_is_judged_on_the_multi_run_holdout(self):
        result = vault_evals.score_modes(vault_evals.load_cases())
        holdout = result["splits"]["holdout"]["scored"]
        self.assertTrue(holdout["valid"])
        self.assertGreater(holdout["precision"], 0.667)
        self.assertGreater(holdout["recall"], 0.667)
        self.assertTrue(result["p3_gate"]["passed"], result["p3_gate"])


class TestItScoresTheShippedPath(unittest.TestCase):
    """The eval is worthless if it grades a reimplementation instead of the real code."""

    def test_decide_runs_the_real_loader(self):
        with patch("core.obsidian_facts.load_fact_records", return_value=[]) as loader:
            vault_evals.decide(
                {
                    "topic": "t",
                    "corpus": "the measured corpus",
                    "note_stem": "n",
                    "note_headings": "h",
                    "bullet": "b",
                },
                mode="scored",
            )
        loader.assert_called_once()
        self.assertEqual(loader.call_args.kwargs["corpus"], "the measured corpus")
        self.assertTrue(loader.call_args.kwargs["require_distinctive"])

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

    def test_dual_mode_render_shows_the_holdout_gate(self):
        text = vault_evals.render(vault_evals.score_modes())
        self.assertIn("holdout", text.lower())
        self.assertIn("p3", text.lower())
        self.assertRegex(text, r"1\.0")

    def test_invalid_run_is_visible_in_report(self):
        text = vault_evals.render(vault_evals.score([]))
        self.assertIn("INVALID", text)

    def test_save_and_compare_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(vault_evals, "EVALS_DIR", str(Path(tmp) / "vault_evals")):
                self.assertIn("Need two", vault_evals.compare_latest())
                vault_evals.save({"timestamp": "2026-01-01T00:00:00", "precision": 0.5})
                vault_evals.save({"timestamp": "2026-01-02T00:00:00", "precision": 0.9})
                out = vault_evals.compare_latest()
        self.assertIn("precision", out)

    def test_compare_refuses_different_rubrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(vault_evals, "EVALS_DIR", str(Path(tmp) / "vault_evals")):
                vault_evals.save({"timestamp": "2026-01-01T00:00:00", "rubric_version": "v1"})
                vault_evals.save({"timestamp": "2026-01-02T00:00:00", "rubric_version": "v2"})
                out = vault_evals.compare_latest()
        self.assertIn("incompatible", out.lower())


class TestTuningIsAdvisory(unittest.TestCase):
    def test_tuning_returns_a_recommendation_without_writing_config(self):
        from core.vault_relevance import load_relevance_config

        before = load_relevance_config(refresh=True)
        result = vault_evals.tune(vault_evals.load_cases())
        after = load_relevance_config(refresh=True)
        self.assertTrue(result["valid"])
        self.assertIn("weights", result)
        self.assertIn("uncertain_threshold", result)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
