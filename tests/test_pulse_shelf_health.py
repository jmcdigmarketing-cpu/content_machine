"""Wave 101 (#1236-#1240): what the operator reads, measured on 2026-10-16 at 9:26 PM.

- TapIn's only tracked competitor was Marques Brownlee. When no competitor title matched the
  topic, the pulse fell back to his 8 newest - "Xiaomi 18 Fold", "iPhone 18 Pro Review" - and an
  NFL angle prompt and research brief read them as "what is working in-niche now".
- `ops status` called run 114 (UFC news, 12 days, never uploaded) "1 recent - requeue_upload".
- `ops health` read engagement RED from run 119: 3 views, 0% engaged.
- 16 of 22 waiting drafts were past their window; the review asked "still current?" 16 times.
- None of TapIn's 11 playlists exist on YouTube; each upload only logged "no playlist yet".
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

# ---- #1236: the pulse only carries titles on the topic ------------------------------------------


SNAP = {
    "synced_at": datetime.now().isoformat(),
    "competitors": [
        {
            "label": "Marques Brownlee (tech/gaming adjacent)",
            "recent_videos": [{"title": "Xiaomi 18 Fold: How Does This Happen?"},
                              {"title": "iPhone 18 Pro Review: All About that Chip"}],
        },
        {
            "label": "Full Mount MMA",
            "recent_videos": [{"title": "Bo Nickal vs Joe Pyfer moves to the main event"}],
        },
    ],
}  # fmt: skip


class PulseTests(unittest.TestCase):
    def _block(self, topic):
        from analytics import competitor_context as cc

        with patch.object(cc, "load_competitor_snapshot", return_value=SNAP):
            return cc.get_competitor_prompt_block("tapin", topic)

    def test_an_nfl_topic_gets_no_tech_titles(self):
        self.assertEqual(self._block("New York Jets at New England Patriots"), "")

    def test_a_topic_a_competitor_covered_keeps_its_line(self):
        block = self._block("Bo Nickal UFC 335 main event")
        self.assertIn("Bo Nickal vs Joe Pyfer", block)
        self.assertNotIn("Xiaomi", block)


# ---- #1237: `ops status` and run 114 ----------------------------------------------------------------


class StatusShelfTests(unittest.TestCase):
    def test_run114_is_past_its_window_not_recent(self):
        from core import stale_renders

        run = SimpleNamespace(id=114, title="Shevchenko demands immediate title shot after "
                              "Silva's UFC 332 win", topic="", mp4_path="r114.mp4")  # fmt: skip
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[run]),
            patch("publishing.go_public.unlisted_holds", return_value=[]),
            patch("publishing.go_public.override_held", return_value=False),
            patch.object(stale_renders, "_queued_runs", return_value={}),
            patch.object(stale_renders, "_signed_out", return_value=False),
            patch.object(stale_renders, "render_age_days", return_value=11.9),
        ):
            counts = stale_renders.shelf("tapin")
            lines = stale_renders.shelf_lines("tapin", counts)
        text = "\n".join(lines)
        self.assertEqual(counts["past_window"], 1)
        self.assertIn("1 past their window", text)
        self.assertNotIn("recent", text)


# ---- #1238: health leaves out a near-empty video -----------------------------------------------------


def _log(run_id, views, rate):
    return SimpleNamespace(
        content_run_id=run_id, metrics_json=json.dumps({"views": views, "engaged_rate": rate})
    )


class HealthTests(unittest.TestCase):
    def test_run119s_three_views_do_not_turn_it_red(self):
        from core import channel_health

        logs = [_log(98, 70, 0.307), _log(99, 80, 0.351), _log(109, 63, 0.272),
                _log(119, 3, 0.0), _log(120, 65, 0.25), _log(92, 60, 0.30)]  # fmt: skip
        repo = SimpleNamespace(list_timed_outcomes=lambda _channel: logs)
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            sub = channel_health._engagement_sub("tapin")
        self.assertNotEqual(sub.status, channel_health.RED, sub.detail)
        self.assertIn("1 video under 20 views left out", sub.detail)

    def test_the_learning_loop_still_sees_every_video(self):
        from core.engagement_predictor import run_engagement_map

        logs = [_log(119, 3, 0.0), _log(120, 65, 0.25)]
        repo = SimpleNamespace(list_timed_outcomes=lambda _channel: logs)
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            self.assertEqual(sorted(run_engagement_map("tapin")), [119, 120])


# ---- #1239: one question sets aside every draft past its window ------------------------------------


class SetAsideTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        old = (datetime.now() - timedelta(days=9)).isoformat(timespec="seconds")
        for run in (115, 116, 122):
            folder = os.path.join(self.root, str(run))
            os.makedirs(folder)
            with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"run_id": run, "topic": f"topic {run}", "title": f"Title {run}",
                           "created_at": old, "channel_id": "tapin"}, f)  # fmt: skip
            with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
                f.write("## Script\n\nA line.\n")

    def _review(self, answers):
        from core.batch_review import review_drafts

        asked: list[str] = []
        replies = iter(answers)

        def ask(prompt):
            asked.append(prompt)
            return next(replies)

        summary = review_drafts("tapin", root=self.root, ask=ask, print_fn=lambda *a, **k: None)
        return summary, asked

    def _decisions(self):
        out = []
        for run in (115, 116, 122):
            with open(os.path.join(self.root, str(run), "meta.json"), encoding="utf-8") as f:
                out.append((json.load(f).get("review") or {}).get("decision"))
        return out

    def test_one_answer_sets_all_three_aside(self):
        summary, asked = self._review([""])
        self.assertEqual(len(asked), 1)
        self.assertIn("Set aside the 3 drafts past their window", asked[0])
        self.assertEqual(sorted(summary.expired), [115, 116, 122])
        self.assertEqual(self._decisions(), ["expired"] * 3)

    def test_no_walks_them_as_before(self):
        summary, asked = self._review(["n", "", "", ""])
        self.assertEqual(len(asked), 4)
        self.assertIn("still current", asked[1])
        self.assertEqual(summary.later, [115, 116, 122])


# ---- #1240: status says the playlists were never made -----------------------------------------------


class PlaylistLineTests(unittest.TestCase):
    def test_none_made_is_said_with_the_command_and_its_cost(self):
        from core import playlists

        rows = [{"name": "UFC / MMA"}, {"name": "NFL"}, {"name": "Gaming"}]
        with (
            patch.object(playlists, "playlist_map", return_value=rows),
            patch.object(playlists, "_load", return_value={"ids": {}}),
        ):
            line = playlists.missing_line("tapin")
        self.assertIn("3 of 3", line)
        self.assertIn("py -m scripts.ops playlists --apply", line)
        self.assertIn("150 quota units", line)

    def test_all_made_says_nothing(self):
        from core import playlists

        rows = [{"name": "NFL"}]
        with (
            patch.object(playlists, "playlist_map", return_value=rows),
            patch.object(playlists, "_load", return_value={"ids": {"NFL": "PL1"}}),
        ):
            self.assertEqual(playlists.missing_line("tapin"), "")


if __name__ == "__main__":
    unittest.main()
