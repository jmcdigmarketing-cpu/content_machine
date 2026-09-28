"""#385: a renamed response field is an error, not "no results".

Every JSON signal read its payload with `.get("results", [])`-shaped defaults, so when a
provider renamed a field the signal reported a healthy "no match" (`STATUS_INACTIVE`)
forever: no incident, nothing in `ops reliability`, just thinner facts. `apis/schema_pins`
names, per signal, the container and item keys its parser reads; a 200 whose body has
drifted from that returns `STATUS_UPSTREAM` "schema drift: ...". The per-signal cases
run from the recorded payloads in `tests/test_signal_contracts.py` (#626).
"""

from __future__ import annotations

import unittest


class DriftTests(unittest.TestCase):
    def test_a_healthy_payload_has_no_drift(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("rawg", {"results": [{"name": "GTA VI"}]}))
        self.assertIsNone(drift("odds", [{"key": "mma_mixed_martial_arts"}]))

    def test_an_empty_answer_is_not_drift(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("rawg", {"results": []}))
        self.assertIsNone(drift("sports", {"teams": None}))  # TheSportsDB's "no match"
        self.assertIsNone(drift("odds", []))

    def test_a_missing_container_is_drift(self):
        from apis.schema_pins import drift

        self.assertEqual(drift("news", {"items": []}), "missing `articles`")

    def test_items_that_lost_a_key_are_drift(self):
        from apis.schema_pins import drift

        self.assertEqual(
            drift("rawg", {"results": [{"title": "GTA VI"}]}), "`results[]` items lack `name`"
        )

    def test_one_item_without_the_key_is_not_drift(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("rawg", {"results": [{"name": "GTA VI"}, {"slug": "x"}]}))

    def test_the_wrong_top_level_type_is_drift(self):
        from apis.schema_pins import drift

        self.assertEqual(drift("odds", {"data": []}), "expected a list, got dict")
        self.assertEqual(drift("rawg", []), "expected an object, got list")

    def test_an_unpinned_signal_is_never_drift(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("no_such_signal", {"anything": 1}))


class SignalTests(unittest.TestCase):
    def test_the_signal_reports_it(self):
        from apis.schema_pins import drift_signal
        from apis.signal_contract import STATUS_UPSTREAM, normalize_signal

        sig = drift_signal("missing `articles`")
        self.assertEqual(sig["status"], STATUS_UPSTREAM)
        self.assertFalse(sig["active"])
        self.assertEqual(sig["status_detail"], "schema drift: missing `articles`")
        self.assertEqual(normalize_signal(sig), sig)

    def test_drift_does_not_trip_the_session_breaker(self):
        from apis import register_signals
        from apis.signal_contract import STATUS_UPSTREAM

        self.assertNotIn(STATUS_UPSTREAM, register_signals._trip_statuses())


if __name__ == "__main__":
    unittest.main()
