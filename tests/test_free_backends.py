"""Tests for the free (yt-dlp) YouTube backend + SIGNAL_BACKEND selection.

All yt-dlp interaction is mocked — no network. What matters here:
  - the free fetcher emits items in the exact schema the Apify signal parses,
    including an ISO datetime date WITH a 'T' (the signal's _days_since only
    parses dates carrying a time component);
  - SIGNAL_BACKEND=apify (default) preserves the pre-change behavior exactly;
  - free/auto selection works and failures degrade to inactive, never no_key
    (no_key would trip the session circuit breaker);
  - cost_meter stops billing youtube_competitors as an Apify run when it was
    served by the free backend.
"""

import unittest
from unittest.mock import patch

from apis import free_backends as fb
from apis import youtube_apify_signal as yas
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK
from core.cost_meter import estimate_run_cost

_FLAT = [
    {"url": "https://youtu.be/low", "title": "Low views", "view_count": 100, "channel": "c1"},
    {"url": "https://youtu.be/hot", "title": "Hot video", "view_count": 9_000, "channel": "c2"},
]

_FULL = {
    "https://youtu.be/hot": {
        "title": "Hot video (full)",
        "view_count": 9_500,
        "upload_date": "20260601",
        "channel": "Channel Two",
        "duration": 45,
        "webpage_url": "https://www.youtube.com/watch?v=hot",
    },
    "https://youtu.be/low": {
        "title": "Low views (full)",
        "view_count": 120,
        "upload_date": "20260101",
        "channel": "Channel One",
        "duration": 30,
        "webpage_url": "https://www.youtube.com/watch?v=low",
    },
}

_APIFY_ITEMS = [
    {
        "title": "Apify video",
        "viewCount": 50_000,
        "date": "2026-06-20T00:00:00.000Z",
        "channelName": "Comp Channel",
        "duration": "00:00:40",
        "url": "https://www.youtube.com/watch?v=apify",
    }
]


class TestIsoDate(unittest.TestCase):
    def test_yyyymmdd_becomes_iso_datetime_with_t(self):
        out = fb._iso_date("20260601")
        self.assertEqual(out, "2026-06-01T12:00:00")
        # _days_since only parses dates containing 'T' — this is load-bearing.
        self.assertIn("T", out)

    def test_invalid_inputs_return_none(self):
        for bad in (None, "", "2026-06-01", "junk", "202606"):
            self.assertIsNone(fb._iso_date(bad))

    def test_iso_date_feeds_days_since_correctly(self):
        # End-to-end: the emitted date must NOT fall into the 30.0-day default.
        age = yas._days_since(fb._iso_date("20260601"))
        self.assertNotAlmostEqual(age, 30.0, places=1)
        self.assertGreater(age, 1.0)


class TestFetchYoutubeFree(unittest.TestCase):
    def test_maps_fields_to_apify_schema(self):
        with (
            patch.object(fb, "youtube_available", return_value=True),
            patch.object(fb, "_flat_search", return_value=list(_FLAT)),
            patch.object(fb, "_full_one", side_effect=lambda url: dict(_FULL[url])),
        ):
            items = fb.fetch_youtube_free("test query", top_n=2, search_n=5)

        self.assertEqual(len(items), 2)
        # Ranked by flat view_count desc → hot first.
        hot = items[0]
        self.assertEqual(hot["title"], "Hot video (full)")
        self.assertEqual(hot["viewCount"], 9_500)
        self.assertEqual(hot["date"], "2026-06-01T12:00:00")
        self.assertEqual(hot["channelName"], "Channel Two")
        self.assertEqual(hot["duration"], 45)
        self.assertEqual(hot["url"], "https://www.youtube.com/watch?v=hot")
        # Exactly the keys the Apify signal parses.
        self.assertEqual(set(hot), {"title", "viewCount", "date", "channelName", "duration", "url"})

    def test_unavailable_returns_empty(self):
        with patch.object(fb, "youtube_available", return_value=False):
            self.assertEqual(fb.fetch_youtube_free("anything"), [])

    def test_flat_search_error_returns_empty_never_raises(self):
        with (
            patch.object(fb, "youtube_available", return_value=True),
            patch.object(fb, "_flat_search", side_effect=RuntimeError("network down")),
        ):
            self.assertEqual(fb.fetch_youtube_free("anything"), [])

    def test_full_extract_failure_falls_back_to_flat_fields(self):
        with (
            patch.object(fb, "youtube_available", return_value=True),
            patch.object(fb, "_flat_search", return_value=list(_FLAT)),
            patch.object(fb, "_full_one", side_effect=RuntimeError("timeout")),
        ):
            items = fb.fetch_youtube_free("q", top_n=1, search_n=5)
        self.assertEqual(items[0]["title"], "Hot video")
        self.assertEqual(items[0]["viewCount"], 9_000)
        self.assertIsNone(items[0]["date"])  # no upload_date in flat mode

    def test_env_overrides_parsed(self):
        with patch.dict("os.environ", {"YT_FREE_TOP_N": "3", "YT_FREE_SEARCH_N": "7"}):
            self.assertEqual(fb._yt_top_n(), 3)
            self.assertEqual(fb._yt_search_n(), 7)
        with patch.dict("os.environ", {"YT_FREE_TOP_N": "junk"}):
            self.assertEqual(fb._yt_top_n(), 5)


