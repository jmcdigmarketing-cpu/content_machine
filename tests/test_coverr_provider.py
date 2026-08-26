"""A1: Coverr stock provider — fail-open without a key, fake requests only."""

from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from config.settings import get_settings
from config.validate_channels import validate_channel


class TestCoverrGating(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()

    def tearDown(self):
        get_settings.cache_clear()

    def test_unconfigured_without_key(self):
        from assets.coverr_provider import CoverrAssetProvider

        with patch.dict(os.environ, {"COVERR_API_KEY": ""}, clear=False):
            self.assertFalse(CoverrAssetProvider().is_configured())
            self.assertIsNone(CoverrAssetProvider().find_video("GTA 6 leak", "gaming"))

    def test_no_key_emits_no_warning(self):
        from assets.coverr_provider import CoverrAssetProvider

        with (
            patch.dict(os.environ, {"COVERR_API_KEY": ""}, clear=False),
            self.assertNoLogs("content_machine.assets", level=logging.WARNING),
        ):
            CoverrAssetProvider().find_video("GTA 6 leak", "gaming")

    def test_not_in_chain_without_key(self):
        from assets import manager

        with patch.dict(os.environ, {"COVERR_API_KEY": ""}, clear=False):
            names = [p.name for p in manager._provider_chain("tapin")]
        self.assertNotIn("coverr", names)
        self.assertIn("local", names)


class TestCoverrSearch(unittest.TestCase):
    def test_find_video_skips_faces_and_downloads_vertical(self):
        from assets.coverr_provider import CoverrAssetProvider

        payload = {
            "hits": [
                {
                    "id": "face1",
                    "title": "Smiling Couple Plays a Video Game",
                    "description": "a happy couple",
                    "tags": ["couple", "girl", "smiling"],
                    "is_vertical": True,
                    "urls": {"mp4_download": "https://example.com/face.mp4"},
                },
                {
                    "id": "ok1",
                    "title": "Empty neon arcade cabinets",
                    "description": "no people, just cabinets",
                    "tags": ["arcade", "neon", "cabinets"],
                    "is_vertical": True,
                    "urls": {"mp4_download": "https://example.com/ok.mp4"},
                },
            ]
        }
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = payload
        dest = os.path.join("assets", "cache", "coverr_ok1.mp4")

        with (
            patch.dict(os.environ, {"COVERR_API_KEY": "test-coverr-key"}, clear=False),
            patch("assets.coverr_provider.find_cached", return_value=None),
            patch("assets.coverr_provider.requests.get", return_value=response) as get,
            patch("assets.coverr_provider.download_file", return_value=dest) as dl,
            patch("assets.coverr_provider.register") as reg,
            patch("assets.category.search_query", return_value="gta leak"),
        ):
            result = CoverrAssetProvider().find_video("GTA 6 leak", "gaming")

        self.assertIsNotNone(result)
        self.assertEqual(result.provider, "coverr")
        self.assertEqual(result.source_id, "ok1")
        called_url = get.call_args.args[0]
        self.assertEqual(called_url, "https://api.coverr.co/videos")
        self.assertEqual(get.call_args.kwargs["params"]["query"], "gta leak")
        self.assertEqual(get.call_args.kwargs["params"]["urls"], "true")
        auth = get.call_args.kwargs["headers"]["Authorization"]
        self.assertTrue(auth.startswith("Bearer "))
        dl.assert_called_once()
        self.assertEqual(dl.call_args.args[0], "https://example.com/ok.mp4")
        reg.assert_called_once()

    def test_registered_in_manager(self):
        from assets import manager

        self.assertIn("coverr", manager._PROVIDERS)


class TestCoverrShippedConfig(unittest.TestCase):
    def test_both_channels_list_coverr_after_stock(self):
        from config.validate_channels import _load_raw

        raw = _load_raw()
        channels = raw.get("channels", raw)
        for channel_id in ("tapin", "moneywise"):
            order = [str(p).lower() for p in channels[channel_id]["asset_provider_order"]]
            self.assertIn("coverr", order, channel_id)
            self.assertLess(order.index("local"), order.index("coverr"))

    def test_coverr_is_an_allowed_provider_name(self):
        errors, _ = validate_channel(
            "tapin",
            {"asset_provider_order": ["local", "coverr", "pexels", "pixabay"]},
        )
        self.assertFalse(any("asset_provider_order" in e for e in errors), errors)

    def test_settings_default_order_includes_coverr(self):
        import inspect

        from config import settings as settings_mod

        source = inspect.getsource(settings_mod.Settings)
        self.assertIn("local,pexels,pixabay,coverr", source)


if __name__ == "__main__":
    unittest.main()
