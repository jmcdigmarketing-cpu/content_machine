"""Wave 99 (#1230-#1232): what held the videos back, from the operator's terminal of 2026-10-16.

- 7:07 PM: `py -m scripts.ops worker` uploaded job 58 (run 126) and stopped. Job 59 (run 155),
  due since 5:10 PM, stayed pending - a single pass was one `process_one()`.
- Overnight was paused: 3 finished videos on the shelf, one of them run 114 (Shevchenko, UFC
  news) - rendered 11.9 days ago, a 2-day window, never uploaded. A render counted until 30 days.
- TikTok and Instagram waited on R2_PUBLIC_BASE_URL, and the line said only that. The bucket's
  public address is switched on in Cloudflare; then it has to reach .env.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---- #1230: one pass sends every upload that is due ---------------------------------------------


class WorkerTests(unittest.TestCase):
    def test_one_pass_sends_both_due_uploads(self):
        from jobs import worker

        with patch.object(worker, "process_one", side_effect=[True, True, False]) as one:
            self.assertEqual(worker.drain_due(), 2)
        self.assertEqual(one.call_count, 3)

    def test_a_pass_stops_at_its_cap(self):
        from jobs import worker

        with patch.object(worker, "process_one", return_value=True) as one:
            self.assertEqual(worker.drain_due(), worker.PASS_CAP)
        self.assertEqual(one.call_count, worker.PASS_CAP)

    def test_the_single_pass_command_drains(self):
        from jobs import worker

        with (
            patch.object(sys, "argv", ["jobs.worker"]),
            patch.object(worker, "process_one", side_effect=[True, True, False]) as one,
        ):
            worker.main()
        self.assertEqual(one.call_count, 3)


# ---- #1231: a render past twice its window stops holding a shelf place --------------------------


def _run(run_id, title, age):
    return SimpleNamespace(id=run_id, title=title, topic="", mp4_path=f"r{run_id}.mp4", _age=age)


class ShelfTests(unittest.TestCase):
    def _rows(self, runs, queued=()):
        from core import stale_renders

        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=runs),
            patch("publishing.go_public.unlisted_holds", return_value=[]),
            patch("publishing.go_public.override_held", return_value=False),
            patch.object(stale_renders, "_queued_runs", return_value={r: object() for r in queued}),
            patch.object(stale_renders, "_signed_out", return_value=False),
            patch.object(stale_renders, "render_age_days", side_effect=lambda run: run._age),
            # Wave 111: run 155's title names Titans at Colts, which kicked off 17:00Z on
            # 2026-10-18 - from then the real clock made this "its game has started". The
            # tests here are about age and window.
            patch.object(stale_renders, "_event_started", return_value=False),
            # 2026-10-27: the shelf reads the event through `run_event` now, which found run
            # 155's real draft in output/tapin/drafts (its Oct 18 kickoff) on the PC - "started".
            patch.object(stale_renders, "run_event", return_value=None),
        ):
            return stale_renders.shelf_rows("tapin")

    def test_run114_is_past_its_window_and_not_counted(self):
        run114 = _run(
            114, "Shevchenko demands immediate title shot after Silva's UFC 332 win", 11.9
        )
        rows = self._rows([run114])
        self.assertIn("past its window", rows[0]["state"])
        self.assertIn("retire-renders", rows[0]["command"])
        self.assertTrue(rows[0].get("stale"))
        from core.batch_review import shelf_waiting

        with patch("core.stale_renders.shelf_rows", return_value=rows):
            self.assertEqual(shelf_waiting("tapin"), 0)

    def test_a_fresh_render_still_counts(self):
        run155 = _run(155, "Tennessee Titans' offensive line faces test vs Colts", 0.1)
        rows = self._rows([run155])
        self.assertFalse(rows[0].get("stale"))
        from core.batch_review import shelf_waiting

        with patch("core.stale_renders.shelf_rows", return_value=rows):
            self.assertEqual(shelf_waiting("tapin"), 1)

    def test_a_queued_upload_always_counts(self):
        old = _run(114, "Shevchenko demands immediate title shot after Silva's UFC 332 win", 11.9)
        rows = self._rows([old], queued=(114,))
        self.assertEqual(rows[0]["state"], "queued, waiting for the worker")
        self.assertFalse(rows[0].get("stale"))


# ---- #1232: `ops crosspost public-url` --------------------------------------------------------------

R2 = {
    "R2_ACCOUNT_ID": "acct",
    "R2_ACCESS_KEY_ID": "key",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_BUCKET": "tapin",
    "R2_PUBLIC_BASE_URL": "",
}


class PublicUrlTests(unittest.TestCase):
    def test_an_address_that_is_not_https_is_refused(self):
        from publishing.video_host import check_public_url

        with patch.dict(os.environ, R2):
            self.assertIn("https://", check_public_url("http://pub-abc.r2.dev"))

    def test_the_address_is_tried_the_way_buffer_reads_it(self):
        from publishing.video_host import check_public_url

        client = MagicMock()
        head = MagicMock(return_value=SimpleNamespace(status_code=200))
        get = MagicMock(return_value=SimpleNamespace(status_code=206))
        with patch.dict(os.environ, R2):
            problem = check_public_url("https://pub-abc.r2.dev/", client=client, head=head, get=get)
            self.assertEqual(os.environ["R2_PUBLIC_BASE_URL"], "")  # put back
        self.assertEqual(problem, "")
        self.assertTrue(head.call_args.args[0].startswith("https://pub-abc.r2.dev/selftest/"))
        client.delete_object.assert_called_once()

    def test_a_403_is_said(self):
        from publishing.video_host import check_public_url

        head = MagicMock(return_value=SimpleNamespace(status_code=403))
        with patch.dict(os.environ, R2):
            problem = check_public_url(
                "https://pub-abc.r2.dev", client=MagicMock(), head=head, get=MagicMock()
            )
        self.assertIn("403", problem)

    def _env(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, ".env")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path

    def test_the_line_is_written_once(self):
        from core.secrets_doctor import set_env_value

        path = self._env("A=1\r\nR2_PUBLIC_BASE_URL=old\r\nB=2\r\n")
        set_env_value("R2_PUBLIC_BASE_URL", "https://pub-abc.r2.dev", path=path)
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        self.assertEqual(text, "A=1\r\nR2_PUBLIC_BASE_URL=https://pub-abc.r2.dev\r\nB=2\r\n")

    def test_a_missing_line_is_added_at_the_end(self):
        from core.secrets_doctor import set_env_value

        path = self._env("A=1\nB=2")
        set_env_value("R2_PUBLIC_BASE_URL", "https://pub-abc.r2.dev", path=path)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "A=1\nB=2\nR2_PUBLIC_BASE_URL=https://pub-abc.r2.dev\n")

    def _ops(self, problem):
        from scripts import ops

        args = SimpleNamespace(
            command="crosspost", target="public-url", value="https://pub-abc.r2.dev",
            channel="tapin", apply=False,
        )  # fmt: skip
        with (
            patch("publishing.video_host.check_public_url", return_value=problem),
            patch("core.secrets_doctor.set_env_value") as write,
        ):
            code = ops.cmd_crosspost(args)
        return code, write

    def test_ops_writes_it_only_when_it_works(self):
        code, write = self._ops("")
        self.assertEqual(code, 0)
        write.assert_called_once_with("R2_PUBLIC_BASE_URL", "https://pub-abc.r2.dev")
        code, write = self._ops("the public address answers 403 to HEAD")
        self.assertEqual(code, 1)
        write.assert_not_called()

    def test_the_waiting_line_says_what_to_do(self):
        from publishing import crosspost

        line = crosspost.waits_line(["R2_PUBLIC_BASE_URL"])
        self.assertIn("Public Development URL", line)
        self.assertIn("py -m scripts.ops crosspost public-url", line)


if __name__ == "__main__":
    unittest.main()
