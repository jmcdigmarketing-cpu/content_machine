"""Wave 72: footage comes from the right local folder, and the PC's links are checked.

The operator (2026-10-10): "ensure the system is properly linked to the files on site out of
cloud" and "ensure clips are pulled from the correct folders instead of relying on worse stock
clips". Measured that day against the real library:

- `_keyword_choose_folder` matched any 3+ letter word of a folder name as a substring, and it
  runs first: "Game of the year 2027 predictions" (p-RED-ictions) and run 70's "...redefine..."
  cut Red Dead Redemption 2, "Lakers rivals" cut Marvel Rivals, "steepest" cut Steep,
  "Black Friday" cut Call of Duty Black Ops 3.
- "EA FC 26 career mode" reached no folder, and after #1006 neither did "People working with
  ai to blend video games" - both fell to stock.
- Clip ingest never read `Videos\\Captures`, where the EA FC recording was.
- The Desktop shortcut was written to `%USERPROFILE%\\Desktop` on a PC whose Desktop is
  `OneDrive\\Desktop`.
- `ops doctor`'s workspace row looked at the repo root only.

An unmatched gaming topic getting other games reverses #955's "never another game" for that
one case, on the operator's call: mixed owned gameplay rather than stock. A sport topic with
no footage of that sport still gets none.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

GAMES = [
    "gaming/open world/Red Dead Redemption 2",
    "gaming/open world/GTA V",
    "gaming/multiplayer games/Marvel Rivals",
    "gaming/multiplayer games/Fortnite",
    "gaming/other/Steep",
    "gaming/solo games/Call of Duty Black Ops 3",
    "gaming/sports/Madden 26",
    "gaming/sports/2k26",
    "gaming/sports/UFC 5",
    "gaming/sports/EA Sports FC",
]
FOLDERS = [os.path.join("video", "backgrounds", *g.split("/")) for g in GAMES]


def _name(folder):
    return os.path.basename(folder) if folder else None


class WholeWordFolderTests(unittest.TestCase):
    def _pick(self, topic):
        from assets.local_provider import _keyword_choose_folder

        return _name(_keyword_choose_folder(topic, FOLDERS))

    def test_a_word_inside_another_word_is_not_the_game(self):
        for topic in (
            "Game of the year 2027 predictions",
            "This Golden Axe adaptation could redefine how SEGA handles its classics",
            "The steepest price hike in console history",
        ):
            self.assertIsNone(self._pick(topic), topic)

    def test_one_word_of_a_longer_name_is_not_the_game(self):
        for topic in (
            "Why the Lakers rivals are circling",
            "Marvel movie box office collapse",
            "Call it what it is: Nintendo is winning",
            "Black Friday PS5 deals",
            "Red Bull esports team folds",
        ):
            self.assertIsNone(self._pick(topic), topic)

    def test_the_named_game_is_still_found(self):
        for topic, want in (
            ("GTA 6 trailer 3 breakdown", "GTA V"),
            ("Fortnite reload is back", "Fortnite"),
            ("Madden NFL 27 franchise mode", "Madden 26"),
            ("UFC 5 career mode tips", "UFC 5"),
            ("Marvel Rivals season 3 tier list", "Marvel Rivals"),
            ("Red Dead Redemption 2 still looks better", "Red Dead Redemption 2"),
            ("2K26 badges ranked", "2k26"),
            ("EA FC 26 career mode is broken", "EA Sports FC"),
        ):
            self.assertEqual(self._pick(topic), want, topic)

    def test_the_fuller_name_wins(self):
        folders = [*FOLDERS, os.path.join("video", "backgrounds", "gaming", "Marvel")]
        from assets.local_provider import _keyword_choose_folder

        got = _keyword_choose_folder("Marvel Rivals season 3", folders)
        self.assertEqual(_name(got), "Marvel Rivals")

    def test_a_capture_file_name_still_finds_its_folder(self):
        """The sibling: `ops ingest-clips` matches file names through the same chooser."""
        from assets.clip_ingest import match_folder

        for name, want in (
            ("EA SPORTS FC 26 2026-08-19 12-40-15.mp4", "EA Sports FC"),
            ("EA SPORTS™ Madden NFL 26-2026_06_23-02_31_36.mp4", "Madden 26"),
            ("UFC® 5-2026_06_16-00_17_00.mp4", "UFC 5"),
            ("NBA 2K26 for Xbox Series X_S-2026_05_16-18_55_26.mp4", "2k26"),
        ):
            self.assertEqual(_name(match_folder(name, FOLDERS)), want, name)
        self.assertIsNone(match_folder("EA SPORTS™ College Football 27 7_7_2026.mp4", FOLDERS))


class _LibraryCase(unittest.TestCase):
    def setUp(self):
        from assets import local_provider

        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        for rel in GAMES:
            path = os.path.join(self.root, *rel.split("/"))
            os.makedirs(path, exist_ok=True)
            for i in range(2):
                Path(path, f"clip{i}.mp4").write_bytes(b"x")
        self.folders = sorted(local_provider._get_subfolders(self.root))
        local_provider.reset_footage_choices()
        self.addCleanup(local_provider.reset_footage_choices)

    def _choose(self, topic):
        from assets import local_provider as lp

        with patch.object(lp, "_ai_choose_folder", return_value=None):
            folder, how = lp.choose_footage(topic, self.folders, "tapin")
        return _name(folder), how


class SportGameFootageTests(_LibraryCase):
    def test_the_sport_of_a_sport_video_game(self):
        from apis.topic_scorer import sport_of_game

        self.assertEqual(sport_of_game("FIFA 24 ultimate team prices"), "soccer")
        self.assertEqual(sport_of_game("EA Sports FC career mode is broken"), "soccer")
        self.assertEqual(sport_of_game("NBA 2K25 is shutting down its single-player mode"), "nba")
        self.assertEqual(sport_of_game("Madden franchise mode"), "nfl")
        self.assertEqual(sport_of_game("UFC 5 career mode tips"), "ufc")
        self.assertEqual(sport_of_game("UFC 320 main card"), "")
        self.assertEqual(sport_of_game("GTA 6 career mode rumours"), "")

    def test_a_sport_game_with_no_folder_word_cuts_its_sports_footage(self):
        """ "FC 26" and "2K27" name no folder and no playlist key; the sport's row does."""
        self.assertEqual(
            self._choose("FC 26 Ultimate Team prices are out of control"),
            ("EA Sports FC", "game-sport"),
        )
        self.assertEqual(self._choose("2K27 cover athlete leak"), ("2k26", "game-sport"))

    def test_another_2k_game_is_not_the_basketball_folder(self):
        from apis.topic_scorer import sport_of_game

        self.assertEqual(sport_of_game("WWE 2K27 roster reveal"), "")
        self.assertNotEqual(self._choose("WWE 2K26 roster reveal")[0], "2k26")


