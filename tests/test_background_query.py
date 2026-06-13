import os
import unittest
from unittest.mock import patch

from assets.background_query import (
    is_abstract_stock_text,
    resolve_background_query,
)


class TestBackgroundQuery(unittest.TestCase):
    @patch.dict(os.environ, {"BACKGROUND_QUERY_LLM": "false"}, clear=False)
    def test_nba_vague_topic_gets_concrete_query(self):
        resolve_background_query.cache_clear()
        q = resolve_background_query("trendy nba finals video for 2026", "sports", "tapin")
        self.assertTrue(any(w in q.lower() for w in ("basketball", "nba", "arena", "game")))
        self.assertFalse(is_abstract_stock_text(q))

    def test_detect_abstract_tags(self):
        self.assertTrue(is_abstract_stock_text("cinematic fog bokeh overlay"))
        self.assertFalse(is_abstract_stock_text("nba basketball court"))


if __name__ == "__main__":
    unittest.main()
