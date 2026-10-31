"""Wave 136 (2026-10-30) - money and reach (decision 88).

#1754 + #1755 Facebook Reels through Buffer, only Shorts made public after it is connected; #1772
every public Short crossposted within the hour, and the week's misses; #1750 a link page on R2 (the
latest long video, the week's top Shorts, the affiliate links); #1753 income beside spend; #1756 +
#1757 TikTok that can earn; #1758's prepublish guard (no affiliate link on a Short).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 30, 23, 0, tzinfo=timezone.utc)


class FacebookTests(unittest.TestCase):
    def test_a_reel_request(self):
        from publishing.buffer_api import post_input

        body = post_input("fb123", text="t", video_url="https://x/v.mp4", due_at=NOW,
                          service="facebook")  # fmt: skip
        self.assertEqual(body["metadata"], {"facebook": {"type": "reel"}})
        self.assertEqual(body["channelId"], "fb123")

    def test_facebook_is_a_platform_read_from_its_env(self):
        from publishing import crosspost

        self.assertIn("facebook", crosspost.PLATFORMS)
        with (
            patch.dict(os.environ, {"BUFFER_FACEBOOK_CHANNEL_ID": "fb123"}),
            patch.object(crosspost, "_load", return_value={}),
        ):
            self.assertEqual(crosspost.buffer_channel_ids("tapin")["facebook"], "fb123")
        with patch.object(crosspost, "_load", return_value={}):
            self.assertNotIn("facebook", crosspost.buffer_channel_ids("tapin"))

    def test_buffers_list_picks_a_facebook_page(self):
        from publishing.crosspost import choose_channels

        picked, notes = choose_channels([{"service": "facebook", "id": "f1", "name": "TapIn"}])
        self.assertEqual(picked.get("facebook"), "f1")
        _picked, notes = choose_channels([])
        self.assertTrue(any("Facebook" in n for n in notes))

    def test_a_new_platform_starts_from_now(self):
        from publishing.crosspost import platform_baselines

        posts = {"101": {"tiktok": {"state": "sent"}}}
        got = platform_baselines({}, ["tiktok", "facebook"], posts, public=[101, 102, 103])
        self.assertEqual(got["tiktok"], [])  # established: nothing skipped
        self.assertEqual(got["facebook"], [101, 102, 103])  # new: the old public runs skipped
        again = platform_baselines(got, ["tiktok", "facebook"], posts, public=[101, 102, 103, 104])
        self.assertEqual(again["facebook"], [101, 102, 103])  # recorded once

    def test_the_round_skips_a_platforms_baseline(self):
        import inspect

        from publishing import crosspost

        source = inspect.getsource(crosspost.send_due)
        self.assertIn("platform_baselines(", source)
        self.assertIn('("instagram", "facebook")', source)  # the Reel length limit for both


def _row(run_id, video, *, published, privacy="public"):
    return SimpleNamespace(content_run_id=run_id, youtube_video_id=video, privacy_status=privacy,
                           published_at=published, title=f"run {run_id}", metrics_json="{}",
                           status="published")  # fmt: skip


class WithinTheHourTests(unittest.TestCase):
    """#1772 (B08.1): a missed post waited until something else turned public."""

    def _store(self):
        return {
            "buffer": {"since": "2026-10-01T00:00:00+00:00", "baseline": [],
                       "organization_id": "o", "baselines": {"tiktok": [], "instagram": []}},
            # `at` is when Buffer got it; the due time is decision 64's next 10 PM, hours later
            "posts": {
                "1": {"tiktok": {"state": "sent", "at": (NOW - timedelta(minutes=175)).isoformat(),
                                 "due_at": (NOW + timedelta(hours=5)).isoformat()},
                      "instagram": {"state": "sent", "at": (NOW - timedelta(minutes=175)).isoformat(),
                                    "due_at": (NOW + timedelta(hours=5)).isoformat()}},
                "2": {"tiktok": {"state": "sent", "at": (NOW - timedelta(minutes=65)).isoformat(),
                                 "due_at": (NOW + timedelta(hours=5)).isoformat()}},
                "3": {"tiktok": {"state": "sent", "at": (NOW - timedelta(minutes=95)).isoformat(),
                                 "due_at": (NOW + timedelta(hours=5)).isoformat()},
                      "instagram": {"state": "skipped", "error": "95s, longer than a Reel (90s)"}},
            },
        }  # fmt: skip

    def _rows(self):
        return [_row(1, "a", published=NOW - timedelta(hours=3)),
                _row(2, "b", published=NOW - timedelta(minutes=70)),
                _row(3, "c", published=NOW - timedelta(minutes=100))]  # fmt: skip

    def _patches(self):
        from publishing import crosspost

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = self._rows()
        return (
            patch.object(crosspost, "_load", return_value=self._store()),
            patch.object(
                crosspost, "buffer_channel_ids", return_value={"tiktok": "t", "instagram": "i"}
            ),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
        )

    def test_the_late_one_is_found(self):
        from publishing.crosspost import late_runs

        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            self.assertEqual(late_runs("tapin", now=NOW), [(2, ["instagram"])])

    def test_the_week_names_the_misses(self):
        from publishing.crosspost import miss_lines

        store = self._store()
        store["posts"]["2"]["instagram"] = {"state": "sent", "at": NOW.isoformat(),  # queued late
                                            "due_at": (NOW + timedelta(hours=5)).isoformat()}  # fmt: skip
        _p1, p2, p3 = self._patches()
        with p2, p3, patch("publishing.crosspost._load", return_value=store):
            text = "\n".join(miss_lines("tapin", now=NOW))
        self.assertIn("Instagram: 1 queued late, 1 too long", text)
        self.assertNotIn("TikTok", text)  # queued at once; its 10 PM due time is not a miss

    def test_the_worker_sends_them(self):
        import inspect

        from jobs import worker

        self.assertIn("late_runs(", inspect.getsource(worker._crosspost_scheduled_live))


