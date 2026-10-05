"""#963 (found by the wave 58 live check): an accented name was shredded into pieces.

`apis/topic_tokens.content_tokens` matched `[a-z0-9]+` on the lower-cased text, so
"Pokémon" became "pok" + "mon" and Wikidata's "Ghost of Yōtei" became "ghost", "y",
"tei". Every "is this about the topic?" check reads these tokens, so the fresh-topic
research for "Ghost of Yōtei" kept none of the headlines that spell it "Yotei" - 0 lines
on the live check. Accents now fold to their base letter before tokenizing.
"""

from __future__ import annotations

import unittest


class AccentTests(unittest.TestCase):
    def test_an_accented_word_stays_one_token(self):
        from apis.topic_tokens import content_tokens

        self.assertEqual(content_tokens("Pokémon Legends"), ["pokemon", "legends"])
        self.assertEqual(content_tokens("Ghost of Yōtei"), content_tokens("Ghost of Yotei"))

    def test_a_headline_without_the_accent_names_it(self):
        from core.event_coverage import covered

        self.assertTrue(covered("Ghost of Yōtei", ["Ghost of Yotei patch 1.03 fixes stutter"]))
        self.assertTrue(covered("Pokemon Legends Z-A", ["Pokémon Legends Z-A sells 5 million"]))

    def test_initials_still_read(self):
        from core.event_coverage import covered

        self.assertTrue(covered("GTA 6", ["Grand Theft Auto 6 trailer three"]))


if __name__ == "__main__":
    unittest.main()
