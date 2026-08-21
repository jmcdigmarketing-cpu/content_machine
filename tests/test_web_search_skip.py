"""Skip web_search when vault facts already clear the density bar."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.web_search_skip import should_skip_web_search


class TestWebSearchSkip(unittest.TestCase):
    def test_empty_vault_never_skips(self):
        # tests/__init__.py clears OBSIDIAN_VAULT_PATH — live vault cannot leak in.
        self.assertFalse(should_skip_web_search("UFC 320 Topuria", "tapin"))

    def test_dense_vault_skips(self):
        facts = [f"fact {i} distinctive token" for i in range(6)]
        with (
            patch.dict(os.environ, {"WEB_SEARCH_SKIP_MIN_FACTS": "6"}, clear=False),
            patch("core.obsidian_facts.load_facts", return_value=facts),
        ):
            self.assertTrue(should_skip_web_search("topic", "tapin"))

    def test_thin_vault_does_not_skip(self):
        with (
            patch.dict(os.environ, {"WEB_SEARCH_SKIP_MIN_FACTS": "6"}, clear=False),
            patch("core.obsidian_facts.load_facts", return_value=["one fact"]),
        ):
            self.assertFalse(should_skip_web_search("topic", "tapin"))

    def test_off_never_skips(self):
        facts = [f"fact {i}" for i in range(20)]
        with (
            patch.dict(os.environ, {"WEB_SEARCH_SKIP_MIN_FACTS": "off"}, clear=False),
            patch("core.obsidian_facts.load_facts", return_value=facts),
        ):
            self.assertFalse(should_skip_web_search("topic", "tapin"))

    def test_register_signals_drops_web_search(self):
        from apis import register_signals as rs

        env = {"CONTENT_SKIP_SIGNALS": ""}
        with (
            patch.dict(os.environ, env, clear=False),
            patch("core.web_search_skip.should_skip_web_search", return_value=True),
        ):
            names = {n for n, _ in rs._active_signal_sources("UFC 320", "tapin")}
        self.assertNotIn("web_search", names)

    def test_register_signals_keeps_web_search_when_thin(self):
        from apis import register_signals as rs

        env = {"CONTENT_SKIP_SIGNALS": ""}
        with (
            patch.dict(os.environ, env, clear=False),
            patch("core.web_search_skip.should_skip_web_search", return_value=False),
        ):
            names = {n for n, _ in rs._active_signal_sources("UFC 320", "tapin")}
        self.assertIn("web_search", names)


if __name__ == "__main__":
    unittest.main()