class LinkPageTests(unittest.TestCase):
    """#1750 (B07.4, the operator: on R2; the long video, the week's top Shorts, the links)."""

    def _page(self, *, tagged):
        from publishing.link_page import links_html

        return links_html(
            "TapIn Media",
            long_video={"title": "GTA 6 - everything we know", "url": "https://youtu.be/L"},
            shorts=[{"title": f"Short {i}", "url": f"https://youtu.be/s{i}"} for i in range(3)],
            affiliates=([{"label": "GTA 6 on Amazon", "url": "https://amazon.com/s?k=GTA&tag=t-20"}]
                        if tagged else []),
            ftc="As an Amazon Associate we earn from qualifying purchases." if tagged else "",
        )  # fmt: skip

    def test_the_page_holds_all_three(self):
        page = self._page(tagged=True)
        for text in (
            "GTA 6 - everything we know",
            "https://youtu.be/L",
            "Short 2",
            "GTA 6 on Amazon",
            "tag=t-20",
            "Amazon Associate",
        ):
            self.assertIn(text, page)  # fmt: skip
        self.assertNotIn("@", page)  # no personal data

    def test_no_tag_no_links(self):
        page = self._page(tagged=False)
        self.assertNotIn("Amazon", page)

    def test_it_goes_up_as_a_web_page(self):
        from publishing import link_page

        client = MagicMock()
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"R2_PUBLIC_BASE_URL": "https://pub-x.r2.dev"}),
            patch.object(link_page, "collect", return_value={
                "long_video": None, "shorts": [], "affiliates": [], "ftc": ""}),
            patch.object(link_page, "_out_dir", return_value=tmp),
            patch("publishing.video_host._client", return_value=client),
            patch("publishing.video_host._bucket", return_value="b"),
        ):  # fmt: skip
            url = link_page.build_and_host("tapin")
        self.assertEqual(url, "https://pub-x.r2.dev/tapin/links.html")
        extra = client.upload_file.call_args.kwargs["ExtraArgs"]
        self.assertEqual(extra["ContentType"], "text/html; charset=utf-8")

    def test_overnight_refreshes_it(self):
        import inspect

        from core import overnight
        from scripts import ops

        self.assertIn("build_and_host(", inspect.getsource(overnight))
        self.assertIn('_register("links"', inspect.getsource(ops))


