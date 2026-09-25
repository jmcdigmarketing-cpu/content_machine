"""Tests for the free signal backends (yt-dlp YouTube, OAuth Reddit) +
SIGNAL_BACKEND selection.

All yt-dlp/requests interaction is mocked — no network. What matters here:
  - each free fetcher emits items in the exact schema the Apify signal parses
    (YouTube: ISO datetime date WITH a 'T' — the signal's _days_since only
    parses dates carrying a time component);
  - SIGNAL_BACKEND=apify (default) preserves the pre-change behavior exactly;
  - free/auto selection works and failures degrade to inactive, never no_key
    (no_key would trip the session circuit breaker) — except a genuinely
    missing credential, where no_key is the accurate status;
  - Reddit's fetcher returns None ONLY on HTTP 429 so the signal can surface
    STATUS_RATE_LIMIT and engage the breaker's timed cooldown;
  - cost_meter stops billing a paid signal as an Apify run when it was served
    by a free backend.
"""

import unittest
from unittest.mock import MagicMock, patch

from apis import free_backends as fb
from apis import reddit_signal as rds
from apis import youtube_apify_signal as yas
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, STATUS_RATE_LIMIT
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
            # Mirrors the real signature: _full_one(url, log=None). A double that
            # only accepts (url) raises TypeError inside the caller's except and
            # silently degrades to the flat entry.
            patch.object(fb, "_full_one", side_effect=lambda url, log=None: dict(_FULL[url])),
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

    def setUp(self):
        from apis.apify_client import reset_apify_state

        reset_apify_state()

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

    def test_free_reddit_not_billed_as_apify(self):
        signals = {"reddit": {"active": True, "data": {"backend": "free"}}}
        cost = estimate_run_cost(script="hi", signals=signals)
        self.assertEqual(cost["apify"], 0.0)


def _http(status_code, payload):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


_REDDIT_CREDS = {"REDDIT_CLIENT_ID": "cid", "REDDIT_CLIENT_SECRET": "csecret"}

_REDDIT_TOKEN = {"access_token": "tok", "expires_in": 3600}

_REDDIT_LISTING = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "Pereira KOs everyone",
                    "ups": 4200,
                    "num_comments": 512,
                    "subreddit": "ufc",
                    "permalink": "/r/ufc/comments/abc/pereira/",
                }
            },
            {"data": {"title": "", "ups": 10}},  # no title → dropped
        ]
    }
}


class TestFetchRedditFree(unittest.TestCase):
    def setUp(self):
        fb.reset_reddit_token()

    def tearDown(self):
        fb.reset_reddit_token()

    def test_no_creds_returns_empty(self):
        with patch.dict("os.environ", {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}):
            self.assertEqual(fb.fetch_reddit_free("ufc", ["ufc"]), [])

    def test_maps_children_to_apify_schema(self):
        with (
            patch.dict("os.environ", _REDDIT_CREDS),
            patch.object(fb.requests, "post", return_value=_http(200, _REDDIT_TOKEN)),
            patch.object(fb.requests, "get", return_value=_http(200, _REDDIT_LISTING)) as get,
        ):
            items = fb.fetch_reddit_free("Pereira", ["ufc", "MMA"])

        self.assertEqual(len(items), 1)  # titleless child dropped
        item = items[0]
        self.assertEqual(item["title"], "Pereira KOs everyone")
        self.assertEqual(item["ups"], 4200)
        self.assertEqual(item["numComments"], 512)
        self.assertEqual(item["subreddit"], "ufc")
        self.assertEqual(item["url"], "https://www.reddit.com/r/ufc/comments/abc/pereira/")
        # Multireddit search across the given subs.
        self.assertIn("/r/ufc+MMA/search", get.call_args[0][0])

    def test_token_cached_across_calls(self):
        with (
            patch.dict("os.environ", _REDDIT_CREDS),
            patch.object(fb.requests, "post", return_value=_http(200, _REDDIT_TOKEN)) as post,
            patch.object(fb.requests, "get", return_value=_http(200, _REDDIT_LISTING)),
        ):
            fb.fetch_reddit_free("a", ["ufc"])
            fb.fetch_reddit_free("b", ["ufc"])
        post.assert_called_once()

    def test_token_failure_returns_empty(self):
        with (
            patch.dict("os.environ", _REDDIT_CREDS),
            patch.object(fb.requests, "post", return_value=_http(401, {})),
        ):
            self.assertEqual(fb.fetch_reddit_free("q", ["ufc"]), [])

    def test_429_returns_none_for_cooldown(self):
        with (
            patch.dict("os.environ", _REDDIT_CREDS),
            patch.object(fb.requests, "post", return_value=_http(200, _REDDIT_TOKEN)),
            patch.object(fb.requests, "get", return_value=_http(429, {})),
        ):
            self.assertIsNone(fb.fetch_reddit_free("q", ["ufc"]))

    def test_other_http_error_returns_empty(self):
        with (
            patch.dict("os.environ", _REDDIT_CREDS),
            patch.object(fb.requests, "post", return_value=_http(200, _REDDIT_TOKEN)),
            patch.object(fb.requests, "get", return_value=_http(500, {})),
        ):
            self.assertEqual(fb.fetch_reddit_free("q", ["ufc"]), [])

    def test_network_exception_returns_empty_never_raises(self):
        with (
            patch.dict("os.environ", _REDDIT_CREDS),
            patch.object(fb.requests, "post", return_value=_http(200, _REDDIT_TOKEN)),
            patch.object(fb.requests, "get", side_effect=OSError("net down")),
        ):
            self.assertEqual(fb.fetch_reddit_free("q", ["ufc"]), [])


