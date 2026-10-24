"""Wave 127 (2026-10-24): catch up, then the next ten.

Measured first, Sat 15:36 CDT: the PC was shut down at 1:00 AM, so there was no 3:05 AM pass
and run 184's UFC 333 preview was taken off the queue after the card - and on Friday at 8:07
PM the worker had uploaded two videos that could wait before it. Run 185 was held for "The
Chiefs are 5-0" and "The game is in Seattle" (#1560, filed: ESPN's line was in the facts); run 187's
YouTube signal read a dropped connection ("0\\r\\n") as broken; every pass logged google's
Python 3.11 FutureWarning.
"""

from __future__ import annotations

import http.client
import json
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class PreviewFirstTests(unittest.TestCase):
    """#1563: a preview due before the next reset is claimed before uploads that can wait."""

    def test_the_preview_gets_the_first_key(self):
        from jobs import worker

        def job(job_id, run_id):
            return SimpleNamespace(id=job_id, content_run_id=run_id, job_type="upload", status="pending",
                                   channel_id="tapin", payload_json=json.dumps({"title": f"run {run_id}"}))  # fmt: skip

        jobs = [job(79, 182), job(80, 184)]
        repo = MagicMock()
        repo.list_active_jobs.return_value = jobs
        runs = MagicMock()
        runs.get.side_effect = lambda r: SimpleNamespace(id=r, title=f"run {r}", mp4_path="")
        card = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
        with (
            patch.object(worker, "get_job_repository", return_value=repo),
            patch.object(worker, "get_content_run_repository", return_value=runs),
            patch(
                "core.stale_renders.run_event",
                side_effect=lambda run, c, a: card if run.id == 184 else None,
            ),
            patch(
                "core.stale_renders._now",
                return_value=datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc),
            ),
        ):
            moved = worker._previews_first()
        self.assertEqual(moved, [80])
        stored = json.loads(repo.update.call_args.args[1]["payload_json"])
        self.assertLess(stored["sort_key"], 79)

    def test_the_stores_claim_by_that_key(self):
        from storage.repositories.jobs import _claim_sort_tuple

        late = {"id": 79, "payload_json": "{}"}
        first = {"id": 80, "payload_json": json.dumps({"sort_key": -70000000})}
        self.assertLess(_claim_sort_tuple(first), _claim_sort_tuple(late))


class TransientHttpTests(unittest.TestCase):
    """#1562: run 187's youtube signal read a dropped connection as broken."""

    def test_a_bad_status_line_is_unavailable(self):
        from apis.signal_contract import STATUS_UNAVAILABLE, classify_exception

        status, detail = classify_exception(http.client.BadStatusLine("0\r\n"))
        self.assertEqual(status, STATUS_UNAVAILABLE)
        self.assertIn("BadStatusLine", detail)

    def test_a_bare_number_is_unavailable(self):
        from apis.signal_contract import STATUS_UNAVAILABLE, classify_exception

        status, detail = classify_exception(Exception("0\r\n"))
        self.assertEqual(status, STATUS_UNAVAILABLE)
        self.assertIn("Exception", detail)

    def test_a_real_error_is_still_an_error(self):
        from apis.signal_contract import STATUS_ERROR, classify_exception

        self.assertEqual(classify_exception(ValueError("bad payload shape"))[0], STATUS_ERROR)


class FutureWarningTests(unittest.TestCase):
    """#1561: google.api_core's Python 3.11 notice is logged once a deadline is filed (#1564)."""

    def test_the_notice_is_filtered(self):
        import core.logging

        found = [
            f for f in warnings.filters
            if f[2] is FutureWarning and f[3] is not None and "google" in f[3].pattern
        ]  # fmt: skip
        self.assertTrue(found)

    def test_other_future_warnings_still_show(self):
        import core.logging

        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("default")
            warnings.warn_explicit("x", FutureWarning, "f.py", 1, module="mine")
        self.assertTrue(seen)


def _draft(script, **meta):
    from core.batch_review import PendingDraft

    base = {"run_id": 1, "created_at": datetime.now().isoformat(), "authenticity_verdict": "ok"}
    return PendingDraft("f", {**base, **meta}, script)


AHEAD = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%MZ")


class PreviewReadTests(unittest.TestCase):
    """#1361 and #1367 (the operator: hold) - a preview read before it renders."""

    def _reason(self, draft):
        from core import batch_review

        with patch.object(batch_review, "authenticity_now", return_value=("ok", "")):
            return batch_review.unattended_block_reason(draft)

    def test_a_bout_called_as_won_waits(self):
        draft = _draft(
            "Volkanovski beat Evloev on the scorecards in Abu Dhabi. Here is how it went. Tap in.",
            title="Volkanovski vs Evloev Preview: what decides UFC 333", topic="UFC 333 preview",
            event_at=AHEAD,
        )  # fmt: skip
        self.assertIn("states a result", self._reason(draft))

    def test_a_preview_with_no_call_waits(self):
        draft = _draft(
            "The Chiefs are 5-0 and the Seahawks are 3-3. Seattle's defense ranks fourth. Tap in.",
            title="Chiefs at Seahawks: the numbers", topic="Kansas City Chiefs at Seattle Seahawks",
            event_at=AHEAD,
        )  # fmt: skip
        self.assertEqual(self._reason(draft), "a preview with no call")

    def test_a_preview_with_a_call_goes(self):
        draft = _draft(
            "The Chiefs are 5-0. Seattle will win at home because its pass rush wins the line. Tap in.",
            title="Chiefs at Seahawks: the call", topic="Kansas City Chiefs at Seattle Seahawks",
            event_at=AHEAD,
        )  # fmt: skip
        self.assertNotIn("call", self._reason(draft))

    def test_news_needs_no_call(self):
        draft = _draft("Mass Effect 5 footage leaked on Friday. EA has not commented. Tap in.",
                       title="Mass Effect 5 leak", topic="Mass Effect 5 leak")  # fmt: skip
        self.assertNotIn("call", self._reason(draft))


