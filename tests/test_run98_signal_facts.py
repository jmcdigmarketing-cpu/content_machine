"""Run 98: a football topic on a gaming channel came back with gaming "facts".

The typed topic was "Manchester City ofund guilty, what does this mean for the prem".
Four separate defects put unrelated lines in front of the script model, each shown
here with the exact strings from the run:

- RAWG kept "What's This?" and "What does it mean!?" because its relevance stoplist
  had no question words, so "what"/"this"/"mean" counted as game-name matches.
- Twitch matched no game, then summed the site-wide top streams anyway and reported
  an active 98 - a number about Twitch, not about this topic.
- Topic fan-out split on the comma and queried "what does this mean for the prem"
  on its own.
- Raw popularity payloads (twitch/trends/wikipedia/autocomplete) were dumped as
  "<name> data: {json}" under VERIFIED FACTS, counted as "16 verified fact(s)", and
  fed the vault relevance corpus - which is how a "Marvel Rivals" vault bullet got
  full entity support on a Manchester City run.

No network: every provider call is a mock.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from apis.signal_contract import make_signal

RUN98 = "Manchester City ofund guilty, what does this mean for the prem"


def _resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.text = ""
    return r


class TestTopicTokens(unittest.TestCase):
    def test_question_words_are_not_content(self) -> None:
        from apis.topic_tokens import content_tokens

        self.assertEqual(content_tokens(RUN98), ["manchester", "city", "ofund", "guilty", "prem"])


class TestRawg(unittest.TestCase):
    def test_question_word_titles_do_not_match(self) -> None:
        from apis.rawg_api import _is_relevant, _sig_tokens

        tokens = set(_sig_tokens(RUN98))
        self.assertFalse(_is_relevant("What's This?", tokens))
        self.assertFalse(_is_relevant("What does it mean!?", tokens))

    def test_a_real_game_still_matches(self) -> None:
        from apis.rawg_api import _is_relevant, _sig_tokens

        self.assertTrue(_is_relevant("Marvel Rivals", set(_sig_tokens("Marvel Rivals season 4"))))
        self.assertTrue(_is_relevant("Grand Theft Auto VI", set(_sig_tokens("GTA 6 delay"))))


_TOP_GAMES = {
    "data": [
        {"id": "1", "name": "Just Chatting"},
        {"id": "2", "name": "League of Legends"},
        {"id": "3", "name": "VALORANT"},
        {"id": "4", "name": "Marvel Rivals"},
    ]
}


class TestTwitch(unittest.TestCase):
    def _signal(self, topic):
        from apis import twitch_api

        calls: list[dict] = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append({"url": url, "params": dict(params or {})})
            if url.endswith("/games/top"):
                return _resp(_TOP_GAMES)
            return _resp({"data": [{"viewer_count": 250_000}, {"viewer_count": 44_783}]})

        with (
            patch.object(twitch_api, "_CLIENT_ID", "id"),
            patch.object(twitch_api, "_CLIENT_SECRET", "secret"),
            patch.object(twitch_api, "_app_token", return_value="tok"),
            patch.object(twitch_api, "get_cached", return_value=None),
            patch.object(twitch_api, "set_cache"),
            patch.object(twitch_api.requests, "get", side_effect=fake_get),
        ):
            return twitch_api.get_twitch_signal(topic), calls

    def test_no_game_match_is_inactive_and_makes_no_streams_call(self) -> None:
        sig, calls = self._signal(RUN98)
        self.assertFalse(sig["active"], sig.get("status_detail"))
        self.assertEqual(len(calls), 1, "queried site-wide streams for a topic with no game")

    def test_premier_league_is_not_league_of_legends(self) -> None:
        sig, _calls = self._signal("Premier League title race")
        self.assertFalse(sig["active"])

    def test_a_named_game_still_scores_on_its_own_streams(self) -> None:
        sig, calls = self._signal("Marvel Rivals season 4 balance patch")
        self.assertTrue(sig["active"])
        self.assertEqual(calls[1]["params"].get("game_id"), "4")


class TestSteam(unittest.TestCase):
    def _signal(self, topic, names):
        from apis import steam_api

        items = [{"name": n, "id": i} for i, n in enumerate(names)]
        with patch.object(steam_api.requests, "get", return_value=_resp({"items": items})):
            return steam_api.get_steam_signal(topic)

    def test_unrelated_store_results_are_inactive(self) -> None:
        sig = self._signal(RUN98, ["What Remains of Edith Finch", "City Car Driving"])
        self.assertFalse(sig["active"])

    def test_a_matching_game_is_active(self) -> None:
        sig = self._signal("Hollow Knight Silksong review", ["Hollow Knight: Silksong"])
        self.assertTrue(sig["active"])


class TestFanout(unittest.TestCase):
    def test_a_question_half_is_not_a_subtopic(self) -> None:
        from apis.topic_fanout import parse_subtopics

        self.assertEqual(parse_subtopics(RUN98), [])

    def test_a_real_list_still_splits(self) -> None:
        from apis.topic_fanout import parse_subtopics

        self.assertEqual(
            parse_subtopics("Marvel Rivals, terraria, cod"), ["Marvel Rivals", "terraria", "cod"]
        )


def _demand_signals():
    return {
        "twitch": make_signal(
            connected=True,
            active=True,
            score=98,
            data={"games": [{"name": "Marvel Rivals"}], "viewers": 294_783},
        ),
        "wikipedia": make_signal(
            connected=True, active=True, score=60, data={"article": "Manchester"}
        ),
    }


class TestDemandDumpsAreContext(unittest.TestCase):
    def test_they_are_not_counted_as_verified_facts(self) -> None:
        from core.fact_enrichment import _fact_line_count
        from core.signal_facts import format_signal_facts

        text = format_signal_facts(_demand_signals())
        self.assertIn("Demand signals", text)
        self.assertEqual(_fact_line_count(text), 0, text)

    def test_the_script_prompt_files_them_under_context(self) -> None:
        from core.content_engine import _split_facts_block
        from core.signal_facts import format_signal_facts

        verified, context = _split_facts_block(format_signal_facts(_demand_signals()))
        self.assertNotIn("Marvel Rivals", verified)
        self.assertIn("Marvel Rivals", context)

    def test_the_tier_layer_calls_them_context(self) -> None:
        from core.fact_store import TIER_CONTEXT
        from core.grounding_tiers import _tag_signal_facts
        from core.signal_facts import format_signal_facts

        tagged = _tag_signal_facts(format_signal_facts(_demand_signals()))
        tiers = {tier for tier, line in tagged if "Marvel Rivals" in line}
        self.assertEqual(tiers, {TIER_CONTEXT})

    def test_the_vault_corpus_does_not_contain_them(self) -> None:
        from core.vault_relevance import build_relevance_corpus

        self.assertNotIn("Marvel Rivals", build_relevance_corpus(_demand_signals()))

    def test_a_finance_dump_is_still_a_fact(self) -> None:
        from core.fact_enrichment import _fact_line_count
        from core.signal_facts import format_signal_facts

        sig = make_signal(connected=True, active=True, score=70, data={"quote": {"c": 101.2}})
        self.assertEqual(_fact_line_count(format_signal_facts({"finnhub": sig})), 1)


if __name__ == "__main__":
    unittest.main()
