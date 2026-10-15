"""Wave 91 (#1200-#1204): TikTok/Instagram and the morning, from 2026-10-15.

- The operator posts some videos to TikTok and Instagram by hand in Buffer: Topuria went out on
  Oct 11 (TikTok) and Oct 14 (Instagram), four days before it went public on YouTube. Those posts
  begin with the video's opening line ("Gaethje TKO'd Topuria at UFC Freedom 250 - and wrote
  the blueprint"), not its title. The automatic round never looked, so it would have posted a
  second copy. The operator: skip that platform only.
- `ops crosspost done --run-id 132` answered "never packed" - a hand post had no way to be
  recorded for the automatic round.
- Topuria went public through the worker; the round only ran from go-public, the morning and
  overnight. The operator: right away.
- Run 126 waited a day for the worker; the operator ran it by hand. The operator: offer it each
  morning - and "is morning ... included in script ops all??? that is what i want".
"""

from __future__ import annotations

import io
import os
import tempfile
import time
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

from tests.test_buffer_crosspost import CrosspostCase

TOPURIA_POST = (
    "Gaethje TKO'd Topuria at UFC Freedom 250 - and wrote the blueprint to beat him. #UFC #Topuria"
)
TOPURIA_RUN = (
    "Topuria's outlook: Can he adapt before UFC's next title cycle? Gaethje beat Topuria and "
    "wrote the blueprint. Fourth-round TKO at UFC Freedom 250, Topuria's first pro loss, and "
    "the lightweight belt gone."
)


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---- #1200: a hand post in Buffer is not posted again --------------------------------------------


class MatchTests(unittest.TestCase):
    def test_topurias_hand_post_is_its_opening_line(self):
        from publishing.crosspost import hand_post_matches

        self.assertTrue(hand_post_matches(TOPURIA_POST, TOPURIA_RUN))

    def test_a_post_about_something_else_is_not(self):
        from publishing.crosspost import hand_post_matches

        other = "The Chargers are 0-4 for the first time since 2017, with the worst start in years."
        self.assertFalse(hand_post_matches(other, TOPURIA_RUN))


class HandPostTests(CrosspostCase):
    def setUp(self):
        super().setUp()
        rendered = datetime.now(timezone.utc) - timedelta(days=3)
        for run in self.runs.values():
            os.utime(run.mp4_path, (rendered.timestamp(), rendered.timestamp()))
            run.script_preview = f"{run.title}. 36 players are on the injury report."
        self.posts: dict[str, list[dict]] = {"tt1": [], "ig1": []}
        self.finder = MagicMock(side_effect=lambda org, ch: list(self.posts.get(ch, [])))
        p = patch("publishing.buffer_api.find_posts", self.finder)
        p.start()
        self.addCleanup(p.stop)

    def _hand_post(self, channel, *, days_ago=1, text=None):
        when = datetime.now(timezone.utc) - timedelta(days=days_ago)
        self.posts[channel].append({
            "id": f"hand-{channel}", "status": "sent", "sentAt": _iso(when), "dueAt": _iso(when),
            "text": text or "Ravens face injury crisis ahead of Browns showdown with 36 players",
            "externalLink": f"https://example.com/{channel}/hand",
        })  # fmt: skip

    def test_a_hand_post_on_tiktok_skips_tiktok_only(self):
        self._hand_post("tt1")
        self._first_then((113, "yt113"))
        self.assertEqual([c.kwargs["service"] for c in self.create.call_args_list], ["instagram"])
        tiktok = self._store()["posts"]["113"]["tiktok"]
        self.assertEqual(tiktok["state"], "manual")
        self.assertEqual(tiktok["link"], "https://example.com/tt1/hand")

    def test_a_post_from_before_the_render_is_another_video(self):
        self._hand_post("tt1", days_ago=20)  # same words, posted before this video existed
        self._first_then((113, "yt113"))
        services = sorted(c.kwargs["service"] for c in self.create.call_args_list)
        self.assertEqual(services, ["instagram", "tiktok"])

    def test_buffer_is_read_once_per_channel_a_round(self):
        self._first_then((113, "yt113"), (114, "yt114"))
        self.assertLessEqual(self.finder.call_count, 2)

    def test_done_records_a_hand_post_the_round_leaves(self):
        from publishing.crosspost import mark_posted, send_due

        send_due("tapin")  # switched on
        self.assertTrue(mark_posted("tapin", 113))  # never packed: a hand post
        self.public.append((113, "yt113"))
        send_due("tapin")
        self.create.assert_not_called()
        self.assertEqual(self._store()["posts"]["113"]["instagram"]["state"], "manual")


