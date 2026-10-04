"""#955: footage must match the topic, and how it was chosen is recorded.

The operator's screenshots (2026-10-04): the Wemby Short cut UFC 5 fighters and the Clair Obscur
Short cut Madden. `LocalAssetProvider.candidate_clips` tried the folder name in the topic, then
the playlist alias, then asked the cheap model with the trademark-stripped stock rewrite (which
never said "Wemby"), then took `random.choice` over every game folder. Fast cut is on by
default, so the whole background was that one wrong game.

Now: keyword, alias, the topic's own domain (#946 names included), then the model shown the
operator's topic and allowed to answer NONE - and nothing else. An unmatched topic gets stock
B-roll or a plain branded background, never another game. `core/owned_beats` had the same shape
(clips that matched no topic token were used anyway).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


def _library(root, folders):
    for rel, count in folders.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(path, exist_ok=True)
        for i in range(count):
            with open(os.path.join(path, f"clip{i}.mp4"), "wb") as f:
                f.write(b"x")


LIBRARY = {
    "gaming/sports/Madden 26": 3,
    "gaming/sports/2k26": 3,
    "gaming/sports/UFC 5": 3,
    "gaming/open world/GTA V": 3,
}


class _LibraryCase(unittest.TestCase):
    def setUp(self):
        from assets import local_provider

        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _library(self.root, LIBRARY)
        self.folders = sorted(local_provider._get_subfolders(self.root))
        local_provider.reset_footage_choices()
        self.addCleanup(local_provider.reset_footage_choices)


class ChooseFootageTests(_LibraryCase):
    def _choose(self, topic, llm=None):
        from assets import local_provider as lp

        with patch.object(lp, "_ai_choose_folder", return_value=llm) as ai:
            folder, how = lp.choose_footage(topic, self.folders, "tapin")
        return (os.path.basename(folder) if folder else None), how, ai

    def test_a_nickname_finds_its_sports_footage(self):
        """The Wemby Short: nba by name (#946) -> the Basketball row -> 2k26."""
        self.assertEqual(self._choose("Wemby's 40-point night")[:2], ("2k26", "domain"))

    def test_a_fighter_led_title_finds_ufc_footage(self):
        self.assertEqual(self._choose("Holloway vs Gaethje")[:2], ("UFC 5", "domain"))

    def test_an_unmatched_topic_gets_no_folder(self):
        """The Clair Obscur Short: no folder is its game, so none is taken."""
        name, how, _ai = self._choose("Clair Obscur sweeps the nominations")
        self.assertEqual((name, how), (None, "none"))

    def test_the_model_is_shown_the_operator_topic(self):
        _name, _how, ai = self._choose("Clair Obscur sweeps the nominations")
        ai.assert_called_once()
        self.assertEqual(ai.call_args.args[0], "Clair Obscur sweeps the nominations")

    def test_a_model_pick_is_recorded_as_one(self):
        from assets import local_provider as lp

        gta = next(f for f in self.folders if f.endswith("GTA V"))
        with patch.object(lp, "_ai_choose_folder", return_value=gta):
            folder, how = lp.choose_footage("Leonida map leak", self.folders, "tapin")
        self.assertEqual((folder, how), (gta, "llm"))

    def test_keyword_and_alias_still_win(self):
        self.assertEqual(self._choose("UFC 5 patch notes")[:2], ("UFC 5", "keyword"))
        self.assertEqual(self._choose("NFL draft night shock trade")[:2], ("Madden 26", "alias"))

    def test_the_model_can_be_left_out(self):
        from assets import local_provider as lp

        with patch.object(lp, "_ai_choose_folder", side_effect=AssertionError("model called")):
            choice = lp.choose_footage(
                "Clair Obscur sweeps the nominations", self.folders, "tapin", use_llm=False
            )
        self.assertEqual(choice, (None, "none"))


class CandidateClipsTests(_LibraryCase):
    def _patches(self, llm=None):
        from assets import local_provider as lp

        return (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch.object(lp, "_ai_choose_folder", return_value=llm),
            patch.object(lp.random, "choice", side_effect=AssertionError("random folder")),
        )

    def test_no_random_folder_for_an_unmatched_topic(self):
        from assets import local_provider as lp

        a, b, c = self._patches()
        with a, b, c:
            clips = lp.LocalAssetProvider().candidate_clips(
                "Clair Obscur sweeps the nominations", "gaming", "tapin"
            )
            found = lp.LocalAssetProvider().find_video(
                "Clair Obscur sweeps the nominations", "gaming", "tapin"
            )
        self.assertEqual(clips, [])
        self.assertIsNone(found)

    def test_the_background_records_how_its_folder_was_chosen(self):
        from assets import local_provider as lp

        a, b, _c = self._patches()
        with a, b:
            found = lp.LocalAssetProvider().find_video("Wemby's 40-point night", "gaming", "tapin")
        self.assertIsNotNone(found)
        self.assertEqual(found.source_id, "footage:domain:2k26")

    def test_one_render_asks_the_model_once(self):
        """Fast cut, then the hybrid fallback, both read the folder: one decision."""
        from assets import local_provider as lp

        with (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch.object(lp, "_ai_choose_folder", return_value=None) as ai,
        ):
            lp.LocalAssetProvider().candidate_clips("Leonida map leak", "gaming", "tapin")
            lp.LocalAssetProvider().find_video("Leonida map leak", "gaming", "tapin")
            self.assertEqual(lp.last_footage_choice("Leonida map leak", "tapin"), (None, "none"))
        self.assertEqual(ai.call_count, 1)


class ModelPromptTests(_LibraryCase):
    def test_none_means_no_folder(self):
        from assets import local_provider as lp

        with (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch("core.llm_router.complete", return_value="NONE") as complete,
        ):
            self.assertIsNone(lp._ai_choose_folder("Clair Obscur nominations", self.folders))
        prompt = complete.call_args.args[0]
        self.assertIn("Clair Obscur nominations", prompt)
        self.assertIn("NONE", prompt)

    def test_an_exact_folder_answer_is_taken(self):
        from assets import local_provider as lp

        two_k = next(f for f in self.folders if f.endswith("2k26"))
        with (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch("core.llm_router.complete", return_value=os.path.relpath(two_k, self.root)),
        ):
            self.assertEqual(lp._ai_choose_folder("Spurs highlights", self.folders), two_k)


OWNED_INDEX = {
    "clips": {
        "/lib/ufc5_knockout_a.mp4": {"source": "UFC 5", "duration_s": 10, "hud": False},
        "/lib/ufc5_knockout_b.mp4": {"source": "UFC 5", "duration_s": 9, "hud": False},
        "/lib/madden_touchdown.mp4": {"source": "Madden 26", "duration_s": 12, "hud": False},
    }
}


class OwnedBeatsTests(unittest.TestCase):
    """The sibling: `assign_owned_clips` ranked by topic-token hits and used 0-hit clips too."""

    def _scenes(self, n=2):
        from video.scene_plan import Scene

        return [Scene(query="q", start=i * 5.0, end=(i + 1) * 5.0, text="t") for i in range(n)]

    def test_clips_that_match_nothing_in_the_topic_are_not_used(self):
        from core.owned_beats import assign_owned_clips

        self.assertEqual(
            assign_owned_clips(self._scenes(), OWNED_INDEX, topic="Wemby's 40-point night"), []
        )

    def test_matching_clips_only(self):
        from core.owned_beats import assign_owned_clips

        paths = assign_owned_clips(self._scenes(), OWNED_INDEX, topic="UFC 5 knockout reel")
        self.assertEqual(len(paths), 2)
        self.assertTrue(all("ufc5" in p for p in paths), paths)


class PlainBackgroundTests(unittest.TestCase):
    def test_a_plain_background_is_drawn_in_the_channel_colour(self):
        from assets import plain_background

        seen = {}

        def runner(cmd):
            seen["cmd"] = cmd
            with open(cmd[-1], "wb") as f:
                f.write(b"x")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(plain_background, "_out_dir", return_value=tmp),
                patch.object(plain_background, "_colour", return_value="#101820"),
            ):
                result = plain_background.plain_background("tapin", 42.5, runner=runner)
            self.assertIsNotNone(result)
            self.assertTrue(os.path.isfile(result.path))
        self.assertEqual(result.provider, "plain")
        self.assertEqual(result.source_id, "footage:plain:")
        graph = " ".join(seen["cmd"])
        self.assertIn("color=c=#101820:s=1080x1920", graph)
        self.assertIn("d=42.500", graph)

    def test_no_footage_and_no_stock_renders_plain_instead_of_failing(self):
        from assets import manager
        from assets.types import AssetResult

        plain = AssetResult(path="/tmp/plain.mp4", provider="plain", source_id="footage:plain:")
        with (
            patch.object(manager, "resolve_background_mode", return_value="hybrid"),
            patch.object(manager, "get_local_background_asset", return_value=None),
            patch.object(manager, "get_stock_background_asset", return_value=None),
            patch("assets.plain_background.plain_background", return_value=plain),
        ):
            result = manager.get_background_asset("Clair Obscur nominations", "tapin", duration=40)
        self.assertEqual(result.provider, "plain")

    def test_local_mode_with_no_matching_footage_renders_plain(self):
        from assets import manager
        from assets.types import AssetResult

        plain = AssetResult(path="/tmp/plain.mp4", provider="plain", source_id="footage:plain:")
        with (
            patch.object(manager, "resolve_background_mode", return_value="local"),
            patch.object(manager, "get_local_background_asset", return_value=None),
            patch("assets.plain_background.plain_background", return_value=plain),
        ):
            result = manager.get_background_asset("Clair Obscur nominations", "tapin", duration=40)
        self.assertEqual(result.provider, "plain")


