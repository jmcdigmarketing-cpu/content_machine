"""Run 74: an article pasted at `Fact N` must survive intake whole.

The Engadget link returned HTTP 403, so the CLI told the operator to paste the
article text. They pasted it at the `Fact N` prompt rather than typing `paste`
first — a reasonable thing to do, since that prompt accepts pasted lines. The
loop read line 1 as fact 51, line 2 as fact 52, and then hit the article's first
blank line, which it treated as "operator pressed Enter, done". Intake ended
after two lines; ~40 paragraphs stayed in the console buffer and went on to
answer the prompts that followed, ending the run.

A blank line may only end intake when nothing else is buffered. Whatever is still
buffered when the loop does end is offered back as facts, not discarded.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.ui import prompt_key_facts_result

# The shape that broke: headline, subtitle, paragraph break, byline, body.
ENGADGET_PASTE = [
    "20+ things you may have missed in the GTA 6 extended look",
    "Prepare for six stars, two playable characters and one hell of a ride.",
    "",
    "Arguably the most anticipated video game of all time is almost upon us. "
    "Netflix bagged an exclusive 26-minute extended look of GTA VI.",
    "",
    "It turns out a lot. Seeing as Grand Theft Auto VI could take you more than "
    "80 hours to finish, Rockstar North has cooked up new in-game mechanics.",
]


class _PasteBuffer:
    """A scripted console: `input_fn` pops a line, `pending` says more is coming."""

    def __init__(self, *lines: str):
        self.lines = list(lines)
        self.calls = 0

    def __call__(self, _prompt: str = "") -> str:
        self.calls += 1
        return self.lines.pop(0) if self.lines else ""

    def pending(self) -> bool:
        return bool(self.lines)

    def drain(self) -> list[str]:
        rest, self.lines = self.lines, []
        return rest


class _Printed(list):
    """`subsection()` calls print_fn() with no argument, so plain .append will not do."""

    def __call__(self, *args) -> None:
        self.append(args[0] if args else "")


def _collect(buffer: _PasteBuffer) -> list[str]:
    printed = _Printed()
    with (
        patch("core.obsidian_facts.load_fact_records", return_value=[]),
        patch("core.operator_facts.capture_facts_to_vault", return_value=None),
        patch("core.console_input.input_pending", side_effect=buffer.pending),
        patch("core.console_input.read_pending_lines", side_effect=buffer.drain),
    ):
        result = prompt_key_facts_result(
            "GTA 6 extended look",
            "tapin",
            signals={},
            print_fn=printed,
            input_fn=buffer,
        )
    return result.facts


class TestABlankLineMidPasteIsNotTheEnd(unittest.TestCase):
    def test_every_paragraph_survives_the_paragraph_breaks(self):
        facts = _collect(_PasteBuffer(*ENGADGET_PASTE))
        joined = " ".join(facts)
        for paragraph in (p for p in ENGADGET_PASTE if p):
            self.assertIn(paragraph[:50], joined, f"lost: {paragraph[:50]}")

    def test_the_run_74_body_is_not_dropped_after_two_lines(self):
        facts = _collect(_PasteBuffer(*ENGADGET_PASTE))
        self.assertGreaterEqual(len(facts), 4)
        self.assertTrue(any("80 hours" in f for f in facts))


class TestABlankLineStillEndsIntakeWhenTypedByHand(unittest.TestCase):
    """No new friction for someone typing facts one at a time."""

    def test_empty_answer_with_nothing_buffered_ends_intake(self):
        buffer = _PasteBuffer("Islam Makhachev is the lightweight champion", "")
        facts = _collect(buffer)
        self.assertEqual(len(facts), 1)
        # Asked twice: the fact, then the blank that ended it. Never a third time.
        self.assertEqual(buffer.calls, 2)


class TestOverflowIsRecoveredNotDiscarded(unittest.TestCase):
    """Whatever is still buffered when intake ends is offered back as facts."""

    def test_buffered_lines_are_offered_and_kept(self):
        # input_pending is False (the operator's Enter looked deliberate) but the
        # buffer still holds the rest of the article.
        printed = _Printed()
        answers = iter(["First fact about Grand Theft Auto 6 and its release.", "", "y"])
        leftovers = [
            "Rockstar Games confirmed the game ships on November 19 this year.",
            "The extended look ran for 26 minutes on Netflix before YouTube.",
        ]
        drained = {"done": False}

        def drain() -> list[str]:
            if drained["done"]:
                return []
            drained["done"] = True
            return list(leftovers)

        with (
            patch("core.obsidian_facts.load_fact_records", return_value=[]),
            patch("core.operator_facts.capture_facts_to_vault", return_value=None),
            patch("core.console_input.input_pending", return_value=False),
            patch("core.console_input.read_pending_lines", side_effect=drain),
        ):
            result = prompt_key_facts_result(
                "GTA 6 extended look",
                "tapin",
                signals={},
                print_fn=printed,
                input_fn=lambda *_a, **_k: next(answers),
            )

        joined = " ".join(result.facts)
        self.assertIn("November 19", joined)
        self.assertIn("26 minutes", joined)
        self.assertIn("pasted", " ".join(printed).lower())

    def test_declining_the_offer_leaves_them_out(self):
        printed = _Printed()
        answers = iter(["First fact about Grand Theft Auto 6 and its release.", "", "n"])
        drained = {"done": False}

        def drain() -> list[str]:
            if drained["done"]:
                return []
            drained["done"] = True
            return ["Rockstar Games confirmed the game ships on November 19 this year."]

        with (
            patch("core.obsidian_facts.load_fact_records", return_value=[]),
            patch("core.operator_facts.capture_facts_to_vault", return_value=None),
            patch("core.console_input.input_pending", return_value=False),
            patch("core.console_input.read_pending_lines", side_effect=drain),
        ):
            result = prompt_key_facts_result(
                "GTA 6 extended look",
                "tapin",
                signals={},
                print_fn=printed,
                input_fn=lambda *_a, **_k: next(answers),
            )
        self.assertNotIn("November 19", " ".join(result.facts))


if __name__ == "__main__":
    unittest.main()
