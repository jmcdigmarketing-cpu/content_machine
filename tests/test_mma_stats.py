"""API-SPORTS MMA fighter stats + the retired Tapology scrape.

Background (verified live 2026-08-14): Tapology sits behind a Cloudflare JS challenge
and returned 403 for ~33 days while reporting itself as "no event match" — the failure
was invisible because a non-200 was swallowed into an empty list. Structured fighter
facts moved to `apis/mma_stats_api.py`.

Two hazards drive most of these tests:

* API-SPORTS answers a rate limit with **HTTP 200 + results: 0 + errors.rateLimit**,
  which must never be read as "fighter not found".
* `search=Topuria` returns *Aleksandre* Topuria — feeding that into a script about
  Ilia Topuria is exactly the fact contamination the vault cleanup undid.

No network: `requests` is mocked (tests/CLAUDE.md).
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from apis import mma_stats_api as mma
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    STATUS_RATE_LIMIT,
    STATUS_UNAVAILABLE,
)

_KEY = {"API_SPORTS_KEY": "test-key"}


def _json_resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


def _ok(response):
    return _json_resp({"results": len(response), "errors": [], "response": response})


FIGHTER = {
    "id": 333,
    "name": "Islam Makhachev",
    "height": "5' 10'",
    "weight": "170 lbs",
    "reach": "70.5'",
}
RECORD = {"total": {"win": 28, "loss": 1, "draw": 0}, "ko": {"win": 5}, "sub": {"win": 13}}


class TestNameExtraction(unittest.TestCase):
    def test_vs_split(self):
        self.assertEqual(
            mma.extract_fighter_names("UFC 330 Makhachev vs Garry"), ["Makhachev", "Garry"]
        )

    def test_event_prefix_is_stripped(self):
        self.assertNotIn("UFC", " ".join(mma.extract_fighter_names("UFC 320 Topuria vs Oliveira")))

    def test_comma_separated_names(self):
        names = mma.extract_fighter_names("MMA rankings: Quillan Salkilld, Alexia Thainara rise")
        self.assertIn("Quillan Salkilld", names)

    def test_no_names_in_generic_topic(self):
        self.assertEqual(mma.extract_fighter_names("UFC 320 preview"), [])

    def test_caps_at_two_fighters(self):
        # Free tier is 10 req/min and each fighter costs 2 calls.
        self.assertLessEqual(len(mma.extract_fighter_names("A vs B vs C vs D")), 2)

    def test_empty_topic(self):
        self.assertEqual(mma.extract_fighter_names(""), [])


class TestNameMatching(unittest.TestCase):
    def test_rejects_the_wrong_brother(self):
        self.assertFalse(mma._name_matches("Ilia Topuria", "Aleksandre Topuria"))

    def test_accepts_middle_name_variant(self):
        self.assertTrue(mma._name_matches("Ian Garry", "Ian Machado Garry"))

    def test_surname_only_query_accepts(self):
        self.assertTrue(mma._name_matches("Makhachev", "Islam Makhachev"))

    def test_rejects_different_surname(self):
        self.assertFalse(mma._name_matches("Ilia Topuria", "Justin Gaethje"))

    def test_empty_inputs_reject(self):
        self.assertFalse(mma._name_matches("", "Islam Makhachev"))
        self.assertFalse(mma._name_matches("Makhachev", ""))


class TestApiErrorDetection(unittest.TestCase):
    """A 200 body can still be a failure."""

    def test_rate_limit_dict_is_an_error(self):
        reason = mma._api_error({"errors": {"rateLimit": "Too many requests."}})
        self.assertIn("rateLimit", reason)

    def test_plan_gate_is_an_error(self):
        self.assertIn("plan", mma._api_error({"errors": {"plan": "Free plans..."}}))

    def test_empty_list_is_success(self):
        self.assertEqual(mma._api_error({"errors": [], "response": []}), "")

    def test_missing_key_is_success(self):
        self.assertEqual(mma._api_error({"response": []}), "")


class TestFighterLine(unittest.TestCase):
    def test_full_line(self):
        line = mma._fighter_line(FIGHTER, RECORD)
        self.assertIn("Islam Makhachev", line)
        self.assertIn("28-1-0", line)
        self.assertIn("5 KO", line)
        self.assertIn("13 SUB", line)
        self.assertIn("API-SPORTS", line)

    def test_physicals_only_when_record_missing(self):
        line = mma._fighter_line(FIGHTER, {})
        self.assertIn("170 lbs", line)
        self.assertNotIn("record", line)

    def test_nothing_usable_yields_no_line(self):
        # Many fighters return None everywhere; emitting a bare name is not a fact.
        self.assertEqual(mma._fighter_line({"name": "Nobody"}, {}), "")

    def test_none_strings_are_not_emitted(self):
        line = mma._fighter_line({"name": "X", "height": "None", "weight": "170 lbs"}, {})
        self.assertNotIn("None", line)


class TestSignal(unittest.TestCase):
    def test_no_key(self):
        with patch.dict("os.environ", {"API_SPORTS_KEY": ""}, clear=False):
            self.assertEqual(mma.get_mma_stats_signal("UFC 330")["status"], STATUS_NO_KEY)

    def test_non_mma_topic_is_inactive(self):
        with patch.dict("os.environ", _KEY, clear=False):
            sig = mma.get_mma_stats_signal("Marvel Rivals new hero")
        self.assertEqual(sig["status"], STATUS_INACTIVE)

    def test_happy_path(self):
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", side_effect=[_ok([FIGHTER]), _ok([RECORD])]),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Makhachev vs Nobody")
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertTrue(sig["active"])
        self.assertIn("28-1-0", (sig["data"]["lines"] or [""])[0])

    def test_rate_limit_reports_rate_limited_not_no_match(self):
        # The whole point: a throttled lookup must not read as "fighter not found".
        limited = _json_resp(
            {"results": 0, "errors": {"rateLimit": "Too many requests."}, "response": []}
        )
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", return_value=limited),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Makhachev vs Garry")
        self.assertEqual(sig["status"], STATUS_RATE_LIMIT)
        self.assertFalse(sig["connected"])

    def test_plan_gate_reports_quota(self):
        gated = _json_resp(
            {"results": 0, "errors": {"plan": "Free plans do not..."}, "response": []}
        )
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", return_value=gated),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Makhachev vs Garry")
        self.assertEqual(sig["status"], STATUS_QUOTA)

    def test_genuine_no_match_is_inactive(self):
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", return_value=_ok([])),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Makhachev vs Garry")
        self.assertEqual(sig["status"], STATUS_INACTIVE)
        self.assertTrue(sig["connected"])

    def test_wrong_person_is_not_emitted_as_fact(self):
        wrong = {"id": 9, "name": "Aleksandre Topuria", "weight": "135 lbs"}
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", return_value=_ok([wrong])),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Ilia Topuria vs Nobody")
        self.assertEqual(sig["data"]["lines"], [])

    def test_network_error_never_raises(self):
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", side_effect=OSError("down")),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Makhachev vs Garry")
        self.assertFalse(sig["active"])

    def test_signal_shape(self):
        with (
            patch.dict("os.environ", _KEY, clear=False),
            patch.object(mma.requests, "get", side_effect=[_ok([FIGHTER]), _ok([RECORD])]),
        ):
            sig = mma.get_mma_stats_signal("UFC 330 Makhachev vs Nobody")
        for field in ("connected", "active", "score", "confidence", "status", "data"):
            self.assertIn(field, sig)


class TestFactsReachThePrompt(unittest.TestCase):
    """`signal_facts` formats per-signal, so a new data key is dropped unless wired.

    Without the `fighter_stats` branch the signal would look healthy while none of its
    facts ever reached the script — the same silent-loss shape as the dead feeds.
    """

    def _facts(self, data):
        from core.signal_facts import format_signal_facts

        return format_signal_facts(
            {"ufc_context": {"connected": True, "active": True, "data": data}}
        )

    def test_fighter_lines_are_rendered(self):
        out = self._facts({"fighter_stats": {"lines": ["Islam Makhachev - record 28-1-0"]}})
        self.assertIn("Islam Makhachev", out)
        self.assertIn("28-1-0", out)

    def test_missing_fighter_stats_is_harmless(self):
        # Older traces / non-MMA payloads have no such key.
        self.assertNotIn("Fighter record", self._facts({"headlines": []}))

    def test_empty_lines_render_nothing(self):
        self.assertNotIn("Fighter record", self._facts({"fighter_stats": {"lines": []}}))


class TestTapologyHonestFailure(unittest.TestCase):
    """A Cloudflare block must read as broken, not as 'no event match'."""

    def test_403_reports_unavailable(self):
        from apis import tapology_api

        err = requests.HTTPError(response=MagicMock(status_code=403))
        with (
            patch.dict("os.environ", {"TAPOLOGY_SCRAPE_ENABLED": "true"}, clear=False),
            patch.object(tapology_api, "scrape_tapology", side_effect=err),
        ):
            sig = tapology_api.get_tapology("UFC 330 fight card")
        self.assertEqual(sig["status"], STATUS_UNAVAILABLE)
        self.assertFalse(sig["connected"])
        self.assertNotIn("no event match", (sig.get("status_detail") or "").lower())

    def test_disabled_by_default(self):
        from apis import tapology_api

        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(tapology_api.scrape_enabled())

    def test_query_no_longer_injects_hardcoded_fighters(self):
        # It used to build "UFC <n> Topuria Gaethje" for *every* numbered event.
        from apis import tapology_api

        captured = []

        def _search(_session, query):
            captured.append(query)
            return []

        with (
            patch.object(tapology_api, "_search_events", side_effect=_search),
            patch.object(tapology_api, "_get_cached", return_value=None),
            patch.object(tapology_api, "_set_cached"),
        ):
            tapology_api.scrape_tapology("UFC 330 Makhachev title defence")
        self.assertTrue(captured)
        joined = " ".join(captured).lower()
        self.assertNotIn("topuria", joined)
        self.assertNotIn("gaethje", joined)


if __name__ == "__main__":
    unittest.main()