class LiveGameTests(unittest.TestCase):
    """#1364 (the operator: leave it off): a game in progress is no idea."""

    def test_an_in_progress_game_is_skipped(self):
        from datetime import date

        from core.seasonal_calendar import topics_from_board

        def event(name, state):
            return {"name": name, "date": "2026-10-24T18:00Z",
                    "status": {"type": {"state": state, "completed": state == "post"}},
                    "competitions": [{"competitors": []}]}  # fmt: skip

        board = {"events": [event("Miami Dolphins at Buffalo Bills", "in"),
                            event("Denver Broncos at Las Vegas Raiders", "pre")]}  # fmt: skip
        names = [t[0] for t in topics_from_board("nfl", board, today=date(2026, 10, 24))]
        self.assertNotIn("Miami Dolphins at Buffalo Bills", names)
        self.assertIn("Denver Broncos at Las Vegas Raiders", names)


class ShortsTitleSignalTests(unittest.TestCase):
    """#1409 (the operator: stayed share): a Short's title outcome is the share who stayed."""

    def test_a_short_uses_stayed(self):
        from core import title_experiments

        run = SimpleNamespace(id=1, title="Chiefs at Seahawks: the call", selected_topic="")
        log = SimpleNamespace(content_run_id=1, metrics_json=json.dumps(
            {"views": 100, "engaged_views": 40, "stayed_share": 0.4, "average_view_percentage": 80,
             "engaged_rate": 0.8, "duration_seconds": 40}))  # fmt: skip
        runs, logs = MagicMock(), MagicMock()
        runs.list_for_channel.return_value = [run]
        logs.list_timed_outcomes.return_value = [log]
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=runs
            ),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=logs),
            patch(
                "analytics.packaging.packaging_figures", return_value={"short": True, "stayed": 0.4}
            ),
        ):
            got = title_experiments._titled_outcomes("tapin")
        self.assertEqual(got, [("Chiefs at Seahawks: the call", 0.4)])


class WeeklyMixTests(unittest.TestCase):
    """#1365: overnight's week by kind - games, news, the rest."""

    def test_the_mix(self):
        from analytics.weekly_report import draft_mix_line

        drafts = [{"event_at": "2026-10-24T17:00Z", "topic": "UFC 333"},
                  {"topic": "Mass Effect 5 leak", "title": "Mass Effect 5 leaked trailer"},
                  {"topic": "Best Madden 27 playbooks", "title": "Madden 27 playbooks"}]  # fmt: skip
        with patch(
            "core.batch_review.freshness_window_days",
            side_effect=lambda m: 2.0 if "leak" in m.get("topic", "") else 7.0,
        ):
            line = draft_mix_line(drafts)
        self.assertEqual(line, "Overnight's mix this week: 1 game, 1 news, 1 other (3 drafts)")


class LiveThumbnailTests(unittest.TestCase):
    """#1541: the live image compared with ours, from i.ytimg.com (no quota)."""

    def _images(self):
        from PIL import Image, ImageDraw

        ours = Image.new("RGB", (1080, 1920), (20, 60, 200))
        ImageDraw.Draw(ours).rectangle((100, 600, 980, 1300), fill=(250, 220, 30))
        live = Image.new("RGB", (480, 360), (0, 0, 0))
        live.paste(ours.resize((202, 360)), (139, 0))  # letterboxed, as YouTube shows a Short
        other = Image.new("RGB", (480, 360), (0, 0, 0))
        other.paste(Image.new("RGB", (202, 360), (230, 230, 230)), (139, 0))
        return ours, live, other

    def test_ours_is_recognised_in_the_letterbox(self):
        from youtube.thumbnail_check import same_image

        ours, live, other = self._images()
        self.assertTrue(same_image(ours, live))
        self.assertFalse(same_image(ours, other))

    def test_the_check_reads_the_live_image(self):
        import io as _io

        from youtube import thumbnail_check

        ours, live, _other = self._images()
        buf = _io.BytesIO()
        live.save(buf, "JPEG")
        with patch.object(thumbnail_check, "_fetch_live", return_value=buf.getvalue()):
            verdict = thumbnail_check.check_video("vid", ours)
        self.assertEqual(verdict, "ours")

    def test_unread_is_said(self):
        from youtube import thumbnail_check

        ours, _live, _other = self._images()
        with patch.object(thumbnail_check, "_fetch_live", return_value=None):
            self.assertEqual(thumbnail_check.check_video("vid", ours), "unread")

    def test_ops_thumbnail_check_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("thumbnail-check", COMMANDS)


if __name__ == "__main__":
    unittest.main()
