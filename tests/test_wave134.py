"""Wave 134 (2026-10-28) - the operator's new backgrounds, and the bridge's scoreboard.

The operator: "I have also updated our background selection." 19 YouTube downloads ("Free To Use /
No Copyright Gameplay") went into video/backgrounds; all were recorded as owned, and Call of Duty,
Black Ops and Counter-Strike topics reached none of the new folders. Then wave 134's first five:
#1823 the YPP bars as data, #1824 engaged Shorts views, #1697 organic subscribers, #1825 the race
clock, #1822 the scoreboard (decision 86: the subscriber count is "at most" until the campaigns'
numbers are final).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

FOLDERS = ["lib/gaming/multiplayer games/COD", "lib/gaming/multiplayer games/CSGO",
           "lib/gaming/solo games/Call of Duty Black Ops 3", "lib/gaming/open world/GTA V",
           "lib/gaming/multiplayer games/Fortnite"]  # fmt: skip


class FootageAliasTests(unittest.TestCase):
    """Call of Duty: Modern Warfare 4 (the 325-view Short's subject) reached no folder."""

    def _pick(self, topic):
        from assets.local_provider import choose_footage

        return choose_footage(topic, FOLDERS, "tapin", use_llm=False)

    def test_the_three_topics_reach_their_folders(self):
        self.assertEqual(
            self._pick("Call Of Duty: Modern Warfare 4's First DLC Is Out Now")[0], FOLDERS[0]
        )
        self.assertEqual(self._pick("Counter-Strike 2 major results")[0], FOLDERS[1])
        self.assertEqual(self._pick("Black Ops 3 zombies maps return")[0], FOLDERS[2])

    def test_the_playlist_path_and_the_plain_words_are_unchanged(self):
        self.assertEqual(self._pick("GTA 6: 21 days to launch")[0], FOLDERS[3])
        self.assertIsNone(self._pick("Black Friday deals on headphones")[0])

    def test_the_aliases_are_their_own_file(self):
        from assets.local_provider import footage_aliases

        rows = footage_aliases("tapin")
        self.assertEqual(rows[0]["folder"], "Call of Duty Black Ops 3")  # most specific first
        self.assertIn("call of duty", [k for r in rows for k in r["keys"]])


class DownloadLicenceTests(unittest.TestCase):
    """The operator: "Credit generically" - a downloaded clip is third party, credited."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        with open(os.path.join(root, "license.yaml"), "w", encoding="utf-8") as handle:
            json.dump({"owner": "TapIn Media", "license": "owned", "commercial_use": True}, handle)
        self.folder = os.path.join(root, "gaming", "multiplayer games", "COD")
        os.makedirs(self.folder)
        patcher = patch("assets.local_provider.BASE_VIDEO_DIR", root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _clip(self, name):
        path = os.path.join(self.folder, name)
        open(path, "wb").close()
        return path

    def test_a_download_is_credited(self):
        from assets.local_provider import clip_credit

        clip = self._clip(
            "Clipto AI video downloader_MW4 DMZ No Copyright Gameplay _ Free to Use.mp4"
        )
        line = clip_credit(clip)
        self.assertIsNotNone(line)
        self.assertTrue(line.startswith("COD gameplay: "))
        self.assertIn("YouTube", line)

    def test_a_capture_stays_owned(self):
        from assets.local_provider import clip_credit

        self.assertIsNone(clip_credit(self._clip("fortnite-2026-08-27-10-59-51-08-win.mp4")))

    def test_a_clips_own_licence_wins(self):
        from assets.local_provider import clip_credit

        clip = self._clip("Clipto AI video downloader_Mine No Copyright.mp4")
        with open(os.path.splitext(clip)[0] + ".license.yaml", "w", encoding="utf-8") as handle:
            json.dump({"owner": "TapIn Media", "license": "owned"}, handle)
        self.assertIsNone(clip_credit(clip))

    def test_the_names_that_mark_a_download(self):
        from assets.local_provider import looks_downloaded

        for name in (
            "Clipto AI video downloader_x.mp4",
            "GTA 5 Gameplay - Free To Use.mp4",
            "Pokemon No Copyright Gameplay.mp4",
            "Minecraft Parkour copyright free.mp4",
        ):
            self.assertTrue(looks_downloaded(name), name)  # fmt: skip
        self.assertFalse(looks_downloaded("GTA V 2026-08-27 race.mp4"))

    def test_ops_footage_says_how_many(self):
        import inspect

        from assets import footage_gaps
        from scripts import ops

        source = inspect.getsource(ops) + inspect.getsource(footage_gaps)
        self.assertIn("downloaded_clips(", source)


BARS = {"bars": [
    {"from": "2023-06-13", "subscribers": 1000, "hours": 4000, "shorts": 10000000,
     "source": "YouTube Help"},
    {"from": "2027-02-01", "subscribers": 1000, "hours": 8000, "shorts": 20000000,
     "source": "third-party reports, 2026-08; not yet on YouTube's help page"},
]}  # fmt: skip


class BarTests(unittest.TestCase):
    """#1823 (B10.2): the bar reportedly doubles on 2027-02-01 - as data, with its source."""

    def test_the_three_dates(self):
        from core.success.bridge import bar_on

        self.assertEqual(
            (bar_on("2026-10-28")["hours"], bar_on("2026-10-28")["shorts"]), (4000, 10000000)
        )
        self.assertEqual(bar_on("2027-02-01")["hours"], 8000)
        self.assertEqual(bar_on("2027-03-01")["shorts"], 20000000)

    def test_the_report_names_the_next_bar_and_its_source(self):
        from core.success.bridge import bar_lines

        text = "\n".join(bar_lines(date(2026, 10, 28)))
        self.assertIn("4,000", text)
        self.assertIn("2027-02-01", text)
        self.assertIn("third-party reports", text)
        later = bar_lines(date(2027, 3, 1))  # no bar after the new one
        self.assertFalse(any(line.startswith("From ") for line in later))
        self.assertIn("8,000", later[0])


def _service(rows_by_metric, refuse=()):
    service = MagicMock()

    def query(**kwargs):
        metric = kwargs["metrics"]
        req = MagicMock()
        if metric in refuse:
            req.execute.side_effect = RuntimeError("HttpError 400: unknown metric")
        else:
            req.execute.return_value = {
                "columnHeaders": [{"name": "insightTrafficSourceType"},
                                  {"name": "creatorContentType"}, {"name": metric}],
                "rows": rows_by_metric.get(metric, []),
            }  # fmt: skip
        return req

    service.reports.return_value.query.side_effect = query
    return service


ENGAGED = [["YT_SHORTS", "SHORTS", 1500], ["ADVERTISING", "SHORTS", 900],
           ["YT_SEARCH", "VIDEO_ON_DEMAND", 40]]  # fmt: skip


class EngagedViewTests(unittest.TestCase):
    """#1824 (B10.3): the Shorts path counts engaged views; nothing asked for them."""

    def _numbers(self, refuse=()):
        from analytics import youtube_metrics

        service = _service({"views": ENGAGED, "engagedViews": ENGAGED,
                            "estimatedMinutesWatched": []}, refuse=refuse)  # fmt: skip
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch.object(youtube_metrics, "_subscriber_count", return_value=195),
            patch.object(youtube_metrics, "_subscriber_change", return_value=None),
        ):
            return youtube_metrics.fetch_ypp_numbers(channel_id="tapin", today=date(2026, 10, 28))

    def test_organic_engaged_views(self):
        self.assertEqual(self._numbers()["shorts_engaged_90d"], 1500)

    def test_a_refused_metric_is_absent_not_zero(self):
        numbers = self._numbers(refuse=("engagedViews",))
        self.assertNotIn("shorts_engaged_90d", numbers)
        self.assertEqual(numbers["shorts_views_90d"], 1500)


