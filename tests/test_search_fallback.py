"""#589: when the web search provider comes back empty, ask the next one.

`apis/web_search_api` picked one provider (Tavily > Brave, or DuckDuckGo) and an empty
answer was final: the run lost its web facts even when a second key sat in `.env`.
Operator's choice (wave 46): keyed providers first, then keyless DuckDuckGo when `ddgs`
is installed. An explicit `WEB_SEARCH_BACKEND=duckduckgo` (Free mode) never falls back to
a paid key. `WEB_SEARCH_FALLBACK=false` turns it off; the suite pins it off in
`tests/__init__.py` (no network in tests) and these cases turn it on.
"""

from __future__ import annotations

import os
import unittest
from typing import ClassVar
from unittest.mock import patch

HIT = {
    "answer": "",
    "results": [{"title": "UFC 320 results", "snippet": "Pereira won.", "url": "u"}],
}
EMPTY = {"answer": "", "results": []}


class _Env(unittest.TestCase):
    ENV: ClassVar[dict[str, str]] = {
        "TAVILY_API_KEY": "t",
        "BRAVE_API_KEY": "",
        "BRAVE_SEARCH_API_KEY": "b",
        "WEB_SEARCH_BACKEND": "",
        "WEB_SEARCH_FALLBACK": "true",
    }

    def setUp(self):
        self._env = patch.dict(os.environ, self.ENV)
        self._env.start()
        self._cache = patch("apis.web_search_api.get_cached", return_value=None)
        self._cache.start()
        self._set = patch("apis.web_search_api.set_cache")
        self._set.start()

    def tearDown(self):
        self._set.stop()
        self._cache.stop()
        self._env.stop()

    def _searchers(self, **answers):
        from apis import web_search_api

        calls: list[str] = []

        def make(name):
            def search(topic, days=None):
                calls.append(name)
                return answers[name]

            return search

        table = {name: make(name) for name in answers}
        return patch.dict(web_search_api._SEARCHERS, table), calls


class ChainTests(_Env):
    def test_keyed_then_duckduckgo(self):
        from apis import web_search_api

        with patch.object(web_search_api, "_ddgs_available", return_value=True):
            self.assertEqual(web_search_api._provider_chain(), ["tavily", "brave", "duckduckgo"])

    def test_without_ddgs_the_keyed_ones_only(self):
        from apis import web_search_api

        with patch.object(web_search_api, "_ddgs_available", return_value=False):
            self.assertEqual(web_search_api._provider_chain(), ["tavily", "brave"])

    def test_free_mode_never_reaches_a_paid_key(self):
        from apis import web_search_api

        with patch.dict(os.environ, {"WEB_SEARCH_BACKEND": "duckduckgo"}):
            self.assertEqual(web_search_api._provider_chain(), ["duckduckgo"])

    def test_off_is_one_provider(self):
        from apis import web_search_api

        with patch.dict(os.environ, {"WEB_SEARCH_FALLBACK": "false"}):
            self.assertEqual(web_search_api._provider_chain(), ["tavily"])

    def test_no_key_and_no_backend_is_still_no_key(self):
        from apis import web_search_api

        with patch.dict(os.environ, {"TAVILY_API_KEY": "", "BRAVE_SEARCH_API_KEY": ""}):
            self.assertEqual(web_search_api._provider_chain(), [])
            self.assertEqual(web_search_api.get_web_search_signal("x")["status"], "no_key")


class SignalTests(_Env):
    def test_an_empty_answer_asks_the_next_provider(self):
        from apis import web_search_api

        patcher, calls = self._searchers(tavily=(EMPTY, None), brave=(HIT, None))
        with patcher, patch.object(web_search_api, "_ddgs_available", return_value=False):
            sig = web_search_api.get_web_search_signal("UFC 320 results")
        self.assertEqual(calls, ["tavily", "brave"])
        self.assertTrue(sig["active"])
        self.assertEqual(sig["data"]["provider"], "brave")
        self.assertIn("tavily empty -> brave", sig["status_detail"])

    def test_an_error_also_falls_through_and_is_named(self):
        from apis import web_search_api

        patcher, _calls = self._searchers(
            tavily=(None, ("quota_exceeded", "usage limit")), brave=(HIT, None)
        )
        with patcher, patch.object(web_search_api, "_ddgs_available", return_value=False):
            sig = web_search_api.get_web_search_signal("UFC 320 results")
        self.assertTrue(sig["active"])
        self.assertIn("tavily quota_exceeded -> brave", sig["status_detail"])

    def test_all_empty_is_inactive_naming_each(self):
        from apis import web_search_api

        patcher, calls = self._searchers(
            tavily=(EMPTY, None), brave=(EMPTY, None), duckduckgo=(EMPTY, None)
        )
        with patcher, patch.object(web_search_api, "_ddgs_available", return_value=True):
            sig = web_search_api.get_web_search_signal("UFC 320 results")
        self.assertEqual(calls, ["tavily", "brave", "duckduckgo"])
        self.assertEqual(sig["status"], "inactive")
        self.assertIn("tavily, brave, duckduckgo", sig["status_detail"])

    def test_all_errors_keep_the_first_error_status(self):
        from apis import web_search_api

        patcher, _calls = self._searchers(
            tavily=(None, ("auth_error", "bad key")), brave=(None, ("rate_limited", "429"))
        )
        with patcher, patch.object(web_search_api, "_ddgs_available", return_value=False):
            sig = web_search_api.get_web_search_signal("UFC 320 results")
        self.assertEqual(sig["status"], "auth_error")
        self.assertIn("brave rate_limited", sig["status_detail"])

    def test_the_first_hit_stops_the_chain(self):
        from apis import web_search_api

        patcher, calls = self._searchers(tavily=(HIT, None), brave=(HIT, None))
        with patcher:
            web_search_api.get_web_search_signal("UFC 320 results")
        self.assertEqual(calls, ["tavily"])


class RecentTests(_Env):
    def test_event_research_search_falls_back_too(self):
        from apis import web_search_api

        patcher, calls = self._searchers(tavily=(EMPTY, None), brave=(HIT, None))
        with patcher, patch.object(web_search_api, "_ddgs_available", return_value=False):
            results = web_search_api.search_recent("UFC Freedom 250", days=7)
        self.assertEqual(calls, ["tavily", "brave"])
        self.assertEqual(results[0]["title"], "UFC 320 results")


class SuitePinTests(unittest.TestCase):
    def test_the_suite_runs_with_the_fallback_off(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parent / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('os.environ["WEB_SEARCH_FALLBACK"] = "false"', text)


if __name__ == "__main__":
    unittest.main()
