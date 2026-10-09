"""#1001: "yes" at the seed prompt is a yes, and the seed keeps the teams and the week.

Run 118: `main._ask_topic_or_thoughts` asked "Search for this? [Enter = yes, or type a better
seed]" and the operator typed "yes" - which became the search seed: Wikipedia "Yes", "77 news
headline(s) named yes", an earnings lookup for a ticker built from it. And the seed pulled
out of "NFl analysis of week 4 with the seahawks and chargers ..." was "nfl": the two teams
and the week were dropped.

- y / yes / ok / okay / sure / yep / yeah accept the seed, like Enter.
- `core.idea_intake.search_seed_from_thoughts` keeps the teams it names (as nicknames, via
  `team_names_in`) and a "week N".
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

RUN_118 = (
    "NFl analysis of week 4 with the seahawks and chargers, what went wrong and what is "
    "next for both teams going forward"
)


class SeedTests(unittest.TestCase):
    def test_the_seed_keeps_the_teams_and_the_week(self):
        from core.idea_intake import parse_pasted_idea

        seed = parse_pasted_idea(RUN_118).seed_topic.lower()
        self.assertIn("seahawks", seed)
        self.assertIn("chargers", seed)
        self.assertIn("week 4", seed)

    def test_yes_accepts_the_seed(self):
        import main

        for answer in ("yes", "y", "ok", "Yes", "sure"):
            with (
                patch("main.ask_text", side_effect=[RUN_118, answer]),
                patch("core.console_input.input_pending", return_value=False),
                redirect_stdout(io.StringIO()),
            ):
                topic, _brief = main._ask_topic_or_thoughts()
            self.assertNotEqual(topic.lower(), answer.lower())
            self.assertIn("chargers", topic.lower())

    def test_a_typed_seed_still_replaces_it(self):
        import main

        with (
            patch("main.ask_text", side_effect=[RUN_118, "seahawks chargers recap"]),
            patch("core.console_input.input_pending", return_value=False),
            redirect_stdout(io.StringIO()),
        ):
            topic, _brief = main._ask_topic_or_thoughts()
        self.assertEqual(topic, "seahawks chargers recap")


if __name__ == "__main__":
    unittest.main()
