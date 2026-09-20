"""Run 74: `trendingnow` failed again, as it has on every run for weeks.

    Trendingnow: ERROR — HTTPSConnectionPool(host='trendingnow.games', port=443):
    Max retries exceeded

Decisions §19: a source that produces nothing gets switched off with a recorded
reason, and the module is kept for revival rather than deleted. §19's kill switch
is `config/apify_sources.json`, which only covers paid actors — this is the same
rule for a free signal, applied where free signals are registered.
"""

from __future__ import annotations

import unittest

from apis.signals_bootstrap import RETIRED_SIGNALS, get_signal_registry


class TestTrendingNowIsRetired(unittest.TestCase):
    def test_it_is_not_registered(self):
        registered = get_signal_registry().get_registered_signals()
        self.assertNotIn("trendingnow", registered)

    def test_the_reason_is_recorded_at_the_point_of_disablement(self):
        self.assertIn("trendingnow", RETIRED_SIGNALS)
        note = RETIRED_SIGNALS["trendingnow"]
        self.assertTrue(note.strip())
        self.assertIn("2026", note)  # dated, so a revival can judge staleness

    def test_the_module_is_kept_for_revival(self):
        from apis.trendingnow_api import get_trendingnow_signal

        self.assertTrue(callable(get_trendingnow_signal))


class TestRetirementIsNarrow(unittest.TestCase):
    def test_the_working_signals_are_untouched(self):
        names = set(get_signal_registry().get_registered_signals())
        for signal in ("wikipedia", "blog_rss", "web_search", "twitch"):
            self.assertIn(signal, names)

    def test_nothing_else_was_retired_by_accident(self):
        self.assertEqual(
            set(RETIRED_SIGNALS),
            {"trendingnow", "tapology", "stats_context", "tvmaze", "tmdb"},
        )


class TestZeroYieldSignalsAreRetired(unittest.TestCase):
    """#810. Traces: tapology/stats_context/tvmaze/tmdb = 0 across every run
    that called them. §19's bar is zero, so they leave the registry. Modules stay."""

    ZEROS = ("tapology", "stats_context", "tvmaze", "tmdb")

    def test_the_zeros_are_not_registered(self) -> None:
        registered = get_signal_registry().get_registered_signals()
        for name in self.ZEROS:
            with self.subTest(name=name):
                self.assertNotIn(name, registered)
                self.assertIn(name, RETIRED_SIGNALS)
                self.assertIn("2026", RETIRED_SIGNALS[name])

    def test_the_modules_are_kept_for_revival(self) -> None:
        from apis.stats_context_api import get_stats_context_signal
        from apis.tapology_api import get_tapology
        from apis.tmdb_api import get_tmdb_signal
        from apis.tvmaze_api import get_tvmaze_signal

        self.assertTrue(callable(get_tapology))
        self.assertTrue(callable(get_stats_context_signal))
        self.assertTrue(callable(get_tvmaze_signal))
        self.assertTrue(callable(get_tmdb_signal))


class TestNearZeroSignalsStayRegistered(unittest.TestCase):
    def test_igdb_and_steam_are_not_retired_at_one_in_thirty_three(self) -> None:
        """Known gap: igdb 1/33 (+6 http errors) and steam 1/33 are not §19 zero.
        A second measured empty window, or an operator call, would close this.
        """
        registered = get_signal_registry().get_registered_signals()
        self.assertIn("igdb", registered)
        self.assertIn("steam", registered)
        self.assertNotIn("igdb", RETIRED_SIGNALS)
        self.assertNotIn("steam", RETIRED_SIGNALS)


if __name__ == "__main__":
    unittest.main()
