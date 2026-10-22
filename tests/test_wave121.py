"""Wave 121 (2026-10-22): the next ten, batch A - the roadmap's five.

Measured first, on 9e03058:
- `ops retention` read over 100% at 3 s on 5 of 8 videos (a replayed opening is counted again),
  and the share who stayed rather than swiped - `stayed_share`, synced on each video - was not
  shown beside it (#1538).
- `entity_lookup.names_for` kept "Los Angeles Chargers'", "Call of Dutys", "Modern Warfare
  Steam", "UFC Edmonton KO" and, from "the new England Patriots", "England Patriots" beside the
  team's full name (#1539).
- health had no "unknown": a check that could not read its input said "n/a" as YELLOW, and a
  $0.00 revenue on every video - what YouTube returns for a channel that is not monetized - read
  RED "negative margin" (#1472).
- health kept no history: one run's colours were all there was (#1475).
- the sync asked YouTube for each video's status only, so a title or description edited in
  Studio never reached the record the learning reads (#1390).

Batch B - five neighbours, measured the same way:
- health's colour thresholds sat in six functions with no version, so two days of #1475's
  history could not say they were read on the same rules (#1479).
- the cost line read the runs' API estimate ($0.05 a video) and never the spend entered with
  `ops spend` (subscriptions, credits) (#1478).
- "NE vs BUF week 7" and "Can NE win the AFC East?" named no team, and "NE Patriots" was
  researched beside "New England Patriots" (#1487).
- the morning said "Python crashed: heap corruption" and never where - the log faulthandler
  wrote names the Python line (#1469).
- the title check passed "New England Patriots fans meet England Patriots": a team named in
  full once hid the broken one (#1486, in #1391's place - the API cannot say which thumbnail
  image is live).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

CURVE = [(0.0, 1.2), (0.05, 0.98), (0.1, 0.9), (0.5, 0.5)]


class StayedShareTests(unittest.TestCase):
    """#1538: the share who stayed beside the 3-second number."""

    def test_the_text(self):
        from core.retention import first_seconds_text

        self.assertEqual(
            first_seconds_text(CURVE, 300.0, stayed=0.64),
            "120% at 3 s (the opening was replayed); 64% stayed rather than swiped",
        )
        self.assertEqual(
            first_seconds_text(CURVE, 60.0, stayed=0.712),
            "98% still watching at 3 s; 71% stayed rather than swiped",
        )
        self.assertEqual(first_seconds_text(CURVE, 60.0), "98% still watching at 3 s")

    def test_the_lines_read_the_synced_share(self):
        from datetime import datetime, timezone

        from core import retention

        metrics = {"retention_curve": [[0.0, 1.2], [0.05, 0.98], [0.5, 0.5]], "stayed_share": 0.58}
        log = SimpleNamespace(
            content_run_id=170,
            published_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
            metrics_json=json.dumps(metrics),
        )
        logs = SimpleNamespace(list_timed_outcomes=lambda channel: [log])
        runs = SimpleNamespace(get=lambda rid: SimpleNamespace(id=rid, title="Chargers week 7"))
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=logs),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=runs
            ),
            patch.object(retention, "_render_seconds", return_value=300.0),
        ):
            lines = retention.first_seconds_lines("tapin")
        self.assertEqual(len(lines), 1)
        self.assertIn("58% stayed rather than swiped", lines[0])


class ResearchNameTests(unittest.TestCase):
    """#1539: a research name is the name, not a fragment of one."""

    def test_the_five_fragments(self):
        from core.facts.entity_lookup import names_for

        self.assertEqual(names_for("Los Angeles Chargers' playoff push"), ["Los Angeles Chargers"])
        self.assertEqual(
            names_for("Call of Dutys new Modern Warfare Steam release"),
            ["Call of Duty", "Modern Warfare"],
        )
        self.assertEqual(names_for("UFC Edmonton KO of the night"), ["UFC Edmonton"])
        got = names_for("Can the new England Patriots win the AFC East?")
        self.assertIn("New England Patriots", got)
        self.assertNotIn("England Patriots", got)

    def test_a_real_name_is_left_alone(self):
        from apis.topic_tokens import trim_name

        for name in ("Blue Jays", "Dallas Cowboys", "Guys", "Call of Duty", "KO"):
            self.assertEqual(trim_name(name), name, name)
        self.assertEqual(trim_name("Los Angeles Chargers'"), "Los Angeles Chargers")
        self.assertEqual(trim_name("Herbert's"), "Herbert")

    def test_the_search_names_too(self):
        # the sibling: `subject_terms` names the news search, and kept the same fragments
        from apis.topic_tokens import subject_terms

        self.assertEqual(
            subject_terms("Los Angeles Chargers' playoff push"), ["Los Angeles Chargers"]
        )
        self.assertEqual(
            subject_terms("Call of Dutys new Modern Warfare Steam release"),
            ["Call of Duty", "Modern Warfare"],
        )


