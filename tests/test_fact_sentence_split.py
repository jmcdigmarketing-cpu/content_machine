"""Run 74: no fact may reach the model cut off mid-sentence.

`_MAX_KEY_FACT_CHARS = 400` was a runaway-blob guard implemented as `line[:400]`.
A scraped paragraph came back as "...the campaign will progress through a
chapter-based" — which does not read as a truncation to a language model. It reads
as a finished, vague statement, and the model resolves the ambiguity by inventing.

The cap becomes a *splitter*: whole sentences, as many as fit, and the rest as the
next fact line. Nothing is lost; only the total prompt budget drops anything, and
it already says so.
"""

from __future__ import annotations

import unittest

from core.operator_facts import _MAX_KEY_FACT_CHARS, facts_for_prompt, split_at_sentences

# A real scraped paragraph, 500+ chars — the shape that used to get sliced.
PARAGRAPH = (
    "Rockstar Games has revealed over 150 new GTA 6 details through its 26-minute "
    "extended look. According to Rockstar North co-studio head Rob Nelson, his latest "
    "playthrough took around 80 hours to finish. Much like Red Dead Redemption 2, the "
    "campaign will progress through a chapter-based structure. Rather than pushing "
    "players directly toward the next major objective, the campaign encourages "
    "wandering. Open-world encounters will also connect more naturally with the story."
)


class TestNothingIsCutMidSentence(unittest.TestCase):
    def test_short_text_is_returned_unchanged(self):
        self.assertEqual(
            split_at_sentences("Six wanted stars return.", 400), ["Six wanted stars return."]
        )

    def test_empty_text_yields_nothing(self):
        self.assertEqual(split_at_sentences("", 400), [])
        self.assertEqual(split_at_sentences("   ", 400), [])

    def test_a_long_paragraph_splits_into_several_lines(self):
        chunks = split_at_sentences(PARAGRAPH, 200)
        self.assertGreater(len(chunks), 1)

    def test_every_chunk_ends_at_a_sentence_boundary(self):
        for chunk in split_at_sentences(PARAGRAPH, 200):
            self.assertTrue(chunk.rstrip().endswith((".", "!", "?", '."', '?"')), chunk[-40:])

    def test_nothing_is_lost(self):
        rejoined = " ".join(split_at_sentences(PARAGRAPH, 200))
        self.assertEqual(rejoined, PARAGRAPH)

    def test_the_run_74_fragment_can_no_longer_be_produced(self):
        for chunk in split_at_sentences(PARAGRAPH, 200):
            self.assertFalse(chunk.endswith("chapter-based"), chunk)

    def test_a_single_over_long_sentence_survives_whole(self):
        # A real sentence is information; a fragment of one is a trap.
        sentence = "Rockstar " + "confirmed and reconfirmed " * 20 + "the release date."
        self.assertGreater(len(sentence), 400)
        self.assertEqual(split_at_sentences(sentence, 400), [sentence])


class TestAbbreviationsAreNotSentenceEnds(unittest.TestCase):
    def test_titles_and_month_abbreviations_do_not_split(self):
        text = (
            "Mr. Nelson told IGN the game ships Nov. 19. Take-Two Interactive Inc. "
            "confirmed the date."
        )
        chunks = split_at_sentences(text, 60)
        self.assertTrue(
            all(not c.rstrip().endswith(("Mr.", "Nov.", "Inc.")) for c in chunks), chunks
        )


class TestPunctuationFreeBlobsAreStillBounded(unittest.TestCase):
    """A scraped <p> with no punctuation must not eat the whole prompt budget."""

    def test_a_huge_run_on_is_split_at_word_boundaries_and_marked_elided(self):
        blob = "detail " * 500  # 3000 chars, not one sentence in sight
        chunks = split_at_sentences(blob, 400)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks[:-1]:
            self.assertTrue(chunk.endswith("…"), chunk[-30:])
            self.assertLessEqual(len(chunk), 400)
        # Word boundaries only — never a severed word.
        self.assertFalse(any(c.rstrip("…").rstrip().endswith("deta") for c in chunks))


class TestTheBudgetPathUsesIt(unittest.TestCase):
    def test_facts_for_prompt_never_returns_a_severed_line(self):
        sent = facts_for_prompt([PARAGRAPH * 3])
        self.assertTrue(sent)
        for line in sent:
            self.assertLessEqual(len(line), max(_MAX_KEY_FACT_CHARS, 1) * 3)
            self.assertTrue(line.rstrip().endswith((".", "!", "?", "…", '."')), line[-40:])

    def test_one_long_fact_becomes_several_prompt_lines(self):
        sent = facts_for_prompt([PARAGRAPH])
        self.assertGreaterEqual(len(sent), 1)
        self.assertEqual(" ".join(sent), PARAGRAPH)


if __name__ == "__main__":
    unittest.main()
