import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from analytics.competitor_context import (
    get_competitor_prompt_block,
    is_snapshot_stale,
    list_recent_competitor_titles,
)


class TestCompetitorContext(unittest.TestCase):
    def test_stale_when_missing(self):
        with patch(
            "analytics.competitor_context.competitors_data_path",
            return_value="/nonexistent/path.json",
        ):
            self.assertTrue(is_snapshot_stale("tapin"))

    def test_list_titles_filters_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "competitors_tapin.json")
            payload = {
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "competitors": [
                    {
                        "label": "Test",
                        "recent_videos": [
                            {"title": "Rams trade for Myles Garrett", "published_at": ""},
                            {"title": "Unrelated cooking video", "published_at": ""},
                        ],
                    }
                ],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            with patch(
                "analytics.competitor_context.competitors_data_path",
                return_value=path,
            ):
                with patch(
                    "analytics.competitor_context.load_competitor_snapshot",
                    side_effect=lambda c: json.load(open(path, encoding="utf-8")),
                ):
                    rows = list_recent_competitor_titles(
                        "tapin", topic="Rams Myles Garrett", limit=5
                    )
                    self.assertEqual(len(rows), 1)
                    self.assertIn("Garrett", rows[0]["title"])


if __name__ == "__main__":
    unittest.main()