class FastCutRecordsTests(unittest.TestCase):
    def test_the_fast_cut_background_carries_the_choice(self):
        from assets import fast_cut, local_provider
        from assets.types import AssetResult

        local_provider.reset_footage_choices()
        self.addCleanup(local_provider.reset_footage_choices)
        local_provider._remember("Wemby's 40-point night", "tapin", (), ("/lib/2k26", "domain"))
        composed = AssetResult(path="/tmp/fc.mp4", provider="fast_cut")
        with (
            patch.object(fast_cut, "fast_cut_enabled", return_value=True),
            patch.object(fast_cut, "_clip_pool", return_value=["a.mp4", "b.mp4", "c.mp4"]),
            patch.object(fast_cut, "_probe", return_value=30.0),
            patch.object(fast_cut, "_compose", return_value=composed),
        ):
            result = fast_cut.try_fast_cut_background(
                "Wemby's 40-point night", "tapin", duration=40.0
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.source_id, "footage:domain:2k26")


def _runs():
    def run(rid, topic):
        return SimpleNamespace(
            id=rid, selected_topic=topic, input_topic=topic, features_json=json.dumps({})
        )

    return [
        run(101, "Wemby's 40-point night"),
        run(102, "Clair Obscur sweeps the nominations"),
        run(103, "UFC 5 patch notes"),
        run(104, "Minecraft mob vote"),
        run(105, "Minecraft movie sequel"),
    ]


