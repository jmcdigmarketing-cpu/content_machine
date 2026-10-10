"""#1048 the higher of two thumbnail scores becomes the pick.

The operator command ``pick-thumbnail`` still overwrites that pick. Scores here
are numbers the test supplies. Nothing calls a vision API.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from assets.thumbnail_scorer import choose_higher_thumbnail


class TestHigherScoreBecomesThePick(unittest.TestCase):
    def test_the_higher_score_is_written_as_the_pick(self):
        with tempfile.TemporaryDirectory() as tmp:
            low = os.path.join(tmp, "text_on.jpg")
            high = os.path.join(tmp, "face_forward.jpg")
            for path in (low, high):
                with open(path, "wb") as handle:
                    handle.write(b"jpeg")
            candidates = [
                {"path": low, "arm": "text_on", "provider": "pillow", "features": {}},
                {
                    "path": high,
                    "arm": "face_forward",
                    "provider": "pillow",
                    "features": {},
                },
            ]
            features = {"thumbnail_candidates": candidates, "channel_id": "tapin"}
            with (
                patch("core.run_features.load_features", return_value=features),
                patch("core.run_features.merge_features") as merge,
                patch("core.experiments.record_assignment"),
                patch("storage.repositories.assets.get_asset_repository") as assets,
                patch("assets.thumbnail_scorer.score_thumbnail") as vision,
            ):
                assets.return_value.create.return_value = SimpleNamespace(id=1)
                chosen = choose_higher_thumbnail(
                    71,
                    candidates,
                    topic="Knicks",
                    channel_id="tapin",
                    scores={low: 22.0, high: 81.0},
                )
            vision.assert_not_called()
            self.assertEqual(os.path.abspath(chosen["path"]), os.path.abspath(high))
            payload = merge.call_args[0][1]
            self.assertEqual(
                os.path.abspath(payload["thumbnail_pick"]["path"]),
                os.path.abspath(high),
            )

    def test_an_operator_pick_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            kept = os.path.join(tmp, "kept.jpg")
            other = os.path.join(tmp, "other.jpg")
            for path in (kept, other):
                with open(path, "wb") as handle:
                    handle.write(b"jpeg")
            candidates = [
                {"path": kept, "arm": "text_on", "provider": "pillow"},
                {"path": other, "arm": "face_forward", "provider": "pillow"},
            ]
            features = {
                "thumbnail_candidates": candidates,
                "thumbnail_pick": {"path": kept},
            }
            with (
                patch("core.run_features.load_features", return_value=features),
                patch("core.run_features.merge_features") as merge,
            ):
                chosen = choose_higher_thumbnail(
                    71,
                    candidates,
                    topic="Knicks",
                    channel_id="tapin",
                    scores={kept: 10.0, other: 99.0},
                )
            self.assertIsNone(chosen)
            merge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
