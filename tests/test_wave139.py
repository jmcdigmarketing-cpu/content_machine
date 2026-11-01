"""Wave 139 (2026-11-01, decision 91): the 22 shortfalls measure themselves.

`ops shortfalls` printed each shortfall's "done when" and never ran it, so the Story's "Where it falls
short" kept all 22 lines from 10-18 while half were done. Each check now reads its own number; the
plan closes what passes; overnight keeps the nights it ran (S07's new check); the backlog sweep
brings S22 under its ceiling, and a test holds it there.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)


class CommandTests(unittest.TestCase):
    def test_each_check_is_run_and_its_number_printed(self):
        from core import roadmap_index
        from core.success import shortfalls as sf

        got = {key: sf.Reading(sf.NOT_YET, f"{key} number") for key in sf.CHECKS}
        got["S12"] = sf.Reading(sf.MET, "TikTok's average watch 3.86 s")
        got["S14"] = sf.Reading(sf.YOURS, "publish the Google app")
        with patch.object(sf, "readings", return_value=got):
            lines = roadmap_index.shortfall_lines("tapin", now=NOW)
        self.assertIn("each check run: 20 not yet, 1 yours, 1 met", lines[0])
        s12 = lines.index(next(line for line in lines if line.startswith("  S12 ")))
        self.assertIn("MET", lines[s12])
        self.assertIn("3.86 s", lines[s12 + 1])

    def test_a_closed_shortfall_that_fails_again_says_so(self):
        from core import roadmap_index
        from core.success import shortfalls as sf

        got = {key: sf.Reading(sf.MET, "fine") for key in sf.CHECKS}
        got["S17"] = sf.Reading(sf.NOT_YET, "1 overnight crash in 28 days")
        sections = [{"key": "S17", "name": "Overnight crashed", "done_when": "x", "commands": [],
                     "closed": "2026-11-01 - 0 crashes in 28 days"}]  # fmt: skip
        with (
            patch.object(sf, "readings", return_value=got),
            patch.object(roadmap_index, "sections", return_value=sections),
        ):
            lines = roadmap_index.shortfall_lines("tapin", now=NOW)
        self.assertIn("the plan closed it (2026-11-01); it no longer passes", lines[1])

    def test_the_plans_closed_line_is_read(self):
        from core.roadmap_index import sections

        text = ("## The 22 shortfalls\n\n### S12 The first second\n\n**Who:** Code. **Done when:** "
                "`py -m scripts.ops growth` - above 3 s.\n\n**Closed:** 2026-11-01 - 3.86 s\n\n"
                "### S13 Volume\n\n**Done when:** 7 a week\n")  # fmt: skip
        found = {s["key"]: s for s in sections(text)}
        self.assertEqual(found["S12"]["closed"], "2026-11-01 - 3.86 s")
        self.assertEqual(found["S12"]["done_when"], "`py -m scripts.ops growth` - above 3 s.")
        self.assertEqual(found["S13"]["closed"], "")

    def test_a_reader_that_fails_reads_no_measure(self):
        from core.success import shortfalls as sf

        def broken(_channel, _now):
            raise ValueError("no store")

        with patch.dict(sf.CHECKS, {"S05": broken}):
            got = sf.reading("S05", "tapin", now=NOW)
        self.assertEqual(got.status, sf.NO_MEASURE)
        self.assertIn("ValueError", got.today)

    def test_every_shortfall_has_a_check(self):
        from core.roadmap_index import sections
        from core.success.shortfalls import CHECKS

        self.assertEqual(sorted(CHECKS), sorted(s["key"] for s in sections()))


def _row(days_ago: float, **extra):
    return SimpleNamespace(privacy_status="public", published_at=NOW - timedelta(days=days_ago),
                           content_run_id=extra.pop("run", 1), metrics_json="{}", **extra)  # fmt: skip


class CheckTests(unittest.TestCase):
    def test_s12_tiktok_watch_and_the_intro(self):
        from core.success import shortfalls as sf

        store = {"rows": {str(i): {"tiktok": {"avg_watch_s": w}} for i, w in enumerate((3.5, 4.2))}}
        with (
            patch("publishing.platform_metrics.load", return_value=store),
            patch("video.channel_intro._intro_enabled", return_value=False),
        ):
            self.assertEqual(sf.reading("S12", "tapin", now=NOW).status, sf.MET)
        store = {"rows": {"1": {"tiktok": {"avg_watch_s": 1.4}}}}
        with (
            patch("publishing.platform_metrics.load", return_value=store),
            patch("video.channel_intro._intro_enabled", return_value=False),
        ):
            self.assertEqual(sf.reading("S12", "tapin", now=NOW).status, sf.NOT_YET)

    def test_s13_four_weeks_of_seven(self):
        from core.success import shortfalls as sf

        def rows(per_week):
            return [
                _row(7 * week + 1 + i * 0.1) for week, n in enumerate(per_week) for i in range(n)
            ]

        cases = (([8, 7, 9, 7], sf.MET), ([25, 18, 5, 4], sf.WAITING), ([3, 9, 9, 9], sf.NOT_YET))
        for weeks, status in cases:
            with patch.object(sf, "_public_rows", return_value=rows(weeks)):
                got = sf.reading("S13", "tapin", now=NOW)
            self.assertEqual(got.status, status, (weeks, got.today))
        with patch.object(sf, "_public_rows", return_value=rows([25, 18, 5, 4])):
            self.assertIn("25, 18, 5, 4", sf.reading("S13", "tapin", now=NOW).today)

    def test_s05_verdicts(self):
        from core.success import shortfalls as sf

        for found, status in (((14, 24), sf.NOT_YET), ((17, 22), sf.MET), ((5, 10), sf.WAITING)):
            with patch("core.success.verdicts.agreement", return_value=found):
                self.assertEqual(sf.reading("S05", "tapin", now=NOW).status, status, found)

    def test_s08_the_weeks_claim_holds(self):
        from core.success import shortfalls as sf

        def run(i, held):
            verification = {"claims": [{"claim": "c", "status": "unsupported", "blocking": True}]}
            return SimpleNamespace(
                id=i,
                created_at=NOW - timedelta(days=1),
                features_json=json.dumps(
                    {"claim_verification": verification if held else {"claims": []}}
                ),
            )

        runs = [run(1, True), *(run(i, False) for i in range(2, 9))]
        with patch("core.claim_types.blocking_unsupported", side_effect=lambda v: [
                c["claim"] for c in v.get("claims") or []]):  # fmt: skip
            found = sf.claim_hold_share(runs, now=NOW)
            self.assertEqual((found["checked"], len(found["held"])), (8, 1))
            with patch("storage.repositories.content_runs.get_content_run_repository") as repo:
                repo.return_value.list_for_channel.return_value = runs
                self.assertEqual(sf.reading("S08", "tapin", now=NOW).status, sf.MET)
                repo.return_value.list_for_channel.return_value = runs[:3]
                self.assertEqual(sf.reading("S08", "tapin", now=NOW).status, sf.WAITING)

    def test_s10_a_hand_post_this_week(self):
        from core.success import shortfalls as sf

        recent = (NOW - timedelta(days=2)).isoformat()
        old = (NOW - timedelta(days=12)).isoformat()
        store = {"posts": {"199": {"instagram": {"state": "manual", "at": recent}},
                           "150": {"tiktok": {"state": "manual", "at": old}},
                           "201": {"tiktok": {"state": "sent", "at": recent}}}}  # fmt: skip
        with patch("publishing.crosspost._load", return_value=store):
            got = sf.reading("S10", "tapin", now=NOW)
        self.assertEqual(got.status, sf.NOT_YET)
        self.assertIn("run 199 instagram", got.today)
        with patch(
            "publishing.crosspost._load", return_value={"posts": {"150": store["posts"]["150"]}}
        ):
            self.assertEqual(sf.reading("S10", "tapin", now=NOW).status, sf.MET)

    def test_s14_the_sign_in(self):
        from core.success import shortfalls as sf

        with patch("youtube.oauth.sign_in_mode", return_value="production"):
            self.assertEqual(sf.reading("S14", "tapin", now=NOW).status, sf.MET)
        with (
            patch("youtube.oauth.sign_in_mode", return_value="testing"),
            patch("youtube.oauth.sign_in_expiry", return_value=datetime(2026, 11, 6, 1, 0)),
        ):
            got = sf.reading("S14", "tapin", now=NOW)
        self.assertEqual(got.status, sf.YOURS)
        self.assertIn("Nov 06", got.today)

    def test_s21_and_s22(self):
        from core.success import shortfalls as sf

        self.assertEqual(sf.reading("S21", "tapin", now=NOW).status, sf.MET)  # the weight is 0
        with patch("core.roadmap_index.counts", return_value={"open_total": 337}):
            self.assertEqual(sf.reading("S22", "tapin", now=NOW).status, sf.NOT_YET)
        with patch("core.roadmap_index.counts", return_value={"open_total": 300}):
            self.assertEqual(sf.reading("S22", "tapin", now=NOW).status, sf.MET)

    def test_s17_crashes_read_in_local_time(self):
        from core.success import shortfalls as sf

        seen = {}

        def count(**kw):
            seen.update(kw)
            return 0

        with patch("core.nightly_task.crash_count", side_effect=count):
            self.assertEqual(sf.reading("S17", "tapin", now=NOW).status, sf.MET)
        self.assertIsNone(seen["now"].tzinfo)
        self.assertEqual(seen["days"], 28)


class FalseHandPostTests(unittest.TestCase):
    """S10's first run found it: the round's own post for run 203 was taken as a "hand post" of runs
    204 and 205 (same story), so neither was crossposted - 8 such in a week."""

    STORE: ClassVar[dict] = {"posts": {
        "203": {"title": "UFC 333 report", "tiktok": {"state": "sent", "post_id": "P203"}},
        "204": {"title": "UFC 333 decline", "tiktok": {"state": "manual", "post_id": "P203",
                                                       "at": "2026-10-31T02:00:00+00:00"}},
        "216": {"title": "GTA 6: 20 days to launch", "tiktok": {"state": "sent", "post_id": "P216"}},
        "220": {"title": "GTA 6: 19 days to launch - x", "tiktok": {
            "state": "manual", "post_id": "P216", "at": "2026-10-31T22:00:00+00:00"}},
        "150": {"title": "old", "instagram": {"state": "manual", "post_id": "H150"}},
    }}  # fmt: skip

    def test_a_post_recorded_for_another_run_is_not_a_hand_post(self):
        from publishing.crosspost import _hand_post, _taken_post_ids

        posts = [{"id": "P203", "text": "UFC 333 Volkanovski decline report cracks", "sentAt": ""}]
        text = "UFC 333 Volkanovski decline report cracks and more"
        self.assertEqual(_hand_post(posts, text, None)["id"], "P203")  # as before, untaken
        taken = _taken_post_ids(self.STORE["posts"], 204)
        self.assertIn("P203", taken)
        self.assertNotIn("H150", _taken_post_ids(self.STORE["posts"], 150))
        self.assertIsNone(_hand_post(posts, text, None, taken))

    def test_the_round_passes_what_is_taken(self):
        import inspect

        from publishing import crosspost

        self.assertIn("_taken_post_ids(posts, run_id)", inspect.getsource(crosspost.send_due))

    def test_false_hand_posts_are_found(self):
        from publishing import crosspost

        with patch.object(crosspost, "_load", return_value=json.loads(json.dumps(self.STORE))):
            found = crosspost.false_hand_posts("tapin")
        self.assertEqual([(x["run_id"], x["owner"]) for x in found], [(204, 203), (220, 216)])

    def test_unclaim_clears_the_recent_and_leaves_the_countdown_and_the_old(self):
        from publishing import crosspost

        data = json.loads(json.dumps(self.STORE))
        data["posts"]["208"] = {
            "title": "Kane's 61-goal peak",
            "instagram": {"state": "manual", "post_id": "P203", "at": "2026-10-31T02:00:00+00:00"},
        }
        public = {204: NOW - timedelta(days=4), 220: NOW - timedelta(days=1),
                  208: NOW - timedelta(days=1)}  # fmt: skip
        saved = {}
        with (
            patch.object(crosspost, "_load", return_value=data),
            patch.object(crosspost, "_save", side_effect=lambda ch, d: saved.update(d)),
            patch.object(crosspost, "_public_times", return_value=public),
        ):
            dry = crosspost.unclaim("tapin", now=NOW)
            self.assertFalse(saved)
            lines = crosspost.unclaim("tapin", apply=True, now=NOW)
        text = "\n".join(lines)
        self.assertIn("run 208 Instagram: was taken for run 203's own post - cleared", text)
        self.assertIn("run 220 TikTok: left - a countdown Short", text)
        self.assertIn("run 204 TikTok: left - public over 3 days ago", text)
        self.assertNotIn("instagram", saved["posts"]["208"])
        self.assertEqual(saved["posts"]["204"]["tiktok"]["state"], "manual")
        self.assertIn("would be cleared", "\n".join(dry))

    def test_s10_names_the_missed_posts(self):
        from core.success import shortfalls as sf

        with patch("publishing.crosspost._load", return_value=json.loads(json.dumps(self.STORE))):
            got = sf.reading("S10", "tapin", now=NOW)
        self.assertEqual(got.status, sf.NOT_YET)
        self.assertIn("2 crossposts in 7 days never went", got.today)
        self.assertIn("0 made by hand", got.today)


class NightsTests(unittest.TestCase):
    """S07's new check: overnight ran every night (decision 69 - at 5:00 or at power-on)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.dict(os.environ, {"OVERNIGHT_RECORD_FILE": os.path.join(self.tmp.name, "o.json")})
        p.start()
        self.addCleanup(p.stop)

    def test_the_record_keeps_the_nights(self):
        from core.nightly_task import KEEP_NIGHTS, record_overnight, recorded_nights

        start = datetime(2026, 10, 1, 5, 0)
        for i in range(20):
            record_overnight("tapin", started=start + timedelta(days=i))
            record_overnight("tapin", started=start + timedelta(days=i),
                             finished=start + timedelta(days=i, minutes=12), drafts=4)  # fmt: skip
        nights = recorded_nights()
        self.assertEqual(len(nights), KEEP_NIGHTS)
        self.assertEqual(nights[-1], date(2026, 10, 20))

    def test_an_old_record_gives_its_one_night(self):
        from core.nightly_task import overnight_record_path, recorded_nights

        with open(overnight_record_path(), "w", encoding="utf-8") as f:
            json.dump({"channel": "tapin", "started": "2026-10-31T05:00:01"}, f)
        self.assertEqual(recorded_nights(), [date(2026, 10, 31)])

    def test_s07_reads_them(self):
        from core.success import shortfalls as sf

        week = [NOW.date() - timedelta(days=i) for i in range(7)]
        with patch("core.nightly_task.recorded_nights", return_value=sorted(week)):
            self.assertEqual(sf.reading("S07", "tapin", now=NOW).status, sf.MET)
        with patch("core.nightly_task.recorded_nights", return_value=sorted(week[:2])):
            self.assertEqual(sf.reading("S07", "tapin", now=NOW).status, sf.WAITING)
        gap = sorted([NOW.date() - timedelta(days=i) for i in (0, 1, 3, 4, 5, 6, 9)])
        with patch("core.nightly_task.recorded_nights", return_value=gap):
            got = sf.reading("S07", "tapin", now=NOW)
        self.assertEqual(got.status, sf.NOT_YET)
        self.assertIn("6 of the last 7", got.today)


class PlanTests(unittest.TestCase):
    def test_s07s_check_is_every_night(self):
        from core.roadmap_index import sections

        s07 = next(s for s in sections() if s["key"] == "S07")
        self.assertIn("every night", s07["done_when"])
        self.assertNotIn("05:0x", s07["done_when"])

    def test_the_closed_shortfalls_are_marked_in_the_plan(self):
        from core.roadmap_index import sections

        closed = {s["key"] for s in sections() if s["closed"]}
        # measured 2026-11-01: 7 met, 2 built (S04, S18)
        self.assertEqual(closed, {"S04", "S08", "S12", "S16", "S17", "S18", "S19", "S20", "S21"})

    def test_the_backlog_stays_under_its_ceiling(self):
        from core.roadmap_index import counts
        from core.success.shortfalls import BACKLOG_CEILING

        self.assertLessEqual(int(counts()["open_total"]), BACKLOG_CEILING)  # S22, decision 68


if __name__ == "__main__":
    unittest.main()
