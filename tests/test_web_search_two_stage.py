"""Scored-mode web_search must wait for a non-web corpus, then skip or fetch once.

Today `_active_signal_sources` calls `should_skip_web_search` before any signal
runs, so the skipper reads the vault with no corpus. In scored mode that cannot
count confident facts. These tests drive the real `build_registry` with fake
signal functions and a temp vault.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apis import register_signals as rs
from apis.api_registry import SignalRegistry
from apis.signal_contract import STATUS_OK, STATUS_SKIPPED, make_signal

TOPIC = "GTA 6 Leak and Wolverine Rage Signal a Cultural Backlash"
HEADLINE = "Rockstar Games filed subpoenas against Microsoft and Discord"
ROCKSTAR_NOTE = """---
tier: link
channel: tapin
tags: [facts]
source: https://example.com/rockstar
---

# Rockstar investigation
- Rockstar Games confirms the leak investigation is ongoing.
"""


def _fake_registry(news_calls: list, web_calls: list) -> SignalRegistry:
    reg = SignalRegistry()

    def fake_news(topic: str):
        news_calls.append(topic)
        return make_signal(
            connected=True,
            active=True,
            score=50,
            data={"headlines": [{"title": HEADLINE, "source": "wire"}]},
        )

    def fake_web(topic: str):
        web_calls.append(topic)
        return make_signal(
            connected=True,
            active=True,
            score=40,
            data={"provider": "tavily", "results": [{"title": "Live result"}]},
        )

    reg.register("news", fake_news)
    reg.register("web_search", fake_web)
    return reg


class TestTwoStageWebSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.news_calls: list[str] = []
        self.web_calls: list[str] = []
        self.reg = _fake_registry(self.news_calls, self.web_calls)
        self.env = {
            "VAULT_RELEVANCE_MODE": "scored",
            "WEB_SEARCH_SKIP_MIN_FACTS": "1",
            "TOPIC_FANOUT_ENABLED": "false",
            "CONTENT_SKIP_SIGNALS": "",
            "OBSIDIAN_VAULT_PATH": "",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *, vault_note: str | None, reuse=None, extra_env=None, topic=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        topic = topic or f"{TOPIC} {self.id()}"
        if vault_note:
            root = Path(self.tmp.name) / "vault" / "tapin"
            root.mkdir(parents=True, exist_ok=True)
            (root / "rockstar.md").write_text(vault_note, encoding="utf-8")
            env["OBSIDIAN_VAULT_PATH"] = str(Path(self.tmp.name) / "vault")
        with (
            patch.object(rs, "get_signal_registry", return_value=self.reg),
            patch.object(rs, "start_youtube_warmup_background"),
            patch.dict(os.environ, env, clear=False),
        ):
            return rs.build_registry(topic, channel_id="tapin", reuse_signals=reuse), topic

    def test_dense_confident_vault_skips_web_with_explicit_status(self):
        results, topic = self._run(vault_note=ROCKSTAR_NOTE)
        self.assertEqual(self.news_calls, [topic])
        self.assertEqual(self.web_calls, [])
        skipped = results["web_search"]
        self.assertEqual(skipped["status"], STATUS_SKIPPED)
        self.assertIn("vault", (skipped.get("status_detail") or "").lower())

    def test_thin_vault_fetches_web_once(self):
        results, topic = self._run(vault_note=None)
        self.assertEqual(self.news_calls, [topic])
        self.assertEqual(self.web_calls, [topic])
        self.assertEqual(results["web_search"]["status"], STATUS_OK)

    def test_scorer_failure_fails_open_to_web(self):
        with patch(
            "core.obsidian_facts.load_fact_records",
            side_effect=RuntimeError("scorer down"),
        ):
            results, topic = self._run(vault_note=ROCKSTAR_NOTE)
        self.assertEqual(self.web_calls, [topic])
        self.assertEqual(results["web_search"]["status"], STATUS_OK)

    def test_cached_web_is_not_fetched_again(self):
        _first, topic = self._run(vault_note=None)
        self._run(vault_note=None, topic=topic)
        self.assertEqual(self.web_calls, [topic])

    def test_variant_reuse_does_not_call_web_after_a_skip(self):
        first, _topic = self._run(vault_note=ROCKSTAR_NOTE)
        self.assertEqual(first["web_search"]["status"], STATUS_SKIPPED)
        second, _ = self._run(vault_note=ROCKSTAR_NOTE, reuse=first, topic=_topic)
        self.assertEqual(self.web_calls, [])
        self.assertEqual(second["web_search"]["status"], STATUS_SKIPPED)

    def test_legacy_still_density_skips_before_fetch(self):
        """Existing contract: legacy may drop web_search from the source list."""
        facts = ["fact 1 distinctive", "fact 2 distinctive"]
        with (
            patch.object(rs, "get_signal_registry", return_value=self.reg),
            patch("core.web_search_skip.should_skip_web_search", return_value=True),
            patch.dict(
                os.environ,
                {**self.env, "VAULT_RELEVANCE_MODE": "legacy"},
                clear=False,
            ),
        ):
            names = {n for n, _ in rs._active_signal_sources(TOPIC, "tapin")}
        self.assertNotIn("web_search", names)
        del facts


if __name__ == "__main__":
    unittest.main()
