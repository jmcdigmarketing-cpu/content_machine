import json
import os
import tempfile
import unittest
from unittest.mock import patch

from apis.learned_weights import compute_profile_from_performance
from apis.topic_scorer import get_weights, infer_domain


class TestTopicScorerLearning(unittest.TestCase):
    def test_infer_gaming_topic(self):
        self.assertEqual(infer_domain("Marvel Rivals meta dead", "tapin"), "gaming")

    @patch("apis.topic_scorer.get_performance_memory_repository")
    @patch("apis.topic_scorer.compute_profile_from_performance", return_value=None)
    def test_tapin_overrides_suppress_sports(self, _profile, mock_repo):
        mock_repo.return_value.has_outcome_data.return_value = False
        mock_repo.return_value.get_domain_average.return_value = 1.0
        mock_repo.return_value.get_domain_engagement_average.return_value = 0.0
        weights = get_weights("gaming", "tapin")
        self.assertEqual(weights.get("sports", 0), 0.0)
        self.assertEqual(weights.get("live_scores", 0), 0.0)
        self.assertGreater(weights.get("rawg", 0), 0.1)

    def test_nba_weights_deemphasize_live_scores_in_profile(self):
        weights = get_weights("nba", "default")
        self.assertLessEqual(weights.get("live_scores", 0), 0.1)

    def test_learned_profile_from_performance_memory(self):
        entries = []
        for _i in range(6):
            entries.append(
                {
                    "domain": "gaming",
                    "engaged_rate": 0.28,
                    "alignment_score": 28.0,
                    "source": "tapin_seed",
                }
            )
        for _i in range(4):
            entries.append(
                {
                    "domain": "ufc",
                    "engaged_rate": 0.26,
                    "alignment_score": 26.0,
                    "source": "tapin_seed",
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = os.path.join(tmp, "performance_memory")
            os.makedirs(mem_dir, exist_ok=True)
            path = os.path.join(mem_dir, "tapin.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entries, f)

            import storage.repositories.performance_memory as pm

            with (
                patch("storage.repositories.performance_memory.MEMORY_DIR", mem_dir),
                patch(
                    "storage.repositories.performance_memory.MEMORY_FILE",
                    os.path.join(tmp, "unused.json"),
                ),
                patch(
                    "storage.repositories.performance_memory.postgres_authoritative",
                    return_value=False,
                ),
            ):
                pm._repo = None
                profile = compute_profile_from_performance("tapin", min_entries=8)
                self.assertIsNotNone(profile)
                self.assertGreater(profile.get("rawg", 0), 0.1)
                pm._repo = None


if __name__ == "__main__":
    unittest.main()