_REDDIT_FREE_ITEMS = [
    {
        "title": "Pereira UFC 320 megathread",
        "ups": 3000,
        "numComments": 400,
        "subreddit": "ufc",
        "url": "https://www.reddit.com/r/ufc/comments/xyz/",
    }
]

_REDDIT_ACTOR_ITEMS = [
    {
        "title": "Pereira UFC 320 odds",
        "ups": 900,
        "numComments": 120,
        "subreddit": "MMA",
        "url": "https://www.reddit.com/r/MMA/comments/apify/",
    }
]


class TestRedditBackendSelection(unittest.TestCase):
    """SIGNAL_BACKEND routing inside get_reddit_signal."""

    def test_default_apify_path_unchanged(self):
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "", "APIFY_CONTENT_MACHINE_KEY": "k"}),
            patch.object(rds, "run_actor", return_value=list(_REDDIT_ACTOR_ITEMS)) as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_called_once()
        self.assertTrue(sig["active"])
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertEqual(sig["data"]["backend"], "apify")

    def test_apify_disabled_degrades_to_free_reddit(self):
        # A dead Apify key this session must fall back to the free OAuth backend, not
        # return inactive after a slow actor timeout (default SIGNAL_BACKEND=apify).
        with (
            patch.dict(
                "os.environ",
                {"SIGNAL_BACKEND": "apify", "APIFY_CONTENT_MACHINE_KEY": "k", **_REDDIT_CREDS},
            ),
            patch("apis.apify_client.apify_disabled", return_value=True),
            patch.object(rds, "fetch_reddit_free", return_value=list(_REDDIT_FREE_ITEMS)),
            patch.object(rds, "run_actor") as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_not_called()  # no Apify actor wait when the key is dead
        self.assertEqual(sig["data"]["backend"], "free")
        self.assertTrue(sig["active"])

    def test_default_apify_no_key_returns_no_key(self):
        with patch.dict("os.environ", {"SIGNAL_BACKEND": "", "APIFY_CONTENT_MACHINE_KEY": ""}):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        self.assertFalse(sig["connected"])
        self.assertEqual(sig["status"], STATUS_NO_KEY)

    def test_free_backend_needs_no_apify_key(self):
        with (
            patch.dict(
                "os.environ",
                {"SIGNAL_BACKEND": "free", "APIFY_CONTENT_MACHINE_KEY": "", **_REDDIT_CREDS},
            ),
            patch.object(rds, "fetch_reddit_free", return_value=list(_REDDIT_FREE_ITEMS)),
            patch.object(rds, "run_actor") as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_not_called()
        self.assertTrue(sig["active"])
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertEqual(sig["data"]["backend"], "free")
        self.assertEqual(sig["data"]["posts"][0]["comments"], 400)

    def test_free_missing_creds_is_no_key(self):
        # A genuinely missing credential: no_key is accurate (breaker trip wanted).
        with (
            patch.dict(
                "os.environ",
                {
                    "SIGNAL_BACKEND": "free",
                    "REDDIT_CLIENT_ID": "",
                    "REDDIT_CLIENT_SECRET": "",
                    "APIFY_CONTENT_MACHINE_KEY": "k",
                },
            ),
            patch.object(rds, "run_actor") as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_not_called()
        self.assertEqual(sig["status"], STATUS_NO_KEY)
        self.assertIn("REDDIT_CLIENT_ID", sig["status_detail"])

    def test_free_rate_limited_surfaces_rate_limit_status(self):
        with (
            patch.dict("os.environ", {"SIGNAL_BACKEND": "free", **_REDDIT_CREDS}),
            patch.object(rds, "fetch_reddit_free", return_value=None),
            patch.object(rds, "run_actor") as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_not_called()
        self.assertEqual(sig["status"], STATUS_RATE_LIMIT)
        self.assertTrue(sig["connected"])

    def test_free_empty_is_inactive_no_fallback(self):
        with (
            patch.dict(
                "os.environ",
                {"SIGNAL_BACKEND": "free", "APIFY_CONTENT_MACHINE_KEY": "k", **_REDDIT_CREDS},
            ),
            patch.object(rds, "fetch_reddit_free", return_value=[]),
            patch.object(rds, "run_actor") as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_not_called()
        self.assertEqual(sig["status"], STATUS_INACTIVE)

    def test_auto_falls_back_to_apify_when_free_empty(self):
        with (
            patch.dict(
                "os.environ",
                {"SIGNAL_BACKEND": "auto", "APIFY_CONTENT_MACHINE_KEY": "k", **_REDDIT_CREDS},
            ),
            patch.object(rds, "fetch_reddit_free", return_value=[]),
            patch.object(rds, "run_actor", return_value=list(_REDDIT_ACTOR_ITEMS)) as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_called_once()
        self.assertTrue(sig["active"])
        self.assertEqual(sig["data"]["backend"], "apify")

    def test_auto_falls_back_to_apify_when_rate_limited(self):
        with (
            patch.dict(
                "os.environ",
                {"SIGNAL_BACKEND": "auto", "APIFY_CONTENT_MACHINE_KEY": "k", **_REDDIT_CREDS},
            ),
            patch.object(rds, "fetch_reddit_free", return_value=None),
            patch.object(rds, "run_actor", return_value=list(_REDDIT_ACTOR_ITEMS)) as ra,
        ):
            sig = rds.get_reddit_signal("Pereira UFC 320", "tapin")
        ra.assert_called_once()
        self.assertEqual(sig["data"]["backend"], "apify")


if __name__ == "__main__":
    unittest.main()
