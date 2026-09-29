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


class NestedPinTests(unittest.TestCase):
    """#906: the pins the remaining JSON signals need."""

    def test_a_dotted_container(self):
        from apis.schema_pins import drift

        ok = {"data": {"Page": {"media": [{"title": {"romaji": "x"}}]}}}
        self.assertIsNone(drift("anilist", ok))
        self.assertEqual(drift("anilist", {"data": {"Page": {}}}), "missing `data.Page.media`")
        self.assertEqual(drift("anilist", {"data": {}}), "missing `data.Page.media`")

    def test_a_null_on_the_path_is_an_empty_answer(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("anilist", {"data": None, "errors": [{"message": "x"}]}))

    def test_alternative_item_keys(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("tmdb", {"results": [{"name": "Arcane"}]}))
        self.assertIsNone(drift("tmdb", {"results": [{"title": "Dune"}]}))
        self.assertEqual(
            drift("tmdb", {"results": [{"original_title": "Dune"}]}),
            "`results[]` items lack `title|name`",
        )

    def test_a_single_object_counts_as_one_item(self):
        from apis.schema_pins import drift

        one = {"results": {"trackmatches": {"track": {"name": "Espresso"}}}}
        self.assertIsNone(drift("lastfm", one))

    def test_an_optional_parent_may_be_absent(self):
        from apis.schema_pins import drift

        self.assertIsNone(drift("web_search_brave", {"type": "search"}))
        self.assertEqual(
            drift("web_search_brave", {"type": "search", "web": {"items": []}}),
            "missing `web.results`",
        )

    def test_check_raises(self):
        from apis.schema_pins import SchemaDrift, check

        with self.assertRaises(SchemaDrift) as ctx:
            check("wikipedia", {"records": []})
        self.assertEqual(str(ctx.exception), "missing `items`")
        check("wikipedia", {"items": []})  # healthy: no raise

    def test_every_pinned_parser_is_named(self):
        from apis.schema_pins import PINS

        for name in (
            "tmdb", "tvmaze", "jikan", "anilist", "finnhub", "balldontlie",
            "wikipedia", "musicbrainz", "lastfm", "web_search_brave",
        ):  # fmt: skip
            self.assertIn(name, PINS)


if __name__ == "__main__":
    unittest.main()
