"""Candidate 324: name overlap is not subject identity.

Live-run 71 covered a 2026 GTA 6 leak under the angle "...Wolverine Rage...". RAWG
contributed three games:

    Wolverine: Adamantium Rage   1994
    X-Men: Wolverine's Rage      2001
    Wolverine                    1991

The shipped relevance gate passed all three *correctly by its own rule* — it keeps a
result when more than half its name tokens appear in the topic. Token overlap is
necessary but not sufficient: it has no notion of whether the game is the SUBJECT.
They then counted toward the authenticity gate's "18 verified fact(s)".

Release era is what separates them, so that is what this adds. The first test class
pins the existing behaviour so it is clear the old rule was not broken — it was
incomplete.
"""

import unittest
from unittest.mock import patch

from apis.rawg_api import _is_current_era, _is_relevant, _sig_tokens, _topic_is_retro

RUN71_TOPIC = "Gta 6 Leak And Wolverine Rage Signal A Cultural Backlash Brewing"

WOLVERINE_1994 = {"name": "Wolverine: Adamantium Rage", "released": "1994-01-01"}
WOLVERINE_2001 = {"name": "X-Men: Wolverine's Rage", "released": "2001-05-15"}
WOLVERINE_1991 = {"name": "Wolverine", "released": "1991-10-01"}


class TestTheOldRuleWasIncompleteNotBroken(unittest.TestCase):
    """Measured: name overlap alone admits all three, exactly as designed."""

    def test_overlap_passes_every_run71_game(self):
        topic_tokens = set(_sig_tokens(RUN71_TOPIC))
        for game in (WOLVERINE_1994, WOLVERINE_2001, WOLVERINE_1991):
            self.assertTrue(
                _is_relevant(game["name"], topic_tokens), f"{game['name']} should pass overlap"
            )


class TestEraGate(unittest.TestCase):
    def test_run71_games_are_rejected_as_stale(self):
        for game in (WOLVERINE_1994, WOLVERINE_2001, WOLVERINE_1991):
            self.assertFalse(
                _is_current_era(game, RUN71_TOPIC, now_year=2026), f"{game['name']} is not evidence"
            )

    def test_a_current_game_survives(self):
        game = {"name": "Grand Theft Auto V", "released": "2013-09-17"}
        self.assertTrue(_is_current_era(game, "GTA 6 leak", now_year=2026))

    def test_the_boundary_is_inclusive(self):
        self.assertTrue(_is_current_era({"released": "2011-01-01"}, "t", now_year=2026))
        self.assertFalse(_is_current_era({"released": "2010-12-31"}, "t", now_year=2026))


class TestFailOpen(unittest.TestCase):
    """A missing date is not evidence of staleness."""

    def test_no_release_date_keeps_the_result(self):
        self.assertTrue(_is_current_era({"name": "Unannounced"}, "t", now_year=2026))

    def test_empty_release_date_keeps_the_result(self):
        self.assertTrue(_is_current_era({"released": ""}, "t", now_year=2026))

    def test_unparseable_release_date_keeps_the_result(self):
        self.assertTrue(_is_current_era({"released": "TBA"}, "t", now_year=2026))

    def test_rule_can_be_disabled(self):
        with patch.dict("os.environ", {"RAWG_MAX_AGE_YEARS": "0"}):
            self.assertTrue(_is_current_era(WOLVERINE_1991, RUN71_TOPIC, now_year=2026))

    def test_garbage_env_falls_back_to_the_default(self):
        with patch.dict("os.environ", {"RAWG_MAX_AGE_YEARS": "banana"}):
            self.assertFalse(_is_current_era(WOLVERINE_1991, RUN71_TOPIC, now_year=2026))


class TestRetroTopicsAreExempt(unittest.TestCase):
    """A topic that is *about* an old game must still get that game's facts."""

    def test_keyword_cues(self):
        for topic in (
            "Retro review: the best PS1 games",
            "GoldenEye remaster finally lands",
            "Marking the 30th anniversary of Wolverine: Adamantium Rage",
            "Revisiting the classics that shaped the genre",
        ):
            self.assertTrue(_topic_is_retro(topic), topic)

    def test_an_explicit_old_year_signals_retro_intent(self):
        self.assertTrue(_topic_is_retro("Why the 1994 original still holds up"))

    def test_a_current_year_does_not(self):
        self.assertFalse(_topic_is_retro("GTA 6 leak spreads in 2026"))

    def test_run71_topic_is_not_retro(self):
        self.assertFalse(_topic_is_retro(RUN71_TOPIC))

    def test_retro_topic_keeps_the_old_game(self):
        self.assertTrue(
            _is_current_era(
                WOLVERINE_1994,
                "Revisiting Wolverine: Adamantium Rage 30 years on",
                now_year=2026,
            )
        )


class TestSignalEndToEnd(unittest.TestCase):
    """The filter must reach get_rawg_signal, not just live in a helper."""

    def _signal(self, results, topic):
        from apis import rawg_api

        class _Resp:
            status_code = 200

            def json(self):
                return {"results": results}

        with patch.object(rawg_api, "_rawg_key", return_value="k"):
            with patch.object(rawg_api.requests, "get", return_value=_Resp()):
                return rawg_api.get_rawg_signal(topic)

    def test_run71_now_yields_nothing_instead_of_three_stale_games(self):
        signal = self._signal([WOLVERINE_1994, WOLVERINE_2001, WOLVERINE_1991], RUN71_TOPIC)
        self.assertFalse(signal["active"])
        self.assertEqual(signal["data"], [])

    def test_a_relevant_current_game_still_lands(self):
        game = {"name": "Marvel Rivals", "released": "2024-12-06"}
        signal = self._signal([game], "Marvel Rivals season 9 patch notes")
        self.assertTrue(signal["active"])
        self.assertEqual(signal["data"], [game])

    def test_the_acronym_case_the_gate_exists_for_still_works(self):
        game = {"name": "Grand Theft Auto V", "released": "2013-09-17"}
        signal = self._signal([game], "GTA 6 leak spreads online")
        self.assertTrue(signal["active"], "GTA -> Grand Theft Auto must survive")


if __name__ == "__main__":
    unittest.main()
