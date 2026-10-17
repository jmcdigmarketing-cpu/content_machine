"""Wave 92 (#1205, #1181, #1182, #1183, #1206): what the drafts and uploads said.

- Run 153 (overnight, 2026-10-15) was drafted from the arc seed "Shavkat Rakhmonov week 4":
  angle "Shavkat Rakhmonov's week 4 performance leaves questions unanswered", script "So week
  four is progress without a finish line." The 4 is the UFC arc's counter - how many UFC videos
  the channel has made - attached to whoever the last one was about.
- Run 149's title read "... After Denver Loss Angeles Stays Optimistic", and the title check
  passed it.
- Run 152 (Ravens at Browns) stored its domain as neutral: it was read from the angle headline.
- Thumbnails keep the title's first four words: "Topuria's Outlook: Can He".
- Run 132's upload warned that "Sources:" was glued to the line above - a description written
  before the builder fix went out as stored.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

# ---- #1205: the arc's counter stays out of the topic --------------------------------------------


def _graph(last_topic, ordinal):
    return {
        "channels": {
            "tapin": {
                "arcs": {
                    "ufc": {
                        "ordinal": ordinal,
                        "last_topic": last_topic,
                        "updated_at": "2026-10-15T20:00:00+00:00",
                    }
                }
            }
        }
    }


class ArcTests(unittest.TestCase):
    def _seed(self, last_topic, ordinal):
        from core import topic_graph

        with patch.object(topic_graph, "_load", return_value=_graph(last_topic, ordinal)):
            return topic_graph.follow_up_seed("tapin")

    def test_run153_the_counter_is_not_the_fighters_week(self):
        seed = self._seed("Shavkat Rakhmonov week 3", 3)
        self.assertEqual(seed.topic, "Shavkat Rakhmonov")
        self.assertNotIn("week", seed.topic.lower())
        self.assertIn("4", seed.rationale)  # the count is kept where the operator reads it

    def test_a_repeat_of_the_last_topic_is_not_offered(self):
        seed = self._seed("UFC Illia Islam", 4)
        self.assertIsNone(seed)

    def test_the_count_still_moves_on(self):
        from core import topic_graph

        saved = {}
        with (
            patch.object(topic_graph, "_load", return_value=_graph("Shavkat Rakhmonov week 3", 3)),
            patch.object(topic_graph, "_save", side_effect=saved.update),
        ):
            topic_graph.record_published_topic("tapin", "Shavkat Rakhmonov at UFC 336")
        self.assertEqual(saved["channels"]["tapin"]["arcs"]["ufc"]["ordinal"], 4)


# ---- #1181: a title that breaks a place name ---------------------------------------------------------


RUN149 = "Chargers Hopeium: Harbaugh's Bold Move After Denver Loss Angeles Stays Optimistic"


class BrokenNameTests(unittest.TestCase):
    def test_run149_los_angeles_lost_its_los(self):
        from core.title_generator import broken_place_name

        self.assertEqual(broken_place_name(RUN149), "Los Angeles")

    def test_whole_names_and_first_names_pass(self):
        from core.title_generator import broken_place_name

        for title in (
            "Los Angeles Chargers Hopeium Into Week 5",
            "Raiders Leave Las Vegas Early",
            "New Orleans Saints at New York Giants",
            "Antonio Brown And Diego Lopes Walk Into A Bar",
        ):
            self.assertEqual(broken_place_name(title), "", title)

    def test_the_title_check_fails_it_so_it_is_regenerated(self):
        from core.youtube_meta import check_title_script_consistency

        clean = SimpleNamespace(unsupported=[], total=1)
        with patch("core.claim_verifier.verify_claims", return_value=clean):
            result = check_title_script_consistency(RUN149, "Script about the Chargers.")
        self.assertEqual(result["status"], "failed")
        self.assertIn("Los Angeles", " ".join(result["warnings"]))


# ---- #1182: a game run's stored domain -------------------------------------------------------------


class DomainTests(unittest.TestCase):
    def test_run152_the_game_name_says_the_sport(self):
        from core.run_features import build_features

        features = build_features(
            topic="Ravens are built to win but can they withstand 36 injuries",
            input_topic="Baltimore Ravens at Cleveland Browns",
            channel_id="tapin",
            content_package={"title": "Ravens face injury crisis", "script": "Baltimore is 4-1."},
        )
        self.assertEqual(features["domains"]["topic"], "nfl")

    def test_an_angle_that_names_its_sport_keeps_it(self):
        from core.run_features import build_features

        features = build_features(
            topic="UFC 320 main event preview",
            input_topic="whatever I typed",
            channel_id="tapin",
            content_package={"title": "t", "script": "s"},
        )
        self.assertEqual(features["domains"]["topic"], "ufc")


# ---- #1183: the thumbnail headline is a whole phrase --------------------------------------------------


class HeadlineTests(unittest.TestCase):
    def test_a_title_with_a_colon_keeps_what_is_before_it(self):
        from assets.thumbnail_compose import headline_words

        words = headline_words("Topuria's Outlook: Can He Adapt Before UFC's Next Title Cycle?")
        self.assertEqual(words, ["Topuria's", "Outlook"])

    def test_it_never_ends_on_a_small_word(self):
        from assets.thumbnail_compose import headline_words

        words = headline_words("Ben Affleck Gets Destroyed by 12-Year-Olds in Fortnite")
        self.assertEqual(words, ["Ben", "Affleck", "Gets", "Destroyed"])

    def test_a_short_title_is_whole(self):
        from assets.thumbnail_compose import headline_words

        self.assertEqual(headline_words("UFC 332 Is Stacked"), ["UFC", "332", "Is", "Stacked"])


# ---- #1206: an old description goes out laid out ---------------------------------------------------------


GLUED = "Body.\n\nMade with AI-assisted narration and editing.\nSources:\nhttps://example.com/a"


class LayoutTests(unittest.TestCase):
    def test_a_glued_block_gets_its_blank_line(self):
        from core.description_extras import layout_problem, unglue_blocks

        fixed = unglue_blocks(GLUED)
        self.assertIn("editing.\n\nSources:", fixed)
        self.assertEqual(layout_problem(fixed, "tapin"), "")

    def test_a_laid_out_description_is_left_alone(self):
        from core.description_extras import unglue_blocks

        good = GLUED.replace("\nSources:", "\n\nSources:")
        self.assertEqual(unglue_blocks(good), good)

    def test_the_upload_sends_it_laid_out(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import laid_out_request

        request = PublishRequest(file_path="v.mp4", title="t", description=GLUED)
        self.assertIn("editing.\n\nSources:", laid_out_request(request).description)


if __name__ == "__main__":
    unittest.main()