class HealthUnknownTests(unittest.TestCase):
    """#1472: a missing input reads unknown, never RED."""

    def test_a_check_that_cannot_read_says_unknown(self):
        from core import channel_health as ch

        def boom(_channel):
            raise RuntimeError("no publish log")

        checks = tuple((n, boom if n == "cost" else (lambda _c, n=n: ch.HealthSub(n, ch.GREEN, "ok")))
                       for n, _f in ch._CHECKS)  # fmt: skip
        with patch.object(ch, "_CHECKS", checks):
            report = ch.build_health("tapin")
        cost = next(s for s in report.subs if s.name == "cost")
        self.assertEqual(cost.status, ch.UNKNOWN)
        self.assertIn("unknown", cost.detail)
        self.assertNotEqual(report.overall, ch.RED)
        self.assertIn("unknown: cost", ch.health_line(report))
        self.assertIn("UNKNOWN", ch.render_health(report))

    def test_zero_revenue_everywhere_is_not_a_negative_margin(self):
        from core import channel_health as ch
        from core.unit_economics import ChannelEconomics, VideoEconomics

        econ = ChannelEconomics(channel_id="tapin")
        econ.videos = [
            VideoEconomics(run_id=i, title="t", cost_usd=0.05, revenue_usd=0.0, views=300,
                           engaged_rate=0.4)
            for i in range(1, 5)
        ]  # fmt: skip
        with patch("core.unit_economics.channel_economics", return_value=econ):
            sub = ch._cost_sub("tapin")
        self.assertNotEqual(sub.status, ch.RED)
        self.assertIn("not monetized", sub.detail)


class HealthHistoryTests(unittest.TestCase):
    """#1475: one line a day."""

    def _report(self, overall):
        from core import channel_health as ch

        report = ch.HealthReport(channel_id="tapin", overall=overall)
        report.subs = [
            ch.HealthSub("engagement", overall, "x"),
            ch.HealthSub("cadence", ch.GREEN, "y"),
        ]
        return report

    def test_a_day_is_one_line_and_the_days_are_kept(self):
        from core import channel_health as ch

        with tempfile.TemporaryDirectory() as tmp:
            template = os.path.join(tmp, "health_history_{channel}.jsonl")
            with patch.object(ch, "HISTORY_TEMPLATE", template):
                ch.record_history(self._report(ch.YELLOW), today=date(2026, 10, 21))
                ch.record_history(self._report(ch.RED), today=date(2026, 10, 21))
                ch.record_history(self._report(ch.GREEN), today=date(2026, 10, 22))
                with open(template.format(channel="tapin"), encoding="utf-8") as handle:
                    rows = [json.loads(line) for line in handle if line.strip()]
                lines = ch.history_lines("tapin")
        self.assertEqual([r["date"] for r in rows], ["2026-10-21", "2026-10-22"])
        self.assertEqual(rows[0]["overall"], ch.RED)  # the day's last read wins
        self.assertTrue(lines[0].startswith("10-22 GREEN"))
        self.assertIn("engagement +", lines[0])
        self.assertTrue(lines[1].startswith("10-21 RED"))

    def test_ops_health_records_and_prints_the_history(self):
        import argparse
        import io
        from contextlib import redirect_stdout

        from core import channel_health as ch
        from scripts import ops

        with tempfile.TemporaryDirectory() as tmp:
            template = os.path.join(tmp, "health_history_{channel}.jsonl")
            out = io.StringIO()
            with (
                patch.object(ch, "HISTORY_TEMPLATE", template),
                patch.object(ch, "build_health", return_value=self._report(ch.YELLOW)),
                redirect_stdout(out),
            ):
                ops.COMMANDS["health"][1](argparse.Namespace(channel="tapin", history=True))
            self.assertTrue(os.path.isfile(template.format(channel="tapin")))
        self.assertIn("History (one line a day)", out.getvalue())
        self.assertIn("YELLOW", out.getvalue())


