"""#970: Enter at the channel menu picked "Default", which is not a channel (run 113).

The operator pressed Enter at "Select 1-3 [Enter = 1]" and run 113 - an NBA Short meant for
TapIn - was made on "default": no niche, no playlists, its own old sign-in
(`config/secrets/youtube_token.json`, no analytics scope), and it was queued public there.
The menu's default came from `CONTENT_CHANNEL_ID`, which falls back to "default".

Now Enter means the channel of the latest run on a real channel (an explicit
`CONTENT_CHANNEL_ID` still wins), "Default" says what it is, picking it says so, and a
public upload on it needs a yes.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

RUNS = {"tapin": [5, 112], "moneywise": [20], "default": [113]}


def _repo():
    return SimpleNamespace(
        list_for_channel=lambda cid, status=None: [SimpleNamespace(id=i) for i in RUNS.get(cid, [])]
    )


def _menu(answer="", env=None):
    from core.ui import prompt_channel_selection

    printed: list[str] = []
    environ = {k: v for k, v in os.environ.items() if k != "CONTENT_CHANNEL_ID"}
    environ.update(env or {})
    with (
        patch.dict(os.environ, environ, clear=True),
        patch("storage.repositories.content_runs.get_content_run_repository", return_value=_repo()),
    ):
        picked = prompt_channel_selection(
            print_fn=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
            input_fn=lambda *_: answer,
        )
    return picked, "\n".join(printed)


class MenuTests(unittest.TestCase):
    def test_enter_takes_the_last_real_channel_used(self):
        picked, _text = _menu()
        self.assertEqual(picked, "tapin")

    def test_an_explicit_setting_still_wins(self):
        picked, _text = _menu(env={"CONTENT_CHANNEL_ID": "moneywise"})
        self.assertEqual(picked, "moneywise")

    def test_default_says_what_it_is(self):
        _picked, text = _menu()
        default_line = next(line for line in text.splitlines() if "(default)" in line)
        self.assertIn("not a channel", default_line)

    def test_picking_default_warns(self):
        picked, text = _menu(answer="1")
        self.assertEqual(picked, "default")
        self.assertIn("generic sign-in", text)

    def test_no_runs_yet_falls_back_to_the_setting(self):
        from core.ui import prompt_channel_selection

        with (
            patch.dict(os.environ, {"CONTENT_CHANNEL_ID": "tapin"}),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                side_effect=RuntimeError("no db"),
            ),
        ):
            picked = prompt_channel_selection(print_fn=lambda *a, **k: None,
                                              input_fn=lambda *_: "")  # fmt: skip
        self.assertEqual(picked, "tapin")


class PublicOnDefaultTests(unittest.TestCase):
    def _plan(self, channel, answers):
        from core.ui import prompt_upload_plan

        replies = iter(answers)
        printed: list[str] = []
        now = datetime(2026, 10, 5, 18, tzinfo=timezone.utc)
        with (
            patch("core.ui.display_upload_queue"),
            patch("analytics.post_timing.next_optimal_post_time", return_value=now),
            patch("analytics.post_timing.format_scheduled_local", return_value="Fri 6:00 PM"),
        ):
            plan = prompt_upload_plan(
                channel_id=channel,
                topic="NBA preseason",
                print_fn=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
                input_fn=lambda *_: next(replies),
            )
        return plan, "\n".join(printed)

    def test_public_on_default_needs_a_yes(self):
        plan, text = self._plan("default", ["2", "3", ""])
        self.assertEqual(plan.privacy_status, "private")
        self.assertIn("generic sign-in", text)

    def test_public_on_default_with_a_yes_stays_public(self):
        plan, _text = self._plan("default", ["2", "3", "y"])
        self.assertEqual(plan.privacy_status, "public")

    def test_a_real_channel_is_not_asked(self):
        plan, _text = self._plan("tapin", ["2", "3"])
        self.assertEqual(plan.privacy_status, "public")


if __name__ == "__main__":
    unittest.main()
