"""Feed health checker + the RSS parser fixes behind it.

Context: on 2026-08-14 an audit found 11 of ~37 configured feeds dead and one *live*
feed (Federal Reserve) silently dropped by a BOM parse error — invisible for over a
month because a failed feed is indistinguishable from a quiet news day. These tests
pin the three distinctions that make rot visible: parses vs doesn't, alive vs stale,
and reachable vs dead.

No network: every fetch is mocked (tests/CLAUDE.md).
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch

from apis.rss_feeds import _parse_feed_xml, decode_feed_bytes
from core import feed_health


def _rss(*, items, encoding="utf-8", bom=False):
    """Build a small RSS document, optionally BOM-prefixed like federalreserve.gov."""
    body = "".join(
        f"<item><title>{t}</title><link>https://x/{i}</link>"
        f"<pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for i, (t, d) in enumerate(items)
    )
    doc = f'<?xml version="1.0" encoding="{encoding}" ?><rss version="2.0"><channel>{body}</channel></rss>'
    raw = doc.encode(encoding)
    return (b"\xef\xbb\xbf" + raw) if bom else raw


def _resp(status=200, raw=b""):
    r = MagicMock()
    r.status_code = status
    r.content = raw
    return r


class TestBomDecoding(unittest.TestCase):
    """The Federal Reserve regression: valid RSS lost to a UTF-8 BOM."""

    def setUp(self):
        self.items = [("Fed raises rates", datetime.now(timezone.utc))]

    def test_bom_feed_parses(self):
        raw = _rss(items=self.items, bom=True)
        self.assertEqual(len(_parse_feed_xml(decode_feed_bytes(raw))), 1)

    def test_bom_feed_was_previously_dropped(self):
        # Pins WHY the helper exists: naive str decoding still fails on byte 0.
        raw = _rss(items=self.items, bom=True)
        self.assertEqual(len(_parse_feed_xml(raw.decode("latin-1"))), 0)

    def test_plain_utf8_still_parses(self):
        raw = _rss(items=self.items, bom=False)
        self.assertEqual(len(_parse_feed_xml(decode_feed_bytes(raw))), 1)

    def test_decode_never_raises_on_garbage(self):
        self.assertIsInstance(decode_feed_bytes(b"\xff\xfe\x00rubbish"), str)
        self.assertEqual(decode_feed_bytes(b""), "")


class TestCheckFeed(unittest.TestCase):
    FEED: ClassVar[dict[str, str]] = {
        "scope": "domain:ufc",
        "name": "Sherdog",
        "url": "https://x/rss",
    }

    def _check(self, response):
        with patch.object(feed_health.requests, "get", return_value=response):
            return feed_health.check_feed(self.FEED)

    def test_fresh_feed_is_ok(self):
        raw = _rss(items=[("Recent", datetime.now(timezone.utc))])
        row = self._check(_resp(200, raw))
        self.assertEqual(row["status"], feed_health.STATUS_OK)
        self.assertEqual(row["items"], 1)

    def test_old_feed_is_stale_not_ok(self):
        # Alive and parsing, but nothing recent — previously indistinguishable from ok.
        old = datetime.now(timezone.utc) - timedelta(days=90)
        row = self._check(_resp(200, _rss(items=[("Ancient", old)])))
        self.assertEqual(row["status"], feed_health.STATUS_STALE)
        self.assertGreater(row["age_days"], 14)

    def test_202_with_empty_body_is_dead(self):
        # ESPN's retired feeds answer 202 with zero bytes.
        row = self._check(_resp(202, b""))
        self.assertEqual(row["status"], feed_health.STATUS_DEAD)

    def test_200_that_parses_to_nothing_is_dead(self):
        row = self._check(_resp(200, b"<html>not a feed</html>"))
        self.assertEqual(row["status"], feed_health.STATUS_DEAD)
        self.assertIn("no items", row["detail"])

    def test_404_is_dead(self):
        row = self._check(_resp(404, b""))
        self.assertEqual(row["status"], feed_health.STATUS_DEAD)
        self.assertIn("404", row["detail"])

    def test_connection_error_is_dead_not_an_exception(self):
        with patch.object(feed_health.requests, "get", side_effect=OSError("boom")):
            row = feed_health.check_feed(self.FEED)
        self.assertEqual(row["status"], feed_health.STATUS_DEAD)
        self.assertIn("boom", row["detail"])

    def test_undated_but_populated_feed_is_ok(self):
        # No pubDate anywhere -> cannot judge staleness; having items is enough.
        doc = b'<?xml version="1.0"?><rss><channel><item><title>T</title></item></channel></rss>'
        row = self._check(_resp(200, doc))
        self.assertEqual(row["status"], feed_health.STATUS_OK)
        self.assertIsNone(row["age_days"])


class TestWarningsAndSummary(unittest.TestCase):
    def test_only_dead_and_stale_warn(self):
        rows = [
            {"status": "ok", "name": "Good", "scope": "s", "detail": ""},
            {"status": "dead", "name": "Gone", "scope": "s", "detail": "HTTP 404"},
            {"status": "stale", "name": "Old", "scope": "s", "detail": "newest 90d old"},
        ]
        warns = feed_health.warnings(rows)
        self.assertEqual(len(warns), 2)
        self.assertTrue(any("Gone" in w and "dead" in w for w in warns))
        self.assertTrue(any("Old" in w and "stale" in w for w in warns))

    def test_healthy_set_produces_no_warnings(self):
        self.assertEqual(feed_health.warnings([{"status": "ok", "name": "A", "scope": "s"}]), [])

    def test_summarize_counts(self):
        rows = [{"status": "ok"}, {"status": "ok"}, {"status": "dead"}]
        self.assertEqual(feed_health.summarize(rows)["ok"], 2)
        self.assertEqual(feed_health.summarize(rows)["dead"], 1)

    def test_render_is_cp1252_safe(self):
        rows = [
            {"status": "dead", "name": "X", "scope": "s", "url": "u", "items": 0, "detail": "d"}
        ]
        # The Windows console is cp1252; a decorative separator would crash `py -m`.
        feed_health.render(rows).encode("cp1252")


class TestPersistence(unittest.TestCase):
    """`ops reliability` reads the last check instead of re-fetching 37 feeds."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "feed_health.json")
        self.patcher = patch("config.paths.FEED_HEALTH_FILE", self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_then_load_roundtrip(self):
        rows = [{"status": "dead", "name": "Gone", "scope": "s", "detail": "HTTP 404"}]
        feed_health.save_results(rows)
        self.assertEqual(feed_health.load_results()["results"], rows)

    def test_cached_warnings_surface_dead_feeds(self):
        feed_health.save_results(
            [{"status": "dead", "name": "Gone", "scope": "s", "detail": "HTTP 404"}]
        )
        self.assertTrue(any("Gone" in w for w in feed_health.cached_warnings()))

    def test_cached_warnings_empty_when_never_run(self):
        self.assertEqual(feed_health.cached_warnings(), [])

    def test_stale_check_is_flagged_as_old(self):
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "checked_at": old,
                    "results": [{"status": "dead", "name": "Gone", "scope": "s", "detail": "x"}],
                },
                fh,
            )
        self.assertIn("ops feeds", feed_health.cached_warnings()[0])

    def test_corrupt_file_does_not_raise(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(feed_health.load_results(), {})
        self.assertEqual(feed_health.cached_warnings(), [])


class TestConfiguredFeeds(unittest.TestCase):
    def test_reads_real_config_and_dedupes(self):
        feeds = feed_health.iter_configured_feeds()
        self.assertGreater(len(feeds), 10)
        urls = [f["url"] for f in feeds]
        self.assertEqual(len(urls), len(set(urls)), "feeds must be de-duplicated by URL")
        self.assertTrue(all(f["url"].startswith("http") for f in feeds))

    def test_no_retired_feeds_remain_configured(self):
        # Regression guard for the 2026-08-14 repair: these were all verified dead.
        urls = " ".join(f["url"] for f in feed_health.iter_configured_feeds())
        for retired in (
            "espn.com/espn/rss/mma/news",
            "espn.com/espn/rss/nba/news",
            "espn.com/espn/rss/nfl/news",
            "mmafighting.com/rss/current",
            "mmajunkie.usatoday.com",
            "theathletic.com/rss",
            "feeds.ign.com/ign/games",
            "dotesports.com/feed",
        ):
            self.assertNotIn(retired, urls, f"{retired} was verified dead — should be replaced")

    def test_check_feeds_is_fail_open(self):
        with patch.object(feed_health, "iter_configured_feeds", side_effect=OSError("nope")):
            self.assertEqual(feed_health.check_feeds(), [])


if __name__ == "__main__":
    unittest.main()
