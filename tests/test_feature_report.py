"""#357: which recorded run features move with the outcome - measured, not acted on.

`core/run_features.build_features` records a dozen features per run (hook length, word
count, key-fact count, angle, title structure, fact source ...) and nothing ever tested
one against engaged rate. `ops feature-report` does: Pearson r for numeric and boolean
features with the n that would make it significant (`grade_calibration`), per-level means
for categorical ones. Report-only: no weight, gate or default changes from it (the #739
rule - measure, then decide). Under five measured runs a feature says "collecting".
"""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


def _run(run_id: int, features: dict) -> ContentRunRecord:
    return ContentRunRecord(
        id=run_id, channel_id="tapin", input_topic="t", selected_topic="t", status="published",
        composite_score=60.0, features_json=json.dumps(features),
    )  # fmt: skip


RUNS = [
    _run(1, {"word_count": 120, "key_facts_count": 2, "angle": "news", "title": "a", "hook_words": 8}),
    _run(2, {"word_count": 140, "key_facts_count": 4, "angle": "news", "title": "b", "hook_words": 9}),
    _run(3, {"word_count": 160, "key_facts_count": 6, "angle": "ranking", "title": "c", "hook_words": 7}),
    _run(4, {"word_count": 180, "key_facts_count": 8, "angle": "ranking", "title": "d", "hook_words": 8}),
    _run(5, {"word_count": 200, "key_facts_count": 10, "angle": "news", "title": "e", "hook_words": 9}),
    _run(6, {"word_count": 220, "key_facts_count": 12, "angle": "ranking", "title": "f"}),
]  # fmt: skip
RATES = {1: 0.10, 2: 0.15, 3: 0.20, 4: 0.25, 5: 0.30, 6: 0.35}


class _Case(unittest.TestCase):
    def setUp(self):
        class _Repo:
            def list_for_channel(self, channel_id, *, status=None):
                return RUNS

        self.stack = ExitStack()
        self.stack.enter_context(
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=_Repo(),
            )
        )
        self.stack.enter_context(
            patch("core.engagement_predictor.run_engagement_map", return_value=dict(RATES))
        )

    def tearDown(self):
        self.stack.close()


class ImportanceTests(_Case):
    def test_numeric_features_get_r_and_n(self):
        from core.predictions.features import feature_importance

        found = {f.name: f for f in feature_importance("tapin")}
        self.assertAlmostEqual(found["word_count"].r, 1.0, places=3)
        self.assertEqual(found["word_count"].n, 6)
        self.assertEqual(found["hook_words"].n, 5)

    def test_text_and_ids_are_not_features(self):
        from core.predictions.features import feature_importance

        names = {f.name for f in feature_importance("tapin")}
        self.assertNotIn("title", names)

    def test_categorical_features_get_level_means(self):
        from core.predictions.features import feature_importance

        angle = next(f for f in feature_importance("tapin") if f.name == "angle")
        self.assertEqual(angle.kind, "categorical")
        self.assertEqual(angle.levels["news"][1], 3)
        self.assertAlmostEqual(angle.levels["news"][0], (0.10 + 0.15 + 0.30) / 3)

    def test_sorted_by_strength(self):
        from core.predictions.features import feature_importance

        numeric = [f for f in feature_importance("tapin") if f.kind == "numeric"]
        self.assertEqual(numeric[0].name, "key_facts_count")  # |r| ties break by name
        self.assertGreaterEqual(abs(numeric[0].r), abs(numeric[-1].r or 0))


class ReportTests(_Case):
    def test_the_report_says_significance_plainly(self):
        from core.predictions.features import report_lines

        text = "\n".join(report_lines("tapin"))
        self.assertIn("word_count", text)
        self.assertIn("r=+1.00", text)
        self.assertIn("report-only", text)

    def test_few_runs_say_collecting(self):
        from core.predictions.features import report_lines

        with patch("core.engagement_predictor.run_engagement_map", return_value={1: 0.1, 2: 0.2}):
            text = "\n".join(report_lines("tapin"))
        self.assertIn("collecting", text)
        self.assertNotIn("r=", text)

    def test_the_verb(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["feature-report"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("Feature report", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
