"""Wave 73: #1111 an ordinary word that is a game name, #1112 the gaps report reads the run.

Both were found building wave 72 and left open:

- "the steep price of GPUs" named the Steep folder - one whole word, and the word is English.
- `ops footage-gaps` chose footage with no run context, so "The one tactical mistake that
  decided the semi-final" (runs 58 and 59, World Cup videos) showed as a gaming mix. In a run
  the seed and the stored sport stop that.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

GAMES = [
    "gaming/open world/GTA V",
    "gaming/multiplayer games/Fortnite",
    "gaming/multiplayer games/Overwatch",
    "gaming/other/Steep",
    "gaming/sports/EA Sports FC",
    "gaming/sports/UFC 5",
]
FOLDERS = [os.path.join("video", "backgrounds", *g.split("/")) for g in GAMES]


def _name(folder):
    return os.path.basename(folder) if folder else None


class OrdinaryWordGameTests(unittest.TestCase):
    def _pick(self, topic, **kw):
        from assets.local_provider import _keyword_choose_folder

        return _name(_keyword_choose_folder(topic, FOLDERS, **kw))

    def test_the_word_used_as_a_word_is_not_the_game(self):
        for topic in (
            "the steep price of GPUs",
            "A steep climb back for the Chargers",
            "Steep price hike hits console buyers",
        ):
            self.assertIsNone(self._pick(topic), topic)

    def test_the_game_written_as_a_name_is_found(self):
        self.assertEqual(self._pick("Is Steep still worth playing in 2026"), "Steep")

    def test_the_word_in_a_gaming_topic_is_the_game(self):
        self.assertEqual(self._pick("steep snowboarding video game is free this week"), "Steep")

    def test_a_name_that_is_not_a_word_needs_no_capital(self):
        self.assertEqual(self._pick("fortnite reload is back"), "Fortnite")
        self.assertEqual(self._pick("overwatch nerfs explained"), "Overwatch")

    def test_a_capture_file_name_is_always_the_game(self):
        """`ops ingest-clips`: Game Bar writes the window title, in any case."""
        from assets.clip_ingest import match_folder

        self.assertEqual(_name(match_folder("steep 2026-08-19 12-40-15.mp4", FOLDERS)), "Steep")

    def test_the_shared_list_holds_the_word(self):
        from apis.topic_tokens import GAME_NAMES_THAT_ARE_WORDS

        self.assertIn("steep", GAME_NAMES_THAT_ARE_WORDS)
        self.assertNotIn("fortnite", GAME_NAMES_THAT_ARE_WORDS)


class RunContextTests(unittest.TestCase):
    def setUp(self):
        from assets import local_provider

        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        for rel in GAMES:
            path = os.path.join(self.root, *rel.split("/"))
            os.makedirs(path, exist_ok=True)
            Path(path, "clip0.mp4").write_bytes(b"x")
        self.folders = sorted(local_provider._get_subfolders(self.root))
        local_provider.reset_footage_choices()
        self.addCleanup(local_provider.reset_footage_choices)

    ANGLE = "The one tactical mistake that decided the semi-final"

    def test_a_given_context_picks_the_runs_sport(self):
        from assets import local_provider as lp

        folder, how = lp.choose_footage(
            self.ANGLE, self.folders, "tapin", use_llm=False, context=("", "soccer")
        )
        self.assertEqual((_name(folder), how), ("EA Sports FC", "run-domain"))

    def test_a_given_context_stops_the_mix(self):
        from assets import local_provider as lp

        self.assertTrue(lp.mix_folders(self.ANGLE, self.folders, "tapin"))
        self.assertEqual(lp.mix_folders(self.ANGLE, self.folders, "tapin", context=("", "nhl")), [])

    def test_a_given_context_leaves_no_state_behind(self):
        from assets import local_provider as lp

        lp.choose_footage(self.ANGLE, self.folders, "tapin", use_llm=False, context=("", "soccer"))
        self.assertEqual(
            lp.choose_footage(self.ANGLE, self.folders, "tapin", use_llm=False), (None, "none")
        )

    def _report(self, contexts, provider="hybrid", source_id=""):
        from assets import footage_gaps, local_provider

        runs = [
            SimpleNamespace(id=58, selected_topic=self.ANGLE, input_topic="World Cup semi finals"),
            SimpleNamespace(id=60, selected_topic="If Steam Machine costs more", input_topic=""),
        ]
        background = SimpleNamespace(
            asset_type="background", provider=provider, source_id=source_id, path="x.mp4"
        )
        with (
            patch.object(local_provider, "BASE_VIDEO_DIR", self.root),
            patch.object(local_provider, "_ai_choose_folder", side_effect=AssertionError("model")),
            patch.object(
                local_provider, "footage_context_for_run", side_effect=lambda rid: contexts[rid]
            ),
            patch.object(
                footage_gaps,
                "_run_repo",
                return_value=SimpleNamespace(list_for_channel=lambda cid, status=None: runs),
            ),
            patch.object(
                footage_gaps,
                "_asset_repo",
                return_value=SimpleNamespace(list_for_run=lambda rid: [background]),
            ),
        ):
            return footage_gaps.footage_gaps("tapin"), footage_gaps.footage_gap_lines("tapin")

    def test_the_report_reads_each_runs_sport(self):
        report, lines = self._report({58: ("World Cup semi finals", "soccer"), 60: ("", "")})
        risky = {row["run_id"]: row for row in report["at_risk"]}
        self.assertEqual(risky[58]["now"], "EA Sports FC")
        self.assertEqual(risky[60]["how"], "mix")
        text = "\n".join(lines)
        self.assertIn("now EA Sports FC", text)
        self.assertIn("now a mix of owned games", text)

    def test_a_sport_with_no_footage_is_not_called_a_mix(self):
        report, lines = self._report({58: ("Stanley Cup final", "nhl"), 60: ("", "")})
        risky = {row["run_id"]: row for row in report["at_risk"]}
        self.assertEqual((risky[58]["now"], risky[58]["how"]), (None, "none"))
        self.assertIn("now no footage of its own: stock or plain", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
