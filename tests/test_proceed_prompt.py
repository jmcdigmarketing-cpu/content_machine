"""Candidate 325: a paste at `Proceed?` must not silently discard the run.

Live-run 71 cost 30.6 minutes wall — 25.6 of them at prompts, 5.0 machine — and
produced no video, because the operator pasted an article paragraph at:

    Proceed? [y = render / + longer / - shorter / 1-4 length / N = stop]:

`prompt_proceed_or_length` returned ("stop", ...) for anything that was not `y`, `+`,
`-` or `1`-`4`. The trap is structural, not carelessness: the key-facts loop directly
above *does* accept pasted blocks, so the habit carries straight into a prompt where a
paste means "throw the run away".

Declining stays instant — the contract for `n` / `N` / Enter does not move. Only input
that is obviously prose earns a second chance.
"""

import unittest

from core.ui import _looks_pasted, prompt_proceed_or_length

# The exact text that ended run 71.
RUN71_PASTE = (
    "On Thursday, Take-Two Interactive filed subpoenas against both Microsoft and "
    "Discord in the Southern District Court of New York, which Kotaku first spotted"
)


class _Answers:
    """Scripted input_fn; records how many times it was asked."""

    def __init__(self, *answers: str):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, _prompt: str = "") -> str:
        self.calls += 1
        return self.answers.pop(0) if self.answers else ""


class TestMenuKeysAreUnchanged(unittest.TestCase):
    """Every documented answer must behave exactly as before, on the first ask."""

    def test_render(self):
        ask = _Answers("y")
        self.assertEqual(prompt_proceed_or_length("2", input_fn=ask), ("render", "2"))
        self.assertEqual(ask.calls, 1)

    def test_uppercase_and_padding_still_render(self):
        self.assertEqual(prompt_proceed_or_length("2", input_fn=_Answers("  Y ")), ("render", "2"))

    def test_explicit_length(self):
        for key in ("1", "2", "3", "4"):
            ask = _Answers(key)
            self.assertEqual(prompt_proceed_or_length("2", input_fn=ask), ("relength", key))
            self.assertEqual(ask.calls, 1)

    def test_nudges(self):
        self.assertEqual(prompt_proceed_or_length("2", input_fn=_Answers("+"))[0], "relength")
        self.assertEqual(prompt_proceed_or_length("2", input_fn=_Answers("-"))[0], "relength")


class TestDecliningIsStillInstant(unittest.TestCase):
    """No extra friction for someone who meant to stop."""

    def test_n_stops_on_the_first_answer(self):
        ask = _Answers("n")
        self.assertEqual(prompt_proceed_or_length("2", input_fn=ask), ("stop", "2"))
        self.assertEqual(ask.calls, 1)

    def test_uppercase_n_stops(self):
        ask = _Answers("N")
        self.assertEqual(prompt_proceed_or_length("2", input_fn=ask), ("stop", "2"))
        self.assertEqual(ask.calls, 1)

    def test_no_stops(self):
        self.assertEqual(prompt_proceed_or_length("2", input_fn=_Answers("no")), ("stop", "2"))

    def test_empty_stops_on_the_first_answer(self):
        ask = _Answers("")
        self.assertEqual(prompt_proceed_or_length("2", input_fn=ask), ("stop", "2"))
        self.assertEqual(ask.calls, 1)

    def test_a_stray_keystroke_is_still_a_stop(self):
        # Someone reaching for N and missing meant to decline — do not nag.
        ask = _Answers("m")
        self.assertEqual(prompt_proceed_or_length("2", input_fn=ask), ("stop", "2"))
        self.assertEqual(ask.calls, 1)


class TestTheRun71Paste(unittest.TestCase):
    def test_paste_reprompts_instead_of_discarding(self):
        ask = _Answers(RUN71_PASTE, "y")
        lines: list[str] = []
        self.assertEqual(
            prompt_proceed_or_length("3", input_fn=ask, print_fn=lines.append), ("render", "3")
        )
        self.assertEqual(ask.calls, 2)

    def test_the_operator_is_told_what_happened(self):
        lines: list[str] = []
        prompt_proceed_or_length("3", input_fn=_Answers(RUN71_PASTE, "n"), print_fn=lines.append)
        text = "\n".join(lines)
        self.assertIn("pasted text", text)
        self.assertIn("still here", text)
        self.assertIn("paste", text)  # points at where the article actually belongs

    def test_a_second_unrecognised_answer_stops(self):
        ask = _Answers(RUN71_PASTE, RUN71_PASTE)
        self.assertEqual(
            prompt_proceed_or_length("3", input_fn=ask, print_fn=lambda *_: None), ("stop", "3")
        )
        self.assertEqual(ask.calls, 2)

    def test_declining_after_the_reprompt_stops(self):
        ask = _Answers(RUN71_PASTE, "n")
        self.assertEqual(
            prompt_proceed_or_length("3", input_fn=ask, print_fn=lambda *_: None), ("stop", "3")
        )

    def test_relength_after_the_reprompt_works(self):
        ask = _Answers(RUN71_PASTE, "4")
        self.assertEqual(
            prompt_proceed_or_length("3", input_fn=ask, print_fn=lambda *_: None), ("relength", "4")
        )

    def test_it_never_asks_a_third_time(self):
        ask = _Answers(RUN71_PASTE, RUN71_PASTE, "y")
        result = prompt_proceed_or_length("3", input_fn=ask, print_fn=lambda *_: None)
        self.assertEqual(result, ("stop", "3"))
        self.assertEqual(ask.calls, 2)


class TestPasteDetection(unittest.TestCase):
    def test_prose_and_urls_look_pasted(self):
        for text in (
            RUN71_PASTE,
            "https://www.msn.com/en-us/money/other/take-two-interactive-subpoenas-microsoft",
            "Standard Edition PS5 - $79.97",
            "line one\nline two",
        ):
            self.assertTrue(_looks_pasted(text), text[:40])

    def test_menu_shaped_input_does_not(self):
        for text in ("", "y", "n", "3", "+", "-", "yes", "quit"):
            self.assertFalse(_looks_pasted(text), text)


if __name__ == "__main__":
    unittest.main()