class MixedOwnedFootageTests(_LibraryCase):
    SPORT_GAMES = frozenset({"Madden 26", "2k26", "UFC 5", "EA Sports FC"})

    def _clips(self, topic):
        from assets import local_provider as lp

        with (
            patch.object(lp, "BASE_VIDEO_DIR", self.root),
            patch.object(lp, "_ai_choose_folder", return_value=None),
        ):
            provider = lp.LocalAssetProvider()
            clips = provider.candidate_clips(topic, "gaming", "tapin")
            found = provider.find_video(topic, "gaming", "tapin")
            choice = lp.last_footage_choice(topic, "tapin")
        return clips, found, choice

    def test_a_general_gaming_topic_cuts_several_owned_games(self):
        clips, found, choice = self._clips("People working with ai to blend video games")
        games = [os.path.basename(os.path.dirname(c)) for c in clips]
        self.assertGreaterEqual(len(set(games)), 3, games)
        self.assertFalse(set(games) & self.SPORT_GAMES, games)
        self.assertEqual(choice, (None, "mix"))
        self.assertIsNotNone(found)
        self.assertEqual(found.source_id, "footage:mix:")

    def test_the_first_clips_come_from_different_games(self):
        """Fast cut takes the head of the list, so the mix must not be one folder first."""
        clips, _found, _choice = self._clips("best skyrim mods")
        head = [os.path.basename(os.path.dirname(c)) for c in clips[:4]]
        self.assertEqual(len(set(head)), 4, head)

    def test_a_sport_topic_never_gets_the_mix(self):
        """No hockey footage: another sport or a shooter behind it is the #955 defect."""
        from assets import local_provider as lp

        clips, found, choice = self._clips("Stanley Cup final goes to game seven")
        with patch("apis.topic_scorer.infer_topic_domain", return_value="nhl"):
            lp.reset_footage_choices()
            clips, found, choice = self._clips("Stanley Cup final goes to game seven")
        self.assertEqual(clips, [])
        self.assertIsNone(found)
        self.assertEqual(choice, (None, "none"))

    def test_a_film_topic_never_gets_the_mix(self):
        clips, _found, choice = self._clips("Marvel movie box office collapse")
        self.assertEqual(clips, [])
        self.assertEqual(choice, (None, "none"))

    def test_the_gaps_report_keeps_asking_for_the_game(self):
        from assets.footage_gaps import recorded_choice, wants_footage

        self.assertTrue(wants_footage(recorded_choice("footage:mix:"), "fast_cut"))
        self.assertFalse(wants_footage(recorded_choice("footage:keyword:UFC 5"), "fast_cut"))
        self.assertTrue(wants_footage(recorded_choice("footage:none:"), "pexels"))


