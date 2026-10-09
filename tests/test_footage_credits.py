"""#1019: a Creative Commons Attribution clip is credited in the YouTube description.

The Minecraft folder's `license.yaml` says "Creative Commons Attribution license (reuse
allowed); YouTube download" with its source URL, and CC BY requires the credit. The render
only logged `asset.attribution` (`video/render_video.py`), and the fast cut replaced it with
"Gameplay (local), N shots" - so no credit ever reached a description.

- `assets.local_provider.clip_credit` reads the clip's nearest licence and returns a credit
  line only when the licence asks for attribution (owned footage needs none).
- `AssetResult.credits` carries them: the fast cut (every clip it cut from), the single local
  clip, and the hybrid compose (its gameplay half).
- `core.description_extras.add_footage_credits` appends a "Footage:" block once, and
  `persist_footage_credits` writes it to the run row after the render - the row is what
  `main.py` queues (`core.chapters.current_description`).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

CC = {"license": "Creative Commons Attribution license (reuse allowed); YouTube download",
      "owner": "third party (see sources)", "commercial_use": True,
      "sources": ["https://www.youtube.com/watch?v=NX-i0IWl3yg"]}  # fmt: skip
OWNED = {"owner": "TapIn Media", "license": "owned", "commercial_use": True}


class CreditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = tmp.name
        for folder, lic in (("Minecraft", CC), ("GTA V", OWNED)):
            os.makedirs(os.path.join(self.base, folder))
            with open(os.path.join(self.base, folder, "license.yaml"), "w", encoding="utf-8") as f:
                json.dump(lic, f)
            for name in ("a.mp4", "b.mp4"):
                open(os.path.join(self.base, folder, name), "w").close()
        patcher = patch("assets.local_provider.BASE_VIDEO_DIR", self.base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _clip(self, folder, name="a.mp4"):
        return os.path.join(self.base, folder, name)

    def test_cc_by_is_credited_with_its_source(self):
        from assets.local_provider import clip_credit

        line = clip_credit(self._clip("Minecraft"))
        self.assertIn("Minecraft", line)
        self.assertIn("https://www.youtube.com/watch?v=NX-i0IWl3yg", line)
        self.assertIn("Creative Commons Attribution", line)

    def test_owned_footage_needs_no_credit(self):
        from assets.local_provider import clip_credit

        self.assertIsNone(clip_credit(self._clip("GTA V")))

    def test_one_line_per_folder(self):
        from assets.local_provider import clip_credits

        got = clip_credits([self._clip("Minecraft"), self._clip("Minecraft", "b.mp4"),
                            self._clip("GTA V")])  # fmt: skip
        self.assertEqual(len(got), 1)

    def test_the_fast_cut_result_carries_them(self):
        from assets.fast_cut import fast_cut_result

        shots = [(self._clip("Minecraft"), 0.0, 2.0), (self._clip("GTA V"), 1.0, 2.5)]
        asset = fast_cut_result("out.mp4", "minecraft", shots)
        self.assertEqual(asset.provider, "fast_cut")
        self.assertEqual(len(asset.credits), 1)
        self.assertIn("Minecraft", asset.credits[0])


class DescriptionTests(unittest.TestCase):
    def test_the_block_is_added_once(self):
        from core.description_extras import add_footage_credits

        once = add_footage_credits("Body.\n\nSources:\nhttps://x", ["Minecraft: CC BY - u"])
        self.assertIn("Footage:\nMinecraft: CC BY - u", once)
        self.assertEqual(add_footage_credits(once, ["Minecraft: CC BY - u"]), once)
        self.assertEqual(add_footage_credits("Body.", []), "Body.")

    def test_the_run_row_gets_it(self):
        from core.description_extras import persist_footage_credits

        record = SimpleNamespace(description="Body.")
        repo = SimpleNamespace(
            get=lambda rid: record, update=lambda rid, data: updates.append(data)
        )
        updates: list[dict] = []
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            got = persist_footage_credits(124, ["Minecraft: CC BY - u"])
        self.assertIn("Footage:", got)
        self.assertEqual(updates, [{"description": got}])

    def test_the_render_step_persists_them(self):
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "core" / "pipeline.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("persist_footage_credits(content_run_id, background.credits)", src)


if __name__ == "__main__":
    unittest.main()