class IncomeTests(unittest.TestCase):
    """#1753 (B07.7): what the channel earns outside YouTube, beside what it spends."""

    def setUp(self):
        from core.money import ledger

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = os.path.join(tmp.name, "spend_ledger.json")
        with open(store, "w", encoding="utf-8") as handle:
            json.dump({"entries": [{"id": 1, "kind": "ads", "amount": 25.65, "date": "2026-10-26",
                                    "what": "campaigns", "ended": "2026-10-27"}]}, handle)  # fmt: skip
        patcher = patch.object(ledger, "LEDGER_FILE", store)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_net(self):
        from core.money import ledger

        ledger.add_income(3.12, "Amazon Associates, November", on=date(2026, 11, 30))
        self.assertEqual(ledger.total_spent(today=date(2026, 12, 1))["total"], 25.65)  # not spend
        self.assertIn("net -$22.53", ledger.money_line(today=date(2026, 12, 1)))
        ledger.add_entry(1.0, "credits", kind="credits", on=date(2026, 12, 1))
        self.assertEqual(len(ledger.income_rows()), 1)  # a spend write keeps the income

    def test_ops_and_the_scoreboard(self):
        import inspect

        from core.success import bridge
        from scripts import ops

        self.assertIn("add_income(", inspect.getsource(ops))
        self.assertIn("money_line(", inspect.getsource(bridge.scoreboard_lines))


class TikTokRewardsTests(unittest.TestCase):
    """#1756 + #1757 (B07.10-11): Creator Rewards pays for videos over a minute, from accounts
    with 10k followers and 100k views in 30 days."""

    def test_over_a_minute(self):
        from publishing.platform_metrics import reward_eligible

        self.assertFalse(reward_eligible(45.0))
        self.assertTrue(reward_eligible(75.0))
        self.assertFalse(reward_eligible(None))

    def test_the_line(self):
        from publishing.platform_metrics import tiktok_line

        rows = {"1": {"tiktok": {"views": 2000, "reward_eligible": False}},
                "2": {"tiktok": {"views": 75, "reward_eligible": True}},
                "3": {"instagram": {"views": 900}}}  # fmt: skip
        posts = {"1": {"tiktok": {"due_at": (NOW - timedelta(days=3)).isoformat()}},
                 "2": {"tiktok": {"due_at": (NOW - timedelta(days=10)).isoformat()}}}  # fmt: skip
        line = tiktok_line(rows, posts, now=NOW)
        self.assertEqual(line, "TikTok: 2,075 of 100,000 views in 30 days; 1 of 2 posts over a "
                               "minute; followers not read")  # fmt: skip

    def test_the_rows_carry_it(self):
        import inspect

        from publishing import platform_metrics

        self.assertIn("reward_eligible", inspect.getsource(platform_metrics._stored_metrics))


class ShortAffiliateTests(unittest.TestCase):
    """#1758 (B07.12): a Short's description links are not clickable."""

    def _request(self, text):
        from publishing.base import PublishRequest

        return PublishRequest(file_path="v.mp4", title="t", description=text)

    def test_a_short_loses_the_link(self):
        from publishing.prepublish import without_short_affiliates

        text = "Body.\n\nGTA 6 on Amazon: https://www.amazon.com/s?k=GTA&tag=tapin-20\nMore."
        with patch("publishing.prepublish._is_long", return_value=False):
            request, removed = without_short_affiliates(self._request(text), 216)
        self.assertEqual(removed, 1)
        self.assertNotIn("amazon.com", request.description)
        self.assertIn("More.", request.description)

    def test_a_long_video_keeps_it(self):
        from publishing.prepublish import without_short_affiliates

        text = "Body.\nGTA 6 on Amazon: https://www.amazon.com/s?k=GTA&tag=tapin-20"
        with patch("publishing.prepublish._is_long", return_value=True):
            request, removed = without_short_affiliates(self._request(text), 300)
        self.assertEqual((removed, request.description), (0, text))

    def test_the_upload_runs_it(self):
        import inspect

        from publishing import youtube_publisher

        self.assertIn("without_short_affiliates(", inspect.getsource(youtube_publisher))


if __name__ == "__main__":
    unittest.main()
