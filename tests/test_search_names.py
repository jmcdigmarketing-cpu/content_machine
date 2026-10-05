"""#969: every signal searches the whole name - "Ghost of Yotei", not "Ghost".

`title_phrases(connectors=True)` (wave 58, #963) kept a name like "Ghost of Yotei" whole for
the who's-who lookup, but `search_query` - what every signal and the event guard search for
- still sent "Ghost". A sweep of `search_query` over the repo's topic strings before turning
connectors on there found three faults in the connector path itself:

- an accented letter ended the word: "Ghost of Yōtei" -> "Ghost of Y" (and "Pokémon" -> "Pok");
- "the" glued two sentence words: "5 Reasons the Lakers ..." -> "Reasons the Lakers";
- a name cut at `max_words` could end on a connector: "Southern District of".
"""

from __future__ import annotations

import unittest


class SearchQueryTests(unittest.TestCase):
    def test_a_name_with_of_is_searched_whole(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("Ghost of Yotei review", mode="entity"), "Ghost of Yotei")
        self.assertEqual(search_query("Ghost of Yotei patch 1.03 fixes stutter"), "Ghost of Yotei")
        self.assertEqual(search_query("League of Legends worlds", mode="entity"),
                         "League of Legends")  # fmt: skip

    def test_lord_of_the_rings_keeps_of_the(self):
        from apis.topic_tokens import search_query

        self.assertEqual(
            search_query("Lord of the Rings game leak", mode="entity"), "Lord of the Rings"
        )

    def test_the_alone_does_not_glue_sentence_words(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("5 Reasons the Lakers Are Overrated: A Deep Dive"),
                         "Reasons")  # fmt: skip
        self.assertEqual(search_query("Mock the LLM, not the ledger", mode="entity"), "Mock")

    def test_names_without_connectors_are_unchanged(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("Is Manchester City finished?", mode="entity"),
                         "Manchester City")  # fmt: skip
        self.assertEqual(search_query("What does Arsenal need this season?"), "Arsenal")
        self.assertEqual(search_query("UFC 320 preview and picks", mode="entity"), "UFC 320")


class AccentTests(unittest.TestCase):
    def test_an_accented_name_is_one_word(self):
        from apis.topic_tokens import search_query, title_phrases

        self.assertEqual(title_phrases("Ghost of Yōtei", connectors=True), ["Ghost of Yōtei"])
        self.assertEqual(search_query("Ghost of Yōtei released 2026-10-01", mode="entity"),
                         "Ghost of Yōtei")  # fmt: skip
        self.assertEqual(search_query("Pokémon Legends news today", mode="entity"),
                         "Pokémon Legends")  # fmt: skip


class ConnectorEdgeTests(unittest.TestCase):
    def test_a_cut_name_never_ends_on_a_connector(self):
        from apis.topic_tokens import title_phrases

        self.assertEqual(
            title_phrases("Southern District of New York", max_words=2, connectors=True),
            ["Southern District"],
        )

    def test_a_name_cut_after_a_connector_drops_the_cut_part(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("Southern District of New York charges", mode="entity"),
                         "Southern District")  # fmt: skip

    def test_an_identifier_is_not_one_word(self):
        from apis.topic_tokens import title_phrases

        self.assertEqual(title_phrases("drop it from LEGACY_NAMES now")[:1], ["LEGACY"])

    def test_connectors_do_not_count_toward_the_length(self):
        from apis.topic_tokens import search_query

        self.assertEqual(search_query("What Remains of Edith Finch", mode="entity"),
                         "Remains of Edith Finch")  # fmt: skip


if __name__ == "__main__":
    unittest.main()