def _studio_service(snippets):
    service = MagicMock()

    def _list(part, id, maxResults):
        call = MagicMock()
        call.execute.return_value = {
            "items": [
                {"id": vid, "status": {"privacyStatus": "public"}, "snippet": snippets[vid]}
                for vid in id.split(",")
                if vid in snippets
            ]
        }
        call.part = part
        return call

    service.videos.return_value.list.side_effect = _list
    return service


class StudioReadBackTests(unittest.TestCase):
    """#1390: a title or description edited in Studio reaches the record."""

    def _sync(self, snippets, runs):
        from analytics import privacy_sync

        rows = [
            SimpleNamespace(id=i, youtube_video_id=vid, privacy_status="public", content_run_id=i,
                            metrics_json="{}")
            for i, vid in enumerate(snippets, start=1)
        ]  # fmt: skip
        run_updates: list[tuple[int, dict]] = []
        merged: list[tuple[int, dict]] = []
        log = SimpleNamespace(list_uploaded_for_channel=lambda c: rows, update=lambda *a: None)
        run_repo = SimpleNamespace(get=lambda rid: runs.get(rid),
                                   update=lambda rid, data: run_updates.append((rid, data)))  # fmt: skip
        service = _studio_service(snippets)
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch(
                "core.run_features.merge_features", side_effect=lambda r, d: merged.append((r, d))
            ),
            patch("apis.youtube_quota.record_usage") as spent,
        ):
            report = privacy_sync.sync_privacy("tapin", service=service)
        parts = {c.kwargs.get("part") for c in service.videos.return_value.list.call_args_list}
        return report, run_updates, merged, spent, parts

    def test_a_studio_edit_is_read_back(self):
        from analytics.privacy_sync import sync_lines

        snippets = {
            "aaa": {"title": "Chargers week 7: three reasons", "description": "new words"},
            "bbb": {"title": "Same title", "description": "same"},
        }
        runs = {
            1: SimpleNamespace(
                id=1, status="published", title="Chargers week 7", description="old"
            ),
            2: SimpleNamespace(id=2, status="published", title="Same title", description="same"),
        }
        report, run_updates, merged, spent, parts = self._sync(snippets, runs)
        self.assertEqual(parts, {"status,snippet"})
        self.assertEqual(spent.call_count, 1)  # still one unit per 50 videos
        self.assertEqual([e["run_id"] for e in report["edited"]], [1])
        self.assertIn(
            (1, {"title": "Chargers week 7: three reasons", "description": "new words"}),
            run_updates,
        )
        self.assertEqual(merged[0][1]["title_uploaded"], "Chargers week 7")
        self.assertIn("edited in Studio", " ".join(sync_lines(report)))

    def test_what_the_upload_adds_is_not_an_edit(self):
        from analytics.privacy_sync import studio_edits

        run = SimpleNamespace(title="T" * 120, description="Three reasons.\nLine two.")
        live = {
            "title": "T" * 100,  # the upload cuts a title to 100
            "description": "Three reasons.\n\nLine two.\n\nThis video uses AI narration.",
        }
        self.assertEqual(studio_edits(run, live), {})
        self.assertEqual(studio_edits(run, {"title": "", "description": ""}), {})


