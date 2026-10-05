"""#968: `ops crosspost` - the pack for Buffer (operator, 2026-10-05: "i got buffer").

TikTok and Instagram go through Buffer, which schedules both and posts with the PC off, so
Content OS needs no app on either platform: it hands over a folder per rendered video -
the mp4, a TikTok caption, an Instagram caption and the slot - and remembers what the
operator marked posted. A Reel over 90 seconds is named rather than packed for Instagram.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

SLOT = datetime(2026, 10, 9, 22, tzinfo=timezone.utc)


def _read(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8") as f:
        return f.read()


def _run(tmp, run_id=113, *, mp4=True, title="Heat's preseason chemistry is a trap"):
    path = os.path.join(tmp, f"v{run_id}.mp4")
    if mp4:
        with open(path, "wb") as f:
            f.write(b"mp4")
    return SimpleNamespace(
        id=run_id,
        channel_id="tapin",
        input_topic="NBA preseason hot takes",
        selected_topic="Which team's preseason chemistry suggests they're peaking too early",
        status="rendered",
        title=title,
        description=(
            "We debate whether preseason chemistry is a contender signal or a trap. "
            "Drop your take below.\n\nMade with AI-assisted narration and editing."
        ),
        tags_json=json.dumps(["NBA preseason", "Miami Heat", "NBA hot takes", "Heat vs Raptors",
                              "NBA debate", "NBA 2026-27", "Miami Heat"]),
        mp4_path=path if mp4 else "",
    )  # fmt: skip


class PackCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "out")
        self.store = os.path.join(self.tmp.name, "crosspost_{channel}.json")
        self.runs = [_run(self.tmp.name), _run(self.tmp.name, 114, mp4=False)]
        for p in (
            patch("publishing.crosspost._pack_root", return_value=self.root),
            patch("publishing.crosspost.CROSSPOST_TEMPLATE", self.store),
            patch("publishing.crosspost._rendered_runs", side_effect=lambda c: list(self.runs)),
            patch("publishing.crosspost._duration", return_value=81.7),
            patch("publishing.crosspost._suggested_slot", return_value=SLOT),
        ):
            p.start()
            self.addCleanup(p.stop)


class PackTests(PackCase):
    def test_a_rendered_video_gets_a_folder_buffer_can_take(self):
        from publishing.crosspost import pack_new

        packed = pack_new("tapin")
        self.assertEqual([p.run_id for p in packed], [113])
        folder = packed[0].folder
        self.assertEqual(sorted(os.listdir(folder)),
                         ["instagram.txt", "slot.txt", "tiktok.txt", "video.mp4"])  # fmt: skip
        tiktok = _read(folder, "tiktok.txt")
        self.assertIn("Heat's preseason chemistry is a trap", tiktok)
        self.assertIn("Made with AI-assisted narration", tiktok)
        tags = [w for w in tiktok.split() if w.startswith("#")]
        self.assertTrue(3 <= len(tags) <= 5, tags)
        self.assertIn("#NBApreseason", tags)
        self.assertEqual(len(tags), len(set(tags)))
        slot = _read(folder, "slot.txt")
        self.assertIn("AI-generated", slot)

    def test_packing_twice_packs_nothing_new(self):
        from publishing.crosspost import pack_new

        pack_new("tapin")
        self.assertEqual(pack_new("tapin"), [])

    def test_a_long_video_is_not_offered_as_a_reel(self):
        from publishing.crosspost import pack_new

        with patch("publishing.crosspost._duration", return_value=95.0):
            folder = pack_new("tapin")[0].folder
        insta = _read(folder, "instagram.txt")
        self.assertIn("95", insta)
        self.assertIn("90", insta)

    def test_marking_posted_takes_it_off_the_list(self):
        from publishing.crosspost import mark_posted, pack_new, waiting_lines

        pack_new("tapin")
        self.assertIn("113", "\n".join(waiting_lines("tapin")))
        self.assertTrue(mark_posted("tapin", 113))
        self.assertNotIn("run 113", "\n".join(waiting_lines("tapin")))


class CommandTests(PackCase):
    def _ops(self, target="", run_id=0):
        from scripts.ops import cmd_crosspost

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_crosspost(Namespace(channel="tapin", target=target, run_id=run_id))
        return code, buf.getvalue()

    def test_the_verb_packs_lists_and_marks(self):
        code, out = self._ops()
        self.assertEqual(code, 0)
        self.assertIn(self.root, out)
        _code, listed = self._ops("list")
        self.assertIn("113", listed)
        code, out = self._ops("done", run_id=113)
        self.assertEqual(code, 0)
        _code, listed = self._ops("list")
        self.assertNotIn("run 113", listed)

    def test_done_without_a_run_says_how(self):
        code, out = self._ops("done")
        self.assertNotEqual(code, 0)
        self.assertIn("--run-id", out)


if __name__ == "__main__":
    unittest.main()
