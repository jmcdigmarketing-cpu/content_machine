"""yt-dlp extractor failures must not print through the discovery spinner.

Run 73 printed this three times, mid-spinner, in red:

    ERROR: [youtube] BTfzszKgRKc: Sign in to confirm your age. This video may be
    inappropriate for some users. Use --cookies-from-browser or --cookies ...

`opts` already set `quiet: True` and `no_warnings: True`, but yt-dlp writes
extractor errors straight to stderr regardless of those flags — only a `logger`
redirects them. The failure itself is real (age-gated competitor videos are
dropped), so it has to stay visible somewhere: debug log plus a count, not three
paragraphs of stack-adjacent noise (decisions §24, fail-open must be fail-visible
at the right volume).
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apis import free_backends


class TestYtdlpOptionsAreQuiet(unittest.TestCase):
    def _opts_for(self, fn, *args):
        seen: dict[str, dict] = {}

        class _FakeYDL:
            def __init__(self, opts):
                seen["opts"] = opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def extract_info(self, *a, **k):
                return {"entries": []}

        with patch("yt_dlp.YoutubeDL", _FakeYDL):
            fn(*args)
        return seen.get("opts", {})

    def test_search_routes_errors_to_a_logger_not_stderr(self):
        opts = self._opts_for(free_backends._flat_search, "gta 6", 3)
        self.assertIn("logger", opts, "no logger => extractor errors print to stderr")

    def test_single_fetch_routes_errors_to_a_logger_not_stderr(self):
        opts = self._opts_for(free_backends._full_one, "https://x/watch?v=1")
        self.assertIn("logger", opts)

    def test_the_logger_swallows_error_lines(self):
        opts = self._opts_for(free_backends._flat_search, "gta 6", 3)
        logger = opts["logger"]
        # Must not raise, must not print. yt-dlp calls all four.
        logger.debug("d")
        logger.info("i")
        logger.warning("w")
        logger.error("ERROR: [youtube] x: Sign in to confirm your age.")


class TestAgeGateIsCountedNotShouted(unittest.TestCase):
    def test_age_gated_failures_are_counted(self):
        logger = free_backends._YtdlpLogger()
        logger.error("ERROR: [youtube] a: Sign in to confirm your age.")
        logger.error("ERROR: [youtube] b: Sign in to confirm your age.")
        logger.error("ERROR: [youtube] c: Video unavailable")
        self.assertEqual(logger.age_gated, 2)
        self.assertEqual(logger.errors, 3)


class TestCookiesAreOptIn(unittest.TestCase):
    """Reading the operator's browser cookie jar is a real privacy step."""

    def test_unset_means_no_cookie_option_at_all(self):
        with patch.dict(os.environ, {"YTDLP_COOKIES_FROM_BROWSER": ""}, clear=False):
            opts = free_backends._ytdlp_opts()
        self.assertNotIn("cookiesfrombrowser", opts)

    def test_set_passes_the_browser_through(self):
        with patch.dict(os.environ, {"YTDLP_COOKIES_FROM_BROWSER": "chrome"}, clear=False):
            opts = free_backends._ytdlp_opts()
        self.assertEqual(opts["cookiesfrombrowser"], ("chrome",))


if __name__ == "__main__":
    unittest.main()