class CaptureFolderTests(unittest.TestCase):
    def test_the_game_bar_folder_is_a_source(self):
        from assets import clip_ingest

        with tempfile.TemporaryDirectory() as tmp:
            videos = Path(tmp) / "Videos"
            (videos / "Captures").mkdir(parents=True)
            with (
                patch.dict(os.environ, {"CLIP_INGEST_DIRS": ""}),
                patch("core.win_shell.known_folder", return_value=str(videos)),
            ):
                dirs = clip_ingest.default_source_dirs()
        self.assertIn(str(videos / "Captures"), dirs)

    def test_a_cloud_only_file_is_not_opened(self):
        from assets import clip_ingest

        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "library" / "gaming" / "GTA V"
            library.mkdir(parents=True)
            (library / "existing.mp4").write_bytes(b"clip")
            source = Path(tmp) / "captures"
            source.mkdir()
            capture = source / "Grand Theft Auto V 2026.08.28 - 16.37.42.01.mp4"
            capture.write_bytes(b"src")
            with (
                patch.object(clip_ingest, "CLIP_INDEX_FILE", str(Path(tmp) / "index.json")),
                patch.object(clip_ingest, "_file_attributes", return_value=0x400000),
            ):
                rows = clip_ingest.plan_ingest(
                    source_dirs=[str(source)], library_root=str(Path(tmp) / "library")
                )
        self.assertEqual([r.status for r in rows], ["cloud-only"], rows)
        self.assertIn("not downloaded", rows[0].reason)

    def test_a_local_file_is_still_matched(self):
        from assets import clip_ingest

        self.assertFalse(clip_ingest.cloud_only_attributes(0x20))
        self.assertTrue(clip_ingest.cloud_only_attributes(0x1000))
        self.assertTrue(clip_ingest.cloud_only_attributes(0x40000))


class DesktopFolderTests(unittest.TestCase):
    def test_the_desktop_is_where_windows_says_it_is(self):
        from core import win_shell

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(win_shell, "known_folder", return_value=tmp, create=True):
                self.assertEqual(win_shell.desktop_dir(), tmp)
                self.assertEqual(os.path.dirname(win_shell.desktop_app_shortcut_path()), tmp)

    def test_no_answer_falls_back_to_the_profile_desktop(self):
        from core import win_shell

        with (
            patch.object(win_shell, "known_folder", return_value="", create=True),
            patch.dict(os.environ, {"USERPROFILE": os.path.join("C:", os.sep, "Users", "x")}),
        ):
            self.assertEqual(
                win_shell.desktop_dir(), os.path.join("C:", os.sep, "Users", "x", "Desktop")
            )

    def test_known_folder_is_empty_off_windows_or_for_a_missing_name(self):
        from core import win_shell

        self.assertEqual(win_shell.known_folder("No Such Folder Name"), "")


