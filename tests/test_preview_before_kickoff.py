"""A game preview goes to TikTok and Instagram before its game (the operator, 2026-10-17).

Run 155, "Tennessee Titans' offensive line faces test vs Colts' revamped pass rush", went public
on Saturday afternoon. Run 126 already held Saturday 10 PM on both platforms, and the one-a-day
spacing (decision 54) put the preview on Sunday 10 PM - nine hours after the 1:00 PM kickoff.
The draft's `meta.json` knows the game's start (`event_at`, #1151).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.test_buffer_crosspost import CrosspostCase


def _draft(root, run_id, event_at):
    folder = os.path.join(root, f"draft-{run_id}")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"run_id": run_id, "topic": "Tennessee Titans at Indianapolis Colts",
                   "event_at": event_at}, fh)  # fmt: skip


class DraftMetaTests(CrosspostCase):
    def test_a_runs_draft_is_found_by_its_id(self):
        from core.batch_review import draft_meta_for_run

        _draft(self.tmp.name, 155, "2026-10-18T17:00Z")
        meta = draft_meta_for_run("tapin", 155, root=self.tmp.name)
        self.assertEqual(meta.get("event_at"), "2026-10-18T17:00Z")
        self.assertEqual(draft_meta_for_run("tapin", 999, root=self.tmp.name), {})


class BeforeKickoffTests(CrosspostCase):
    def _send_with_kickoff(self, kickoff):
        from publishing.crosspost import send_due

        send_due("tapin")  # records what was already public
        self.public.extend([(113, "yt113"), (114, "yt114")])
        starts = {114: kickoff}
        with patch(
            "publishing.crosspost._kickoff_for", side_effect=lambda _c, rid: starts.get(rid)
        ):
            return send_due("tapin")

    def _due(self, service, run_id):
        state = self._store()["posts"][str(run_id)][service]
        return state

    def test_the_preview_goes_before_its_game_even_on_a_taken_day(self):
        kickoff = datetime.now(timezone.utc) + timedelta(hours=6)
        self._send_with_kickoff(kickoff)
        for service in ("tiktok", "instagram"):
            state = self._due(service, 114)
            self.assertEqual(state["state"], "scheduled")
            due = datetime.fromisoformat(state["due_at"])
            self.assertLess(due, kickoff)

    def test_a_game_that_has_started_is_not_posted(self):
        kickoff = datetime.now(timezone.utc) - timedelta(hours=1)
        lines = self._send_with_kickoff(kickoff)
        self.assertEqual(self._due("tiktok", 114)["state"], "skipped")
        self.assertIn("game has started", "\n".join(lines))
        self.assertEqual(self._due("tiktok", 113)["state"], "scheduled")  # the rest still go

    def test_a_video_with_no_game_goes_at_its_slot(self):
        # Decision 63: no spacing - both go at the channel's suggested slot.
        self._send_with_kickoff(None)
        first = datetime.fromisoformat(self._due("tiktok", 113)["due_at"])
        second = datetime.fromisoformat(self._due("tiktok", 114)["due_at"])
        self.assertEqual(first, second)


if __name__ == "__main__":
    import unittest

    unittest.main()