class ThresholdTests(unittest.TestCase):
    """#1479: one table, one version."""

    def _auth(self, mean):
        from core import channel_health as ch

        runs = [SimpleNamespace(id=i, quality_json="{}") for i in range(5)]
        repo = SimpleNamespace(list_for_channel=lambda c: runs)
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.run_quality.authenticity_gate_value", return_value=mean),
        ):
            return ch._authenticity_sub("tapin")

    def test_the_checks_read_the_table(self):
        from core import channel_health as ch

        self.assertEqual(self._auth(60).status, ch.YELLOW)
        with patch.dict(ch.THRESHOLDS, {"authenticity_yellow_under": 58}):
            self.assertEqual(self._auth(60).status, ch.GREEN)
        self.assertIsInstance(ch.THRESHOLDS_VERSION, int)

    def test_the_history_carries_the_version(self):
        from core import channel_health as ch

        with tempfile.TemporaryDirectory() as tmp:
            template = os.path.join(tmp, "health_history_{channel}.jsonl")
            report = ch.HealthReport(channel_id="tapin", overall=ch.GREEN)
            report.subs = [ch.HealthSub("cadence", ch.GREEN, "y")]
            with patch.object(ch, "HISTORY_TEMPLATE", template):
                ch.record_history(report, today=date(2026, 10, 21))
                with patch.object(ch, "THRESHOLDS_VERSION", ch.THRESHOLDS_VERSION + 1):
                    ch.record_history(report, today=date(2026, 10, 22))
                with open(template.format(channel="tapin"), encoding="utf-8") as handle:
                    rows = [json.loads(line) for line in handle]
                lines = ch.history_lines("tapin")
        self.assertEqual(rows[0]["thresholds"], ch.THRESHOLDS_VERSION)
        self.assertIn(f"thresholds v{ch.THRESHOLDS_VERSION + 1}", lines[0])
        self.assertNotIn("thresholds", lines[1])


class SpendCostTests(unittest.TestCase):
    """#1478: the spend entered with `ops spend`, when there is any."""

    def _cost(self, revenue, spent):
        from core import channel_health as ch
        from core.unit_economics import ChannelEconomics, VideoEconomics

        econ = ChannelEconomics(channel_id="tapin")
        econ.videos = [
            VideoEconomics(run_id=i, title="t", cost_usd=0.05, revenue_usd=revenue, views=300,
                           engaged_rate=0.4)
            for i in range(1, 5)
        ]  # fmt: skip
        with (
            patch("core.unit_economics.channel_economics", return_value=econ),
            patch("core.money.ledger.total_spent", return_value=spent),
            patch.object(ch, "_uploaded_videos", return_value=40),
        ):
            return ch._cost_sub("tapin")

    def test_the_entered_spend_is_the_cost(self):
        from core import channel_health as ch

        sub = self._cost(None, {"total": 54.0, "by_kind": {}, "count": 2})
        self.assertIn("$1.35/video from the spend you entered", sub.detail)
        self.assertIn("API estimate $0.050/video", sub.detail)
        self.assertIn("ops spend", sub.source)
        self.assertEqual(sub.status, ch.YELLOW)
        self.assertEqual(self._cost(2.0, {"total": 54.0, "by_kind": {}, "count": 2}).status,
                         ch.GREEN)  # fmt: skip
        loss = self._cost(0.5, {"total": 54.0, "by_kind": {}, "count": 2})
        self.assertEqual(loss.status, ch.RED)
        self.assertIn("the spend you entered", loss.detail)

    def test_with_nothing_entered_it_says_it_is_the_estimate(self):
        sub = self._cost(None, {"total": 0.0, "by_kind": {}, "count": 0})
        self.assertIn("API estimate", sub.detail)
        self.assertIn("ops spend add", sub.detail)


class AbbreviationTests(unittest.TestCase):
    """#1487: NE is New England - where a topic reads as a game."""

    def test_the_leagues(self):
        from apis.nba_teams import team_names_in as nba
        from apis.nfl_entities import team_names_in as nfl

        self.assertEqual(nfl("NE vs BUF week 7"), ["New England Patriots", "Buffalo Bills"])
        self.assertEqual(nfl("Can NE win the AFC East?"), ["New England Patriots"])
        self.assertEqual(nfl("DEN vs KC"), ["Denver Broncos", "Kansas City Chiefs"])
        self.assertEqual(nba("LAL at BOS"), ["Los Angeles Lakers", "Boston Celtics"])
        # an abbreviation both leagues use waits for the league's own word
        self.assertEqual(nba("DAL vs PHI week 7"), [])
        self.assertEqual(nba("DAL vs PHI NBA tonight"), ["Dallas Mavericks", "Philadelphia 76ers"])

    def test_words_in_capitals_are_words(self):
        from apis.nfl_entities import team_names_in as nfl

        self.assertEqual(nfl("NO WAY the Bills win"), ["Buffalo Bills"])
        self.assertEqual(nfl("32 GB vs 16 GB"), [])
        self.assertEqual(nfl("TOP TEN QBs of the season"), [])
        self.assertEqual(nfl("NE VS BUF WEEK 7"), [])  # an all-caps headline

    def test_the_research_and_search_names(self):
        from apis.topic_tokens import subject_terms
        from core.facts.entity_lookup import names_for

        self.assertEqual(names_for("NE vs BUF week 7"), ["Buffalo Bills", "New England Patriots"])
        self.assertEqual(names_for("NE Patriots trade deadline"), ["New England Patriots"])
        self.assertEqual(names_for("Drake Maye NE comeback"), ["Drake Maye"])
        self.assertEqual(
            subject_terms("KC Chiefs at LV"), ["Kansas City Chiefs", "Las Vegas Raiders"]
        )


