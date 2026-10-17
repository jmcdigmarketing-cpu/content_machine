"""Wave 100 (#1233-#1234): what the checks called failures, from the operator's terminal.

- Overnight's signal canary, 2026-10-16: "off anime - All providers in chain failed". Probed:
  AniList answered `inactive` "no anime match" (connected); Jikan could not be reached. The chain
  kept the last answer, so an honest no-match read as a failure - in the canary and as a
  data-quality failure.
- "Grounding tier check flagged ... High-stakes claim about 'Beats Pill'" (run 158, Pokemon's
  collabs: "the Beats Pill speaker, Santa Cruz skateboards") - the brand matched "beats".
"""

from __future__ import annotations

import unittest

from apis.signal_contract import make_signal

# ---- #1233: a provider chain keeps the honest no-match -----------------------------------------


def _anilist(_topic):
    return make_signal(
        connected=True, active=False, status="inactive", status_detail="AniList: no anime match"
    )


def _jikan_down(_topic):
    raise ConnectionError("HTTPSConnectionPool(host='api.jikan.moe', port=443): Max retries")


def _jikan_unavailable(_topic):
    return make_signal(
        connected=False, active=False, status="unavailable", status_detail="jikan unreachable"
    )


class ChainTests(unittest.TestCase):
    def test_the_canary_topic_reads_no_match_not_failed(self):
        from apis.signal_chain import chain_signal

        for jikan in (_jikan_down, _jikan_unavailable):
            with self.subTest(jikan=jikan.__name__):
                sig = chain_signal(
                    "ufc heavyweight title fight",
                    [("anilist", _anilist), ("jikan", jikan)],
                    min_score=20,
                )
                self.assertTrue(sig["connected"])
                self.assertEqual(sig["status"], "inactive")
                self.assertIn("no anime match", sig["status_detail"])
                self.assertEqual(sig["data"]["provider"], "anilist")

    def test_none_connected_is_still_a_failure(self):
        from apis.signal_chain import chain_signal

        sig = chain_signal("x", [("jikan", _jikan_unavailable)], min_score=20)
        self.assertFalse(sig["connected"])
        self.assertEqual(sig["status_detail"], "All providers in chain failed")

    def test_an_active_answer_still_wins(self):
        from apis.signal_chain import chain_signal

        def live(_topic):
            return make_signal(connected=True, active=True, status="ok", score=60)

        sig = chain_signal(
            "Frieren season 2", [("anilist", _anilist), ("jikan", live)], min_score=20
        )
        self.assertTrue(sig["active"])
        self.assertEqual(sig["data"]["provider"], "jikan")


# ---- #1234: "Beats" the brand is not a result ---------------------------------------------------------


class BrandTests(unittest.TestCase):
    def _warnings(self, script, signal_facts):
        from core.grounding_tiers import build_tiered_corpus, high_stakes_low_tier

        corpus = build_tiered_corpus(signal_facts=signal_facts, topic="t", key_facts=None)
        return high_stakes_low_tier(script, corpus)

    def test_run158s_collabs_are_not_a_result(self):
        facts = "News headlines:\n- Pokemon collabs with the Beats Pill and Santa Cruz (Dexerto)"
        script = (
            "Pokemon's 30th anniversary is stacking collabs - the Beats Pill speaker, Santa Cruz "
            "skateboards, TCG drops."
        )
        self.assertEqual(self._warnings(script, facts), [])

    def test_a_game_titled_title_is_not_a_belt(self):
        facts = "News headlines:\n- Title Update 7 lands for Warzone (Dexerto)"
        self.assertEqual(self._warnings("Warzone's Title Update 7 lands Tuesday.", facts), [])

    def test_beat_the_verb_still_warns(self):
        facts = "News headlines:\n- Jiri Prochazka beat Ankalaev on points (ESPN)"
        warnings = self._warnings("Jiri Prochazka beat Ankalaev in a classic.", facts)
        self.assertTrue(any("Jiri Prochazka" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