class TestBackendSelection(unittest.TestCase):
    """SIGNAL_BACKEND routing inside get_youtube_apify_signal."""

    def test_default_apify_no_key_returns_no_key(self):
        # Default backend + no Apify key = the exact pre-change behavior.
        with patch.dict("os.environ", {"SIGNAL_BACKEND": "", "APIFY_CONTENT_MACHINE_KEY": ""}):
            sig = yas.get_youtube_apify_signal("some topic")
        self.assertFalse(sig["connected"])
        self.assertEqual(sig["status"], STATUS_NO_KEY)

    def test_default_apify_path_tags_backend_apify(self):
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "", "APIFY_CONTENT_MACHINE_KEY": "k"}),
            patch.object(yas, "get_source", return_value={"actor": "a/b", "ttl_seconds": 60}),
            patch.object(yas, "build_input", return_value={}),
            patch.object(yas, "run_actor", return_value=list(_APIFY_ITEMS)) as ra,
        ):
            sig = yas.get_youtube_apify_signal("some topic")
        ra.assert_called_once()
        self.assertTrue(sig["active"])
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertEqual(sig["data"]["backend"], "apify")

    def test_free_backend_needs_no_apify_key(self):
        free_items = [
            {
                "title": "Free video",
                "viewCount": 200_000,
                "date": "2026-06-25T12:00:00",
                "channelName": "Free Channel",
                "duration": 50,
                "url": "https://www.youtube.com/watch?v=free",
            }
        ]
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "free", "APIFY_CONTENT_MACHINE_KEY": ""}),
            patch.object(yas, "youtube_available", return_value=True),
            patch.object(yas, "fetch_youtube_free", return_value=free_items),
            patch.object(yas, "run_actor") as ra,
        ):
            sig = yas.get_youtube_apify_signal("some topic")
        ra.assert_not_called()
        self.assertTrue(sig["active"])
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertEqual(sig["data"]["backend"], "free")
        self.assertGreater(sig["data"]["top_velocity"], 0)

    def test_free_backend_empty_is_inactive_not_no_key(self):
        # STATUS_NO_KEY would trip the session circuit breaker — must be inactive.
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "free", "APIFY_CONTENT_MACHINE_KEY": ""}),
            patch.object(yas, "youtube_available", return_value=True),
            patch.object(yas, "fetch_youtube_free", return_value=[]),
            patch.object(yas, "run_actor") as ra,
        ):
            sig = yas.get_youtube_apify_signal("some topic")
        ra.assert_not_called()
        self.assertTrue(sig["connected"])
        self.assertEqual(sig["status"], STATUS_INACTIVE)

    def test_auto_falls_back_to_apify_when_free_empty(self):
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "auto", "APIFY_CONTENT_MACHINE_KEY": "k"}),
            patch.object(yas, "youtube_available", return_value=True),
            patch.object(yas, "fetch_youtube_free", return_value=[]),
            patch.object(yas, "get_source", return_value={"actor": "a/b", "ttl_seconds": 60}),
            patch.object(yas, "build_input", return_value={}),
            patch.object(yas, "run_actor", return_value=list(_APIFY_ITEMS)) as ra,
        ):
            sig = yas.get_youtube_apify_signal("some topic")
        ra.assert_called_once()
        self.assertTrue(sig["active"])
        self.assertEqual(sig["data"]["backend"], "apify")

    def test_auto_prefers_free_when_it_delivers(self):
        free_items = [
            {
                "title": "Free wins",
                "viewCount": 10_000,
                "date": "2026-06-25T12:00:00",
                "channelName": "c",
                "duration": 40,
                "url": "u",
            }
        ]
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "auto", "APIFY_CONTENT_MACHINE_KEY": "k"}),
            patch.object(yas, "youtube_available", return_value=True),
            patch.object(yas, "fetch_youtube_free", return_value=free_items),
            patch.object(yas, "run_actor") as ra,
        ):
            sig = yas.get_youtube_apify_signal("some topic")
        ra.assert_not_called()
        self.assertEqual(sig["data"]["backend"], "free")


class TestCostMeterBackendAware(unittest.TestCase):
    def test_free_youtube_not_billed_as_apify(self):
        signals = {
            "youtube_competitors": {"active": True, "data": {"backend": "free"}},
        }
        cost = estimate_run_cost(script="hi", signals=signals)
        self.assertEqual(cost["apify"], 0.0)

    def test_apify_youtube_still_billed(self):
        signals = {
            "youtube_competitors": {"active": True, "data": {"backend": "apify"}},
        }
        cost = estimate_run_cost(script="hi", signals=signals)
        self.assertGreater(cost["apify"], 0.0)

    def test_missing_backend_key_defaults_to_billed(self):
        # Legacy signal dicts (no backend marker) must keep counting — the other
        # three paid signals never set data.backend.
        signals = {
            "reddit": {"active": True},
            "youtube_competitors": {"active": True, "data": None},
        }
        cost = estimate_run_cost(script="hi", signals=signals)
        # Two billed runs: reddit + youtube (data=None → treated as apify).
        self.assertAlmostEqual(cost["apify"], 2 * 0.02, places=4)


if __name__ == "__main__":
    unittest.main()