FAULT = """16:32:12 [INFO] Rendering run 156
Windows fatal exception: code 0xc0000374

Thread 0x00002a1c (most recent call first):
  File "C:\\Python311\\Lib\\threading.py", line 324 in wait
  File "C:\\Python311\\Lib\\threading.py", line 600 in wait

Current thread 0x000035e4 (most recent call first):
  File "C:\\dev\\content_machine\\video\\render.py", line 412 in _encode
  File "C:\\dev\\content_machine\\video\\render.py", line 200 in render
  File "C:\\dev\\content_machine\\scripts\\ops.py", line 4500 in <module>
"""
LIBRARY_TOP = """Fatal Python error: Aborted

Current thread 0x000035e4 (most recent call first):
  File "C:\\venv\\Lib\\site-packages\\PIL\\Image.py", line 3100 in open
  File "C:\\dev\\content_machine\\video\\thumbs.py", line 77 in frame
"""
TRACEBACK = """Traceback (most recent call last):
  File "C:\\dev\\content_machine\\scripts\\ops.py", line 4500, in <module>
    main()
  File "C:\\dev\\content_machine\\video\\compose.py", line 88, in compose
    clip = build(frames)
MemoryError
"""


class CrashLineTests(unittest.TestCase):
    """#1469: the morning names the Python line the crash was at."""

    def test_the_frame(self):
        from core.nightly_task import crash_frame

        self.assertEqual(crash_frame(FAULT), "video/render.py line 412 in _encode")
        self.assertEqual(
            crash_frame(LIBRARY_TOP),
            "PIL/Image.py line 3100 in open, called from video/thumbs.py line 77 in frame",
        )
        self.assertEqual(
            crash_frame(TRACEBACK), "MemoryError at video/compose.py line 88 in compose"
        )
        self.assertEqual(crash_frame("16:32:13 [WARNING] Quote attribution: 1 lacks a source"), "")

    def test_the_morning_line_reads_the_log(self):
        from datetime import datetime

        from core import nightly_task
        from tests.test_stops_and_facts import CRASHED

        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "overnight-last.log")
            with open(log, "w", encoding="utf-8") as handle:
                handle.write(FAULT)
            died = datetime(2026, 10, 16, 16, 32, 13).timestamp()
            os.utime(log, (died, died))
            with (
                patch.dict(os.environ, {"OVERNIGHT_RECORD_FILE": os.path.join(tmp, "r.json")}),
                patch.object(
                    nightly_task, "_queried_times", return_value=nightly_task.task_times(CRASHED)
                ),
            ):
                line = nightly_task.overnight_stop_line(root=tmp, log_path=log)
        self.assertIn("heap corruption", line)
        self.assertIn("at video/render.py line 412 in _encode", line)


class BrokenTeamNameTests(unittest.TestCase):
    """#1486: the title check, every league - and a full name does not hide a broken one."""

    def test_a_full_name_does_not_hide_a_broken_one(self):
        from core.title_generator import broken_place_name

        self.assertEqual(
            broken_place_name("New England Patriots fans meet England Patriots"),
            "New England Patriots",
        )
        self.assertEqual(broken_place_name("New England Patriots fans meet the Patriots"), "")


if __name__ == "__main__":
    unittest.main()
