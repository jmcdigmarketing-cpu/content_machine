"""Wave 80: the drafts line, the week on the header, a parked channel, competitor searches.

- #1132: 69 runs had stopped at a draft and no line said any were waiting.
- #1133: the header had no count of the week's uploads against the operator's 3-5.
- #1134: MoneyWise is parked (operator, 2026-10-11); it had made no video and its dead finance
  feed was failing `ops doctor` for the channel that is worked.
- #1127: "NFL news" returned the league's own channel and four soccer channels.
- Run 116's draft was titled "Contrarian: ..." - a label a person would fix.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

UC_A = "UC" + "a" * 22
UC_B = "UC" + "b" * 22


class _DraftsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _draft(self, run_id, **over):
        meta = {
            "run_id": run_id,
            "channel_id": "tapin",
            "topic": f"Topic {run_id}",
            "title": f"Title {run_id}",
            "hook_score": 70,
            "hook_verdict": "strong",
            "authenticity_verdict": "ok",
            "claim_verification": {},
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        meta.update(over)
        folder = os.path.join(self.tmp.name, f"draft_{run_id:04d}")
        os.makedirs(folder)
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as fh:
            fh.write("# Draft\n\n## Script\n\nA script.\n")


class DraftsLineTests(_DraftsCase):
    def test_a_title_that_starts_with_a_label_waits_for_a_person(self):
        from core.batch_review import pending_drafts, unattended_block_reason

        self._draft(116, title="Contrarian: Spain's World Cup win exposes overreliance on Rodri")
        self._draft(117, title="Spain's World Cup win exposes an overreliance on Rodri")
        first, second = pending_drafts("tapin", root=self.tmp.name)
        self.assertEqual(
            unattended_block_reason(first), 'its title starts with a label ("Contrarian:")'
        )
        self.assertEqual(unattended_block_reason(second), "")

    def test_the_line_splits_what_overnight_takes_from_what_needs_a_person(self):
        from core import batch_review

        self._draft(1)
        self._draft(2)
        self._draft(3, authenticity_verdict="review")
        self._draft(4, created_at="2026-01-01T00:00:00")
        with patch.object(batch_review, "unattended_limit", return_value=2):
            line = batch_review.drafts_line("tapin", root=self.tmp.name)
        self.assertEqual(
            line,
            "Drafts waiting: 4 - 2 could render overnight (2 a night), 1 need you, "
            "1 past their window: py -m scripts.ops batch-review --channel tapin",
        )

    def test_no_drafts_is_no_line(self):
        from core.batch_review import drafts_line

        self.assertEqual(drafts_line("tapin", root=self.tmp.name), "")

    def test_ops_status_carries_it(self):
        from core.status import build_status_lines

        with patch("core.batch_review.drafts_line", return_value="Drafts waiting: 4 - 1 need you"):
            self.assertIn("Drafts waiting: 4 - 1 need you", build_status_lines("tapin"))


class WeekOnTheHeaderTests(unittest.TestCase):
    def _week(self, recent, upcoming, cap=5, target=3):
        from core import status
        from core.cadence import CadenceStatus

        cadence = CadenceStatus(recent=recent, upcoming=upcoming, cap=cap, window_days=7)
        with (
            patch("core.cadence.cadence_status", return_value=cadence),
            patch("core.cadence.weekly_target", return_value=target),
        ):
            return status._hdr_week("tapin")

    def test_the_week_counts_uploads_and_scheduled_against_the_band(self):
        self.assertEqual(self._week(1, 1), "week 2 of 3-5")

    def test_a_target_at_the_cap_is_one_number(self):
        self.assertEqual(self._week(5, 0, target=5), "week 5 of 5")

    def test_the_header_carries_it(self):
        from core import status

        with (
            patch.object(status, "_hdr_name", return_value="TapIn"),
            patch.object(status, "_hdr_sign_in", return_value=""),
            patch.object(status, "_hdr_spent", return_value=""),
            patch.object(status, "_hdr_uploads", return_value=""),
            patch.object(status, "_hdr_queue", return_value=""),
            patch.object(status, "_hdr_last", return_value=""),
            patch.object(status, "_hdr_week", return_value="week 2 of 3-5"),
            patch.object(status, "_hdr_shelf", return_value=""),
        ):
            self.assertEqual(status.header_line("tapin"), "TapIn · week 2 of 3-5")


class ParkedChannelTests(unittest.TestCase):
    def test_moneywise_is_parked_and_tapin_is_not(self):
        from config.channels import active_channel_ids, get_channel_profile, parked_channel_ids

        self.assertTrue(get_channel_profile("moneywise").parked)
        self.assertFalse(get_channel_profile("tapin").parked)
        self.assertEqual(parked_channel_ids(), ["moneywise"])
        self.assertIn("tapin", active_channel_ids())
        self.assertNotIn("moneywise", active_channel_ids())

    def test_only_a_parked_channels_own_feeds_are_set_aside(self):
        from config.channels import parked_feed_scopes

        scopes = parked_feed_scopes()
        self.assertIn("seo:moneywise", scopes)
        self.assertIn("domain:finance", scopes)
        self.assertNotIn("domain:gaming", scopes)
        self.assertNotIn("domain:soccer", scopes)
        self.assertNotIn("global", scopes)

    def test_the_doctor_no_longer_fails_on_a_parked_channels_feed(self):
        from core import feed_health

        rows = [
            {
                "url": "https://a",
                "scope": "domain:finance",
                "name": "Yahoo Finance",
                "status": feed_health.STATUS_DEAD,
                "detail": "HTTP 404",
            },
            {
                "url": "https://b",
                "scope": "domain:gaming",
                "name": "Game Feed",
                "status": feed_health.STATUS_DEAD,
                "detail": "HTTP 500",
            },
        ]
        feeds = [{"url": r["url"], "scope": r["scope"], "name": r["name"]} for r in rows]
        with (
            patch.object(feed_health, "load_results", return_value={"results": rows}),
            patch.object(feed_health, "iter_configured_feeds", return_value=feeds),
        ):
            text = " ".join(feed_health.cached_warnings())
        self.assertNotIn("Yahoo Finance", text)
        self.assertIn("Game Feed", text)

    def test_the_channel_picker_does_not_offer_it(self):
        from core.ui import prompt_channel_selection

        printed: list[str] = []
        picked = prompt_channel_selection(
            print_fn=lambda *a: printed.append(" ".join(map(str, a))), input_fn=lambda prompt: ""
        )
        text = "\n".join(printed)
        self.assertNotIn("(moneywise)", text)
        self.assertIn("(tapin)", text)
        self.assertIn("Parked, not listed: MoneyWise", text)
        self.assertNotEqual(picked, "moneywise")

    def test_naming_it_still_reaches_it(self):
        from config.channels import resolve_channel_id

        self.assertEqual(resolve_channel_id("moneywise"), "moneywise")


class CompetitorSearchTests(unittest.TestCase):
    def setUp(self):
        import config.competitors as competitors

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for attr in ("COMPETITORS_DIR", "DATA_DIR"):
            patcher = patch.object(competitors, attr, self.tmp.name)
            patcher.start()
            self.addCleanup(patcher.stop)
        competitors.get_competitor_channels.cache_clear()
        self.addCleanup(competitors.get_competitor_channels.cache_clear)
        quota = patch("apis.youtube_quota.record_usage")
        quota.start()
        self.addCleanup(quota.stop)

    def test_each_search_carries_its_niches_own_words(self):
        from analytics.competitor_list import niche_keys

        keys = niche_keys("tapin")
        self.assertIn("nfl", keys["NFL news"])
        self.assertIn("ufc", keys["UFC news"])
        self.assertIn("gaming", keys["gaming news"])

    def test_a_word_must_stand_alone(self):
        from analytics.competitor_list import on_niche

        self.assertTrue(on_niche("HangTime NFL - new NFL videos every day", ["nfl", "touchdown"]))
        self.assertFalse(on_niche("Daily Football News - Manchester United updates", ["nfl"]))
        self.assertFalse(on_niche("Infloor heating tips", ["nfl"]))
        self.assertTrue(on_niche("anything", None))

    def test_a_soccer_channel_under_an_nfl_search_is_left_out(self):
        from analytics import competitor_list

        service = MagicMock()
        service.search.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": {"channelId": UC_A},
                    "snippet": {
                        "title": "Daily Football News",
                        "description": "Manchester United and Premier League updates",
                    },
                },
                {
                    "id": {"channelId": UC_B},
                    "snippet": {"title": "HangTime NFL", "description": "New NFL videos every day"},
                },
            ]
        }
        service.channels.return_value.list.return_value.execute.return_value = {"items": []}
        rows = competitor_list.suggest(
            "tapin", service, queries=["NFL news"], keys={"NFL news": ["nfl", "touchdown"]}
        )
        self.assertEqual([r["title"] for r in rows], ["HangTime NFL"])

    def _ops(self, **kwargs):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["competitors"][1](Namespace(channel="tapin", **kwargs))
        return code, buf.getvalue()

    def test_a_channel_is_added_by_its_name_from_the_kept_shortlist(self):
        from analytics import competitor_list

        competitor_list.save_shortlist(
            "tapin",
            [
                {"id": UC_A, "title": "Full Mount MMA", "about": "", "query": "UFC news"},
                {"id": UC_B, "title": "THE MMA GURU", "about": "", "query": "UFC news"},
            ],
        )
        self.assertEqual(competitor_list.from_shortlist("tapin", "full mount mma")["id"], UC_A)
        self.assertEqual(competitor_list.from_shortlist("tapin", "guru")["id"], UC_B)
        self.assertIsNone(competitor_list.from_shortlist("tapin", "mma"))  # two match
        with patch("analytics.competitor_sync._get_youtube_service") as service:
            code, text = self._ops(target="add", source=None, name="Full Mount MMA")
        service.assert_not_called()
        self.assertEqual(code, 0, text)
        self.assertIn(f"Added: Full Mount MMA [{UC_A}]", text)
        self.assertEqual(competitor_list.load_shortlist("tapin")[1][0]["id"], UC_B)

    def test_a_name_that_is_not_on_the_shortlist_says_where_to_look(self):
        code, text = self._ops(target="add", source=None, name="Nobody")
        self.assertEqual(code, 1)
        self.assertIn("competitors suggest", text)


if __name__ == "__main__":
    unittest.main()