ASSETS = {
    101: [
        SimpleNamespace(
            asset_type="background", provider="fast_cut", path="/t/fc1.mp4", source_id=""
        )
    ],
    102: [
        SimpleNamespace(
            asset_type="background", provider="fast_cut", path="/t/fc2.mp4", source_id=""
        )
    ],
    103: [
        SimpleNamespace(
            asset_type="background",
            provider="fast_cut",
            path="/t/fc3.mp4",
            source_id="footage:keyword:UFC 5",
        )
    ],
    104: [
        SimpleNamespace(
            asset_type="background", provider="plain", path="/t/p.mp4", source_id="footage:plain:"
        )
    ],
    105: [
        SimpleNamespace(
            asset_type="background", provider="pexels", path="/t/s.mp4", source_id="123"
        )
    ],
}


class FootageGapsTests(_LibraryCase):
    def _report(self):
        from assets import footage_gaps, local_provider

        runs = SimpleNamespace(list_for_channel=lambda cid, status=None: _runs())
        assets = SimpleNamespace(list_for_run=lambda rid: ASSETS.get(rid, []))
        with (
            patch.object(local_provider, "BASE_VIDEO_DIR", self.root),
            patch.object(local_provider, "_ai_choose_folder", side_effect=AssertionError("model")),
            patch.object(footage_gaps, "_run_repo", return_value=runs),
            patch.object(footage_gaps, "_asset_repo", return_value=assets),
        ):
            return footage_gaps.footage_gaps("tapin"), footage_gaps.footage_gap_lines("tapin")

    def test_the_shopping_list_names_what_fell_through(self):
        report, _lines = self._report()
        wanted = {row["playlist"]: row["runs"] for row in report["wanted"]}
        self.assertEqual(wanted.get("Minecraft"), [104, 105])
        self.assertIn(102, [r for row in report["wanted"] for r in row["runs"]])

    def test_past_videos_that_may_show_another_game(self):
        report, _lines = self._report()
        risky = {row["run_id"]: row for row in report["at_risk"]}
        self.assertEqual(sorted(risky), [101, 102])
        self.assertEqual(risky[101]["now"], "2k26")
        self.assertIsNone(risky[102]["now"])

    def test_the_lines_read_as_a_list(self):
        _report, lines = self._report()
        text = "\n".join(lines)
        self.assertIn("Minecraft", text)
        self.assertIn("run 101", text)
        self.assertIn("2k26", text)

    def test_the_command_prints_the_report(self):
        from assets import footage_gaps
        from scripts.ops import COMMANDS

        self.assertIn("footage-gaps", COMMANDS)
        with patch.object(footage_gaps, "footage_gap_lines", return_value=["Footage gaps - x"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = COMMANDS["footage-gaps"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("Footage gaps", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