class OrganicSubscriberTests(unittest.TestCase):
    """#1697 (B05.1): ad subscribers do not count toward YPP (Google's Promote help page)."""

    def test_at_most_while_a_count_is_missing(self):
        from core.success.bridge import organic_line

        entries = [{"kind": "ads", "result": {"subscribers": 27, "final": True}},
                   {"kind": "ads", "result": {"subscribers": 2, "final": True}},
                   {"kind": "ads"}, {"kind": "subscription"}]  # fmt: skip
        line = organic_line(134, entries)
        self.assertIn("at most 105", line)
        self.assertIn("YouTube 134", line)

    def test_final_counts_drop_the_at_most(self):
        from core.success.bridge import organic_line

        entries = [{"kind": "ads", "result": {"subscribers": 27, "final": True}},
                   {"kind": "ads", "result": {"subscribers": 2, "final": True}}]  # fmt: skip
        line = organic_line(134, entries)
        self.assertIn("organic subscribers 105", line)
        self.assertNotIn("at most", line)

    def test_a_count_to_date_is_not_final(self):
        # Decision 86: 134 -> 195 in a day with both campaigns "ended" - counts to date.
        from core.success.bridge import organic_line

        line = organic_line(195, [{"kind": "ads", "result": {"subscribers": 27}}])
        self.assertIn("at most 168", line)
        self.assertIn("not final", line)

    def test_no_count_is_not_measured(self):
        from core.success.bridge import organic_line

        self.assertIn("not measured", organic_line(None, []))

    def test_the_ledger_records_a_final_count(self):
        from core.money import ledger

        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "spend_ledger.json")
            with open(store, "w", encoding="utf-8") as handle:
                json.dump({"entries": [{"id": 2, "kind": "ads", "amount": 14.55,
                                        "date": "2026-10-26",
                                        "result": {"subscribers": 27}}]}, handle)  # fmt: skip
            with patch.object(ledger, "LEDGER_FILE", store):
                row = ledger.set_result(2, final=True)
        self.assertEqual(row["result"], {**row["result"], "subscribers": 27, "final": True})


