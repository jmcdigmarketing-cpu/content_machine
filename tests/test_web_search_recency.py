"""The vault must not talk the run out of fetching news.

Run 73, three runs on the same GTA 6 topic minutes apart:

    run 1  Web_search: ON      - Web search (tavily): 6 result(s)
    run 2  Web_search: SKIPPED (vault coverage)
    run 3  Web_search: SKIPPED (vault coverage)

Run 1 saved its own findings to the vault, which cleared
`WEB_SEARCH_SKIP_MIN_FACTS` (6), so runs 2 and 3 stopped searching. Each run made
the next one less fresh, and a reveal that was hours old ended up grounded on
general facts the system had written about itself.

The bar counted DENSITY with no recency term. Same shape as candidate 369
estimating from an empty script: the number was real, it just was not the number
that mattered.
"""

from __future__ import annotations

import datetime
import os
import unittest
from unittest.mock import patch

from core.web_search_skip import is_event_shaped_topic, should_skip_web_search

# Run 73's actual topics. Every one is about a thing that had just happened.
EVENT_TOPICS = (
    "GTA 6 Extended look reactions, looks great!",
    "GTA 6 Extended Look analysis reveals missing mechanics",
    "Rockstar reveals GTA 6 gameplay",
    "UFC 320 results and recap",
    "Marvel Rivals patch notes",
    "GTA 6 release date announced",
)

EVERGREEN_TOPICS = (
    "GTA 6 meta breakdown",
    "best open world games to play",
    "how to budget on a low income",
)


class TestEventShapedTopics(unittest.TestCase):
    def test_run_73_topics_all_read_as_event_shaped(self):
        for topic in EVENT_TOPICS:
            with self.subTest(topic=topic):
                self.assertTrue(is_event_shaped_topic(topic))

    def test_evergreen_topics_are_not_event_shaped(self):
        for topic in EVERGREEN_TOPICS:
            with self.subTest(topic=topic):
                self.assertFalse(is_event_shaped_topic(topic))


class _Rec:
    def __init__(self, verified_at):
        self.claim = "x"
        self.verified_at = verified_at
        self.relevance_band = "confident"
        self.uncertain = False


class TestSkipRespectsRecency(unittest.TestCase):
    """`should_skip_web_search` is what actually gates the paid call."""

    def _skip(self, topic, records, *, env=None):
        environ = {"WEB_SEARCH_SKIP_MIN_FACTS": "6", "OBSIDIAN_VAULT_PATH": "x"}
        environ.update(env or {})
        with (
            patch.dict(os.environ, environ, clear=False),
            patch("core.vault_relevance.relevance_mode", return_value="scored"),
            patch("core.obsidian_facts.load_fact_records", return_value=records),
        ):
            return should_skip_web_search(topic, "tapin", corpus="gta 6 rockstar")

    def test_a_dense_vault_does_not_silence_an_event_topic(self):
        """The run 73 case: 8 confident facts saved minutes earlier, and the topic
        is still about something that just happened."""
        today = datetime.date.today()
        fresh = [_Rec(today) for _ in range(8)]
        self.assertFalse(self._skip(EVENT_TOPICS[0], fresh))

    def test_an_evergreen_topic_with_a_dense_vault_still_skips(self):
        today = datetime.date.today()
        fresh = [_Rec(today) for _ in range(8)]
        self.assertTrue(self._skip("GTA 6 meta breakdown", fresh))

    def test_stale_vault_facts_do_not_justify_skipping(self):
        old = datetime.date.today() - datetime.timedelta(days=90)
        self.assertFalse(self._skip("GTA 6 meta breakdown", [_Rec(old) for _ in range(8)]))

    def test_undated_facts_do_not_justify_skipping(self):
        """A note with no `verified_at` cannot prove it is current."""
        self.assertFalse(self._skip("GTA 6 meta breakdown", [_Rec(None) for _ in range(8)]))

    def test_the_age_gate_is_configurable_and_can_be_turned_off(self):
        old = datetime.date.today() - datetime.timedelta(days=90)
        recs = [_Rec(old) for _ in range(8)]
        self.assertTrue(
            self._skip("GTA 6 meta breakdown", recs, env={"WEB_SEARCH_SKIP_MAX_AGE_DAYS": "0"})
        )

    def test_skip_off_entirely_still_wins(self):
        today = datetime.date.today()
        fresh = [_Rec(today) for _ in range(8)]
        self.assertFalse(
            self._skip("GTA 6 meta breakdown", fresh, env={"WEB_SEARCH_SKIP_MIN_FACTS": "off"})
        )


if __name__ == "__main__":
    unittest.main()
