"""#1012: lines pasted at the `Fact N` prompt skip the filter a link or a block gets.

Run 124 (2026-10-08): the operator pasted a Yahoo article at `Fact N`, so it arrived one
line per prompt. Each line was a typed fact - "never questioned" and pinned at score 2.0 -
and the script was handed "Shopify", "Sponsored", "call to action icon", "View on Watch",
"Current Time", "0:00", "/", "Duration", "1:06", "0", "html", the ad copy "Get started
faster, no design skills needed." and the article's subheads as key facts. The same URL
was then fetched a second time, adding its 13 lines again.

- `core.operator_facts.is_junk_line`: page chrome, bare symbols and numbers, ad and video-
  player furniture, "Related video:" captions and single words are never facts.
- `core.operator_facts.clean_typed_lines`: a line that arrived inside a paste (more input
  was buffered around it) is read as page text - fewer than 4 words without a number, or a
  short subhead, is dropped; an ad marker ("Sponsored") drops the short lines since the
  last paragraph (the ad unit it closes). A line typed on its own keeps the operator's
  benefit of the doubt.
- `core.ui`: a URL already read this run is not fetched again; the skipped lines are
  named once.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.ui import prompt_key_facts_result

PARA_1 = (
    "The Chargers are one of the biggest disappointments of the 2026 season. Despite "
    "massive expectations, they are 0-4 for the first time since 2017."
)
PARA_2 = (
    "Left tackle Rashawn Slater is out for 4 to 6 weeks with a high ankle sprain. "
    "Compounding that, right tackle Joe Alt is expected to miss Sunday's game."
)
PARA_3 = (
    "The Chargers' pass-catching room took another hit when wide receiver Ladd McConkey "
    "reaggravated a persistent foot injury during last week's loss to the Seahawks."
)

# Run 124, in the order it arrived (blank lines are the article's paragraph breaks).
RUN_124 = [
    "The Chargers look to pick up their first win of the season as they face the Broncos on Sunday afternoon.",
    "",
    "Overcoming a disastrous start",
    PARA_1,
    "",
    "Get started faster, no design skills needed.",
    "Get started faster, no design skills needed.",
    "Shopify",
    "Shopify",
    "·",
    "Sponsored",
    "call to action icon",
    "",
    "Dealing with a depleted offensive line",
    PARA_2,
    "",
    "Related video: Chargers at 0-4 could turn trade deadline sellers, says Tom Pelissero (Sportsnaut)",
    "View on Watch",
    "View on Watch",
    "",
    "Sportsnaut",
    "Current Time",
    "0:00",
    "/",
    "Duration",
    "1:06",
    "0",
    "Making up for no McConkey",
    PARA_3,
    "html",
]

JUNK = ["Shopify", "Sponsored", "call to action icon", "View on Watch", "Current Time",
        "0:00", "/", "Duration", "1:06", "0", "html", "·", "Sportsnaut",
        "Get started faster, no design skills needed.", "Overcoming a disastrous start",
        "Making up for no McConkey", "Dealing with a depleted offensive line",
        "Related video: Chargers at 0-4"]  # fmt: skip


class _PasteBuffer:
    def __init__(self, *lines: str):
        self.lines = list(lines)

    def __call__(self, _prompt: str = "") -> str:
        return self.lines.pop(0) if self.lines else ""

    def pending(self) -> bool:
        # A hand-typed line has nothing buffered behind it: the Enter that ends intake is
        # typed later. Only text still waiting reads as a paste.
        return any(self.lines)

    def drain(self) -> list[str]:
        rest, self.lines = self.lines, []
        return rest


class _Printed(list):
    def __call__(self, *args) -> None:
        self.append(args[0] if args else "")


def _collect(buffer, *, extract=None):
    printed = _Printed()
    with (
        patch("core.obsidian_facts.load_fact_records", return_value=[]),
        patch("core.operator_facts.capture_facts_to_vault", return_value=None),
        patch("core.console_input.input_pending", side_effect=buffer.pending),
        patch("core.console_input.read_pending_lines", side_effect=buffer.drain),
        patch("core.link_facts.extract_facts_from_url", side_effect=extract or (lambda u: [])),
    ):
        result = prompt_key_facts_result(
            "How the 0-4 chargers can turn it around this year",
            "tapin",
            signals={},
            print_fn=printed,
            input_fn=buffer,
        )
    return result.facts, "\n".join(str(p) for p in printed)


class PasteAtFactPromptTests(unittest.TestCase):
    def test_run_124_keeps_the_article_and_drops_the_page(self):
        facts, text = _collect(_PasteBuffer(*RUN_124))
        joined = "\n".join(facts)
        for para in (PARA_1, PARA_2, PARA_3):
            self.assertIn(para[:60], joined)
        self.assertIn("face the Broncos on Sunday", joined)
        for junk in JUNK:
            self.assertFalse(
                any(f.strip() == junk or f.startswith(junk) for f in facts), f"kept: {junk!r}"
            )
        self.assertIn("Skipped", text)
        self.assertIn("Shopify", text)

    def test_a_short_fact_typed_by_hand_stays(self):
        facts, _text = _collect(_PasteBuffer("Herbert benched", ""))
        self.assertEqual(facts, ["Herbert benched"])

    def test_a_single_word_typed_by_hand_is_not_a_fact(self):
        facts, _text = _collect(_PasteBuffer("Shopify", ""))
        self.assertEqual(facts, [])

    def test_the_same_link_is_read_once(self):
        url = "https://sports.yahoo.com/articles/justin-herbert-offers-glimmer-hope-035606510.html"
        calls: list[str] = []

        def extract(u):
            calls.append(u)
            return ["Chargers QB Justin Herbert has struggled through the first 4 games."]

        with (
            patch("core.link_facts.looks_like_url", side_effect=lambda s: s.startswith("http")),
            patch("core.link_facts.last_extract_report", return_value={"title": "T"}),
        ):
            _facts, text = _collect(_PasteBuffer(url, url, ""), extract=extract)
        self.assertEqual(len(calls), 1)
        self.assertIn("already read", text)


class JunkLineTests(unittest.TestCase):
    def test_junk(self):
        from core.operator_facts import is_junk_line

        for line in ("0", "/", "·", "1:06", "0:00 / 3:38", "Sponsored", "html", "Shopify",
                     "call to action icon", "View on Watch", "Duration", "Current Time",
                     "Related video: Chargers at 0-4 could turn sellers (Sportsnaut)"):  # fmt: skip
            self.assertTrue(is_junk_line(line), line)
        for line in ("Herbert benched", "Chargers are 0-4", PARA_1):
            self.assertFalse(is_junk_line(line), line)

    def test_link_lines_drop_sponsored_content(self):
        from core.link_facts import _JUNK_MARKERS

        self.assertTrue(any("sponsored" in m for m in _JUNK_MARKERS))


if __name__ == "__main__":
    unittest.main()