# ---- #1202: the worker starts the round ------------------------------------------------------------


class WorkerTests(unittest.TestCase):
    def _finalize(self, status):
        from jobs import worker

        job = SimpleNamespace(id=9, content_run_id=132, channel_id="tapin", attempts=1,
                              max_attempts=3)  # fmt: skip
        result = SimpleNamespace(status=status, video_id="VX1N97nQXgU", detail="",
                                 thumbnail_status="set", thumbnail_detail="")  # fmt: skip
        with (
            patch.object(worker, "get_job_repository"),
            patch.object(worker, "get_content_run_repository"),
            patch.object(worker, "_defer_for_quota", return_value=False),
            patch(
                "publishing.crosspost.step", return_value=["  run 132 TikTok: scheduled"]
            ) as step,
            redirect_stdout(io.StringIO()) as out,
        ):
            worker._finalize_upload_job(job, result)
        return step, out.getvalue()

    def test_an_upload_starts_the_round(self):
        step, out = self._finalize("uploaded")
        step.assert_called_once_with("tapin")
        self.assertIn("run 132 TikTok: scheduled", out)

    def test_a_scheduled_upload_waits_for_its_slot(self):
        step, _out = self._finalize("scheduled")
        step.assert_not_called()

    def test_queued_uploads_are_sent_up_to_the_number_asked(self):
        from jobs import worker

        jobs = [SimpleNamespace(id=i, job_type="upload") for i in (1, 2, 3)]
        repo = MagicMock()
        repo.claim_next.side_effect = lambda job_type=None: jobs.pop(0) if jobs else None
        with (
            patch.object(worker, "get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch.object(worker, "_process_upload") as process,
        ):
            sent = worker.send_queued_uploads(2)
        self.assertEqual(sent, 2)
        self.assertEqual(process.call_count, 2)
        repo.claim_next.assert_called_with(job_type="upload")


# ---- #1203 / #1204: the morning, and ops all ---------------------------------------------------------


class MorningOfferTests(unittest.TestCase):
    def _batch(self, name, *, console=True, answer="y", queued=2, installed=False):
        from scripts import ops

        commands = {n: (h, lambda _a: 0) for n, (h, _f) in ops.COMMANDS.items()}
        asked: list[str] = []
        with (
            patch.dict(ops.COMMANDS, commands),
            patch.object(ops, "_batch_sign_in", return_value=""),
            patch.object(ops, "_batch_sign_in_reminder", return_value=""),
            patch.object(ops, "_has_console", return_value=console),
            patch.object(ops, "_queued_uploads", return_value=queued),
            patch.object(ops, "_worker_installed", return_value=installed),
            patch("builtins.input", side_effect=lambda p: asked.append(p) or answer),
            patch("jobs.worker.send_queued_uploads", return_value=queued) as send,
            redirect_stdout(io.StringIO()),
        ):
            ops._run_batch(name, Namespace(channel="tapin"))
        return asked, send

    def test_queued_uploads_are_offered_and_sent(self):
        asked, send = self._batch("morning")
        self.assertTrue(any("Send the 2 queued uploads now" in a for a in asked))
        send.assert_called_once_with(2)

    def test_a_no_sends_nothing(self):
        _asked, send = self._batch("morning", answer="n")
        send.assert_not_called()

    def test_an_installed_task_is_not_asked(self):
        asked, send = self._batch("morning", installed=True)
        self.assertEqual(asked, [])
        send.assert_not_called()

    def test_no_console_no_question(self):
        asked, _send = self._batch("morning", console=False)
        self.assertEqual(asked, [])

    def test_ops_all_offers_it_too(self):
        _asked, send = self._batch("all")
        send.assert_called_once_with(2)


class AllTests(unittest.TestCase):
    def test_ops_all_includes_the_morning(self):
        from scripts import ops

        leaves = ops.batch_leaves("all")
        for step in (
            "crosspost-send",
            "overnight-last",
            "shelf",
            "corrections-open",
            "batch-review",
        ):
            self.assertIn(step, leaves)
        self.assertEqual(leaves.count("sync-metrics"), 1)
        self.assertEqual(leaves[-1], "batch-review")


# ---- found by the live draft: Buffer needs a public address ------------------------------------------


class PublicAddressTests(unittest.TestCase):
    ENV: ClassVar[dict[str, str]] = {
        "R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "id", "R2_SECRET_ACCESS_KEY": "s",
        "R2_BUCKET": "videos", "R2_PUBLIC_BASE_URL": "https://pub-test.r2.dev",
    }  # fmt: skip

    def test_no_public_address_is_not_set_up(self):
        from publishing import video_host

        with patch.dict(os.environ, {**self.ENV, "R2_PUBLIC_BASE_URL": ""}):
            self.assertEqual(video_host.missing(), ["R2_PUBLIC_BASE_URL"])

    def test_the_name_cannot_be_guessed(self):
        from publishing.video_host import object_key

        first, second = (object_key("tapin", 132, "C:/x/topuria.mp4") for _ in range(2))
        self.assertTrue(first.startswith("tapin/run132-") and first.endswith(".mp4"))
        self.assertNotEqual(first, second)

    def test_the_self_test_reads_it_the_way_buffer_does(self):
        from publishing.video_host import self_test

        refused = SimpleNamespace(status_code=403)
        with patch.dict(os.environ, self.ENV):
            problem = self_test(client=MagicMock(), head=lambda url, **kw: refused)
        self.assertIn("403", problem)
        ok = SimpleNamespace(status_code=200)
        part = SimpleNamespace(status_code=206)
        with patch.dict(os.environ, self.ENV):
            self.assertEqual(
                self_test(client=MagicMock(), head=lambda u, **k: ok, get=lambda u, **k: part), ""
            )

    def test_it_switches_on_while_the_bucket_is_not_ready(self):
        from publishing import crosspost

        with tempfile.TemporaryDirectory() as tmp, (
            patch("publishing.crosspost.CROSSPOST_TEMPLATE",
                  os.path.join(tmp, "crosspost_{channel}.json"))
        ), patch("publishing.crosspost._public_runs", return_value=[(132, "VX1N97nQXgU")]), (
            patch("publishing.buffer_api.configured", return_value=True)
        ), patch("publishing.video_host.missing", return_value=["R2_PUBLIC_BASE_URL"]), (
            patch("publishing.video_host.configured", return_value=False)
        ), patch.dict(os.environ, {"CROSSPOST_AUTO": "true"}):  # fmt: skip
            crosspost.save_channels("tapin", "org1", {"tiktok": "tt1", "instagram": "ig1"})
            lines = crosspost.step("tapin")
            block = crosspost._load("tapin")["buffer"]
        self.assertTrue(block.get("since"))
        self.assertEqual(block["baseline"], [132])  # Topuria went out by hand
        self.assertIn("R2_PUBLIC_BASE_URL", "\n".join(lines))


# ---- the live draft (#1200 verification) --------------------------------------------------------------


class DraftTests(unittest.TestCase):
    def test_a_draft_is_saved_not_scheduled(self):
        from publishing.buffer_api import post_input

        body = post_input("tt1", text="t", video_url="u", due_at=datetime.now(timezone.utc),
                          service="tiktok", draft=True)  # fmt: skip
        self.assertTrue(body["saveToDraft"])
        self.assertNotIn("saveToDraft", post_input("tt1", text="t", video_url="u",
                                                   due_at=datetime.now(timezone.utc),
                                                   service="tiktok"))  # fmt: skip


if __name__ == "__main__":
    unittest.main()
