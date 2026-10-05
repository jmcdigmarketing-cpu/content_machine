"""#962 (and run 113): footage follows the run, not only the angle's wording.

Footage is chosen from the text the render is given - the angle. Run 113's angle, "Which
team's preseason chemistry suggests they're peaking too early", had dropped the "NBA" the
operator typed ("NBA preseason hot takes"), so it got stock footage although the library
has 2K26. Five soccer runs ("The one tactical mistake that decided the semi-final") named
no league either (#962). Now the render tells the chooser the run's own topic and the
sport its facts name; they are tried after the angle's words and before the model.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

FOLDERS = [
    "/lib/gaming/sports/2k26",
    "/lib/gaming/sports/UFC 5",
    "/lib/gaming/sports/EA Sports FC",
    "/lib/gaming/open world/GTA V",
]
ANGLE = "Which team's preseason chemistry suggests they're peaking too early"
SOCCER = "The one tactical mistake that decided the semi-final"


class ContextTests(unittest.TestCase):
    def setUp(self):
        from assets import local_provider

        local_provider.reset_footage_choices()
        self.addCleanup(local_provider.reset_footage_choices)

    def test_the_angle_alone_finds_nothing(self):
        from assets.local_provider import choose_footage

        self.assertEqual(choose_footage(ANGLE, FOLDERS, "tapin", use_llm=False), (None, "none"))

    def test_the_runs_own_topic_finds_the_game(self):
        from assets.local_provider import choose_footage, set_footage_context

        set_footage_context(ANGLE, seed="NBA preseason hot takes")
        folder, how = choose_footage(ANGLE, FOLDERS, "tapin", use_llm=False)
        self.assertEqual(folder, "/lib/gaming/sports/2k26")
        self.assertEqual(how, "seed")

    def test_the_runs_sport_finds_the_game(self):
        from assets.local_provider import choose_footage, set_footage_context

        set_footage_context(SOCCER, domain="soccer")
        folder, how = choose_footage(SOCCER, FOLDERS, "tapin", use_llm=False)
        self.assertEqual(folder, "/lib/gaming/sports/EA Sports FC")
        self.assertEqual(how, "run-domain")

    def test_the_angles_own_words_still_win(self):
        from assets.local_provider import choose_footage, set_footage_context

        set_footage_context("UFC 5 patch notes", seed="NBA preseason", domain="nba")
        folder, _how = choose_footage("UFC 5 patch notes", FOLDERS, "tapin", use_llm=False)
        self.assertEqual(folder, "/lib/gaming/sports/UFC 5")

    def test_the_channels_own_domain_is_not_a_sport(self):
        from assets.local_provider import choose_footage, set_footage_context

        set_footage_context(SOCCER, domain="gaming")
        self.assertEqual(choose_footage(SOCCER, FOLDERS, "tapin", use_llm=False)[0], None)


class FromRunTests(unittest.TestCase):
    def test_the_context_comes_from_the_saved_run(self):
        from assets.local_provider import footage_context_for_run

        run = SimpleNamespace(input_topic="NBA preseason hot takes",
                              features_json=json.dumps({"domains": {"topic": "neutral"}}))  # fmt: skip
        repo = SimpleNamespace(get=lambda rid: run)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            seed, domain = footage_context_for_run(113)
        self.assertEqual(seed, "NBA preseason hot takes")
        self.assertEqual(domain, "nba")

    def test_the_stored_topic_domain_wins(self):
        from assets.local_provider import footage_context_for_run

        run = SimpleNamespace(input_topic=SOCCER,
                              features_json=json.dumps({"domains": {"topic": "soccer"}}))  # fmt: skip
        repo = SimpleNamespace(get=lambda rid: run)
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            self.assertEqual(footage_context_for_run(7), (SOCCER, "soccer"))

    def test_no_run_no_context(self):
        from assets.local_provider import footage_context_for_run

        self.assertEqual(footage_context_for_run(None), ("", ""))


if __name__ == "__main__":
    unittest.main()
