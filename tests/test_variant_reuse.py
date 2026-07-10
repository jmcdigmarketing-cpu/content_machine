"""Variant-scoring signal reuse defaults (apis/register_signals).

Efficiency regression: only youtube + the Apify actors were pinned during per-variant
scoring (and a stale .env override pinned only youtube), so signals re-fetched x5
variants — 150-185s of scoring per run, 5x web-search spend, Wikipedia 429 cooldowns.
All signals now pin by default; VARIANT_REUSE_SIGNALS still overrides per-call.
"""

import os
import unittest
from unittest.mock import patch

from apis.register_signals import _VARIANT_REUSE_DEFAULT, _variant_reuse


class TestVariantReuseDefaults(unittest.TestCase):
    def test_default_pins_all_slow_or_paid_signals(self):
        with patch.dict(os.environ, {"VARIANT_REUSE_SIGNALS": _VARIANT_REUSE_DEFAULT}, clear=False):
            pinned = set(_variant_reuse())
        expected = {
            # original pins
            "youtube",
            "reddit",
            "twitter",
            "tiktok_trends",
            "youtube_competitors",
            # previously re-fetched x5 per run
            "web_search",
            "wikipedia",
            "trends",
            "news",
            "blog_rss",
            "twitch",
            "rawg",
            "steam",
            "igdb",
            "trendingnow",
            "autocomplete",
        }
        self.assertTrue(expected.issubset(pinned))

    def test_env_override_narrows_the_pin_set(self):
        with patch.dict(os.environ, {"VARIANT_REUSE_SIGNALS": "youtube, twitch"}, clear=False):
            self.assertEqual(_variant_reuse(), ("youtube", "twitch"))


if __name__ == "__main__":
    unittest.main()