class WorkspaceLinkTests(unittest.TestCase):
    def _gather(self, tmp, **kw):
        from core.workspace_hazards import gather

        base = {"vault": "", "host": "DESKTOP-TEST", "empty_footage": []}
        base.update(kw)
        return gather(tmp, **base)

    def test_a_missing_vault_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = self._gather(tmp, vault=os.path.join(tmp, "gone"))
        self.assertTrue(any("vault" in h and "missing" in h for h in data["hazards"]), data)

    def test_a_vault_under_onedrive_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = os.path.join(tmp, "OneDrive", "Documents", "vault")
            os.makedirs(vault)
            data = self._gather(tmp, vault=vault)
        self.assertTrue(any("vault" in h and "OneDrive" in h for h in data["hazards"]), data)

    def test_a_sync_conflict_copy_in_data_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "data"))
            Path(tmp, "data", "signal_cache.json").write_text("{}")
            Path(tmp, "data", "signal_cache-DESKTOP-TEST.json").write_text("{}")
            data = self._gather(tmp)
        self.assertTrue(
            any("signal_cache-DESKTOP-TEST.json" in h for h in data["hazards"]), data["hazards"]
        )

    def test_an_empty_footage_folder_is_a_note_not_a_failure(self):
        from core.workspace_hazards import render

        with tempfile.TemporaryDirectory() as tmp:
            data = self._gather(tmp, empty_footage=["EA Sports FC"])
        self.assertEqual(data["hazards"], [])
        self.assertIn("EA Sports FC", render(data))

    def test_a_clean_workspace_still_reads_ok(self):
        from core.workspace_hazards import render

        with tempfile.TemporaryDirectory() as tmp:
            vault = os.path.join(tmp, "vault")
            os.makedirs(vault)
            data = self._gather(tmp, vault=vault)
        self.assertEqual(data["hazards"], [])
        self.assertIn("ok", render(data))

    def test_playlist_folders_without_clips_are_found(self):
        from core.workspace_hazards import empty_footage_folders

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "gaming", "sports", "EA Sports FC"))
            full = os.path.join(tmp, "gaming", "sports", "UFC 5")
            os.makedirs(full)
            Path(full, "a.mp4").write_bytes(b"x")
            rows = [{"footage": ["EA Sports FC"]}, {"footage": ["UFC 5"]}, {"footage": []}]
            self.assertEqual(empty_footage_folders(tmp, rows), ["EA Sports FC"])


class OwnedBeatClipTests(unittest.TestCase):
    """The sibling: `core.owned_beats.topic_clips` runs when fast cut makes nothing.

    It looked for a topic word anywhere in the clip's path or source: "World Cup" matched the
    "open world" directory (27 GTA V clips) and "box office" matched "Xbox" in a capture name.
    """

    INDEX: ClassVar[dict] = {
        "clips": {
            os.path.join("video", "backgrounds", "gaming", "open world", "GTA V", "a.mp4"): {
                "source": "library",
                "duration_s": 30.0,
            },
            os.path.join("video", "backgrounds", "gaming", "sports", "2k26", "b.mp4"): {
                "source": "C:/Videos/NBA 2K26 for Xbox Series X_S-2026_05_16.mp4",
                "duration_s": 40.0,
            },
            os.path.join("video", "backgrounds", "gaming", "sports", "UFC 5", "c.mp4"): {
                "source": "library",
                "duration_s": 20.0,
            },
        }
    }

    def _games(self, topic):
        from core.owned_beats import topic_clips

        return [os.path.basename(os.path.dirname(p)) for p in topic_clips(self.INDEX, topic=topic)]

    def test_a_directory_word_is_not_the_topic(self):
        self.assertEqual(self._games("World Cup semi finals preview"), [])
        self.assertEqual(self._games("People working with ai to blend video games"), [])

    def test_a_word_inside_a_capture_name_is_not_the_topic(self):
        self.assertEqual(self._games("Marvel movie box office collapse"), [])

    def test_the_named_game_and_the_sport_still_find_their_clips(self):
        self.assertEqual(self._games("GTA 6 trailer 3 breakdown"), ["GTA V"])
        self.assertEqual(self._games("UFC 320 main card"), ["UFC 5"])
        self.assertEqual(self._games("Wemby's 40-point night"), ["2k26"])


if __name__ == "__main__":
    unittest.main()
