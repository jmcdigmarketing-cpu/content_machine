"""Tests for historical feature backfill."""

import json
import unittest
from unittest.mock import MagicMock, patch

from analytics import backfill_features as bf


class _Run:
    def __init__(self, id, title, script, features="{}", timings='{"length_preset": "2"}'):
        self.id = id
        self.title = title
        self.script_preview = script
        self.selected_topic = title
        self.input_topic = title
        self.features_json = features
        self.timings_json = timings


class TestBackfill(unittest.TestCase):
    def test_backfills_runs_missing_features(self):
        repo = MagicMock()
        repo.list_for_channel.return_value = [
            _Run(1, "Top 5 UFC upsets", "He lost it all. Then more."),
            _Run(2, "Already done", "x", features='{"feature_version": "v1"}'),
        ]
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            n = bf.backfill_channel("tapin")

        self.assertEqual(n, 1)  # only run 1 (run 2 already has features)
        run_id, data = repo.update.call_args[0]
        self.assertEqual(run_id, 1)
        features = json.loads(data["features_json"])
        self.assertEqual(features["title_structure"], "listicle")
        self.assertEqual(features["fact_source"], "backfilled")

    def test_force_recomputes_all(self):
        repo = MagicMock()
        repo.list_for_channel.return_value = [
            _Run(1, "A title", "x", features='{"feature_version": "v1"}'),
        ]
        with unittest.mock.patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            n = bf.backfill_channel("tapin", force=True)
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
