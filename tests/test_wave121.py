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


if __name__ == "__main__":
    unittest.main()
