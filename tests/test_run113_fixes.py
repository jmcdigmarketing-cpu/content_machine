"""#972: four defects in run 113 (operator, 2026-10-04, "NBA preseason hot takes").

- Grounding reported "Somebody" as a specific the facts did not back ("Somebody has to be
  the East favorite"): in a sports script any capitalised 4+ letter word is a candidate
  name, and indefinite pronouns were in no shared list. "You're" too.
- The description said "Giannis and Bam look unstoppable in Heat preseason" as fact. The
  claim rewrite had restated it in the script as a rumor, but the description was written
  with the first draft and never revisited.
- Auto-research read 0 pages before its deadline and kept nothing; #964's Google News
  fallback ran only when web search returned no results at all.
- The Fact quality preview ended on a section heading ("Blog/RSS:") whose lines were cut off.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = (
    "You're punishing them for being good early. The Knicks just won a title. "
    "Somebody has to be the East favorite, and Miami's the team that looks assembled. "
    "Everyone saw it."
)


class PronounTests(unittest.TestCase):
    def test_pronouns_are_not_specifics(self):
        from core.facts.grounding import find_ungrounded_entities

        flagged = find_ungrounded_entities(SCRIPT, "The Knicks won the title. Miami Heat NBA")
        for word in ("Somebody", "You're", "Everyone"):
            self.assertNotIn(word, flagged)

    def test_a_possessive_name_is_grounded_by_the_name(self):
        from core.facts.grounding import find_ungrounded_entities

        flagged = find_ungrounded_entities(SCRIPT, "The Knicks won the title. Miami Heat NBA")
        self.assertNotIn("Miami's", flagged)

    def test_a_real_unbacked_name_is_still_flagged(self):
        from core.facts.grounding import find_ungrounded_entities

        script = "Wembanyama dropped forty in the NBA preseason opener."
        self.assertIn("Wembanyama", find_ungrounded_entities(script, "NBA preseason opener"))


class DescriptionTests(unittest.TestCase):
    DESC = (
        "Giannis and Bam look unstoppable in Heat preseason — but is Miami peaking too early? "
        "We debate whether preseason chemistry is a contender signal or a classic trap. "
        "Drop your take below."
    )

    def test_a_sentence_restating_an_unbacked_claim_is_dropped(self):
        from core.youtube_meta import drop_unbacked_sentences

        desc, dropped = drop_unbacked_sentences(
            self.DESC, ["Giannis and Bam look unstoppable in preseason."]
        )
        self.assertNotIn("unstoppable", desc)
        self.assertTrue(desc.startswith("We debate"))
        self.assertEqual(len(dropped), 1)

    def test_nothing_unbacked_leaves_it_alone(self):
        from core.youtube_meta import drop_unbacked_sentences

        self.assertEqual(drop_unbacked_sentences(self.DESC, []), (self.DESC, []))

    def test_it_never_empties_the_description(self):
        from core.youtube_meta import drop_unbacked_sentences

        desc, _ = drop_unbacked_sentences("Giannis and Bam look unstoppable in preseason.",
                                          ["Giannis and Bam look unstoppable in preseason"])  # fmt: skip
        self.assertTrue(desc.strip())


class ZeroPagesTests(unittest.TestCase):
    def test_every_page_timing_out_falls_back_to_news(self):
        from core.auto_research import attach_web_research

        signals = {
            "web_search": {
                "connected": True,
                "active": True,
                "data": {"results": [{"url": "https://slow.example/a", "title": "NBA preseason",
                                      "snippet": "s"}]},
            }
        }  # fmt: skip
        with (
            patch.dict(os.environ, {"AUTO_RESEARCH_NEWS_FALLBACK": "true"}),
            patch("core.auto_research._read", return_value=[]),
            patch("core.event_research.google_news_headlines",
                  return_value=["Heat beat Raptors in preseason opener (Sun, 04 Oct 2026)"]),
        ):  # fmt: skip
            out, report = attach_web_research(
                signals, angle="Heat preseason", topic="NBA preseason"
            )
        self.assertIn("web_research", out)
        self.assertTrue(report["reason"].startswith("news fallback"))

    def test_the_line_says_what_happened(self):
        from core.auto_research import report_line

        line = report_line({"reason": "news fallback (deadline)", "lines": 3, "pages": 0})
        self.assertIn("3 Google News headline(s)", line)
        self.assertIn("deadline", line)


class PreviewTests(unittest.TestCase):
    def test_the_preview_never_ends_on_an_empty_heading(self):
        from core.ui import display_fact_preview

        facts = "News headlines:\n" + "\n".join(f"- headline {i}" for i in range(6))
        facts += "\nBlog/RSS:\n- a blog headline\n- another"
        printed: list[str] = []
        display_fact_preview(facts, print_fn=lambda *a, **k: printed.append(" ".join(map(str, a))))
        shown = [p.strip() for p in printed if p.strip()]
        self.assertNotEqual(shown[-1], "Blog/RSS:")
        self.assertFalse(any(p == "Blog/RSS:" for p in shown))
        self.assertTrue(any("more" in p for p in shown))


class ContentEngineTests(unittest.TestCase):
    def test_the_package_description_drops_the_rewritten_claim(self):
        from core.content_engine import _final_description

        before = SimpleNamespace(
            unsupported=[SimpleNamespace(claim="Giannis and Bam look unstoppable in preseason")]
        )
        after = SimpleNamespace(unsupported=[])
        desc = _final_description(DescriptionTests.DESC, before, after)
        self.assertNotIn("unstoppable", desc)
        self.assertIn("We debate", desc)


if __name__ == "__main__":
    unittest.main()
