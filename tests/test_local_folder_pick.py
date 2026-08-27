"""Local background folder pick must use the original topic, not the stock rewrite.

Measured: resolve_background_query turns a Fortnite topic into
"video game gameplay esports" when the LLM rewrite is off. The folder picker
then asked the cheap LLM (or random.choice) with that generic string, so a
library that has both `gaming/fortnite/` and `gaming/gta/` could put GTA
footage under a Fortnite script.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from assets.local_provider import LocalAssetProvider


def _touch_clip(folder: str, name: str) -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "wb") as fh:
        fh.write(b"clip")
    return path


class TestKeywordFolderPick(unittest.TestCase):
    def test_fortnite_topic_selects_fortnite_folder_over_gta(self):
        with tempfile.TemporaryDirectory() as tmp:
            fortnite = os.path.join(tmp, "gaming", "fortnite")
            gta = os.path.join(tmp, "gaming", "gta")
            fn_clip = _touch_clip(fortnite, "fn.mp4")
            _touch_clip(gta, "gta.mp4")

            with (
                patch("assets.local_provider.BASE_VIDEO_DIR", tmp),
                patch.dict(os.environ, {"BACKGROUND_QUERY_LLM": "false"}, clear=False),
                patch(
                    "assets.local_provider._ai_choose_folder",
                    return_value=gta,
                ),
            ):
                result = LocalAssetProvider().find_video(
                    "Fortnite Chapter 6 reload",
                    "gaming",
                )

        self.assertIsNotNone(result)
        self.assertEqual(result.path, fn_clip)

    def test_keyword_match_uses_original_topic_not_stock_rewrite(self):
        folders = [
            os.path.join("video", "backgrounds", "gaming", "fortnite"),
            os.path.join("video", "backgrounds", "gaming", "gta"),
        ]
        from assets.local_provider import _keyword_choose_folder

        chosen = _keyword_choose_folder("Fortnite reload", folders)
        self.assertEqual(os.path.basename(chosen or ""), "fortnite")
        # The stock rewrite for a gaming topic does not mention Fortnite.
        self.assertIsNone(_keyword_choose_folder("video game gameplay esports", folders))

    def test_known_gap_gta_topic_still_falls_through_when_only_fortnite_exists(self):
        """Until a gta/ folder exists, a GTA topic can still draw Fortnite clips.

        Keyword matching cannot invent a missing franchise library. Closing this
        means adding `video/backgrounds/gaming/gta/` clips, or refusing local
        footage when no folder token matches.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fortnite = os.path.join(tmp, "gaming", "fortnite")
            fn_clip = _touch_clip(fortnite, "fn.mp4")

            with (
                patch("assets.local_provider.BASE_VIDEO_DIR", tmp),
                patch.dict(os.environ, {"BACKGROUND_QUERY_LLM": "false"}, clear=False),
                patch("assets.local_provider._ai_choose_folder", return_value=None),
            ):
                result = LocalAssetProvider().find_video("GTA 6 trailer", "gaming")

        self.assertIsNotNone(result)
        self.assertEqual(result.path, fn_clip)


if __name__ == "__main__":
    unittest.main()