NUMBERS = {"as_of": "2026-10-28", "shorts_views_90d": 3852, "shorts_views_28d": 2817,
           "long_hours_365d": 10.2, "subscribers": 134, "subs_net_28d": 133}  # fmt: skip


class RaceClockTests(unittest.TestCase):
    """#1825 (B10.4): the days to 2027-02-01 and what each path needs a day."""

    def test_the_briefs_fixture(self):
        from core.success.bridge import race_clock

        clock = race_clock(NUMBERS, today=date(2026, 10, 28))
        self.assertEqual(clock["days_left"], 96)
        self.assertEqual(clock["shorts"]["need_now"], 111068)
        self.assertEqual(clock["shorts"]["pace"], 101)
        self.assertEqual(clock["shorts"]["need_new"], 222179)
        line = "\n".join(clock["lines"])
        self.assertIn("96 days", line)
        self.assertIn("not reachable at this pace", line)


class ScoreboardTests(unittest.TestCase):
    """#1822 (B10.1): four numbers, each with its pace - "not measured", never 0."""

    def test_four_rows_and_the_clock(self):
        from core.success.bridge import scoreboard_lines

        entries = [{"kind": "ads", "result": {"subscribers": 27, "final": True}}]
        text = "\n".join(scoreboard_lines("tapin", numbers=NUMBERS, entries=entries,
                                          today=date(2026, 10, 28)))  # fmt: skip
        self.assertIn("organic subscribers 107", text)
        self.assertIn("engaged Shorts views (90 days): not measured", text)
        self.assertIn("long-form hours (365 days): 10.2", text)
        self.assertIn("money outside YouTube: not tracked yet", text)
        self.assertIn("96 days", text)

    def test_no_numbers_says_so(self):
        from core.success.bridge import scoreboard_lines

        text = "\n".join(
            scoreboard_lines("tapin", numbers={}, entries=[], today=date(2026, 10, 28))
        )
        self.assertNotIn(": 0", text)
        self.assertIn("not measured", text)

    def test_it_reaches_status_the_week_and_ops_ypp(self):
        import inspect

        from analytics import weekly_report
        from core import status_summary
        from scripts import ops

        self.assertIn("Bridge", [label for label, _verb, _fn in status_summary.FAMILIES])
        self.assertIn("_bridge_block(", inspect.getsource(weekly_report.format_report))
        self.assertIn("scoreboard_lines(", inspect.getsource(ops.cmd_ypp))

    def test_the_status_line(self):
        from core.success.bridge import status_line

        line = status_line("tapin", numbers=NUMBERS, entries=[], today=date(2026, 10, 28))
        self.assertTrue(line.startswith("Bridge: "))
        self.assertIn("96 days", line)


if __name__ == "__main__":
    unittest.main()
