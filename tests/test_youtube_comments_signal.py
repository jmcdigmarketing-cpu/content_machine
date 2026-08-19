"""youtube_comments signal — audience questions as content gaps.

Wired against the **official Data API** (1 unit per video) rather than the catalog's
`streamers/youtube-comments-scraper`, which would bill Apify credits for data the
YouTube key already reaches. Two properties matter beyond "it parses":

* Comments are audience *language*, never verified fact — `signal_facts` must label
  them so the script prompt can't promote a viewer's guess into a claim.
* These lines reach an advertiser-facing channel's script prompt, so crude comments
  are dropped rather than trusted to the LLM.

No network: the API client is mocked (tests/CLAUDE.md).
"""

import unittest
from unittest.mock import MagicMock, patch

from apis import youtube_comments_signal as yc
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, STATUS_QUOTA


def _thread(text, likes=0, replies=0):
    return {
        "snippet": {
            "topLevelComment": {"snippet": {"textDisplay": text, "likeCount": likes}},
            "totalReplyCount": replies,
        }
    }


def _search(n=3):
    return {
        "items": [
            {"id": {"kind": "youtube#video", "videoId": f"vid{i}"}, "snippet": {"title": f"T{i}"}}
            for i in range(n)
        ]
    }


class TestQuestionQuality(unittest.TestCase):
    def test_substantive_question_kept(self):
        self.assertTrue(yc._is_useful_question("Why did they nerf healing instead of damage?"))

    def test_engagement_bait_dropped(self):
        for noise in ("who else is watching in 2026?", "first?", "anyone else here?"):
            self.assertFalse(yc._is_useful_question(noise))

    def test_too_short_or_too_long_dropped(self):
        self.assertFalse(yc._is_useful_question("why?"))
        self.assertFalse(yc._is_useful_question("why " * 90 + "?"))

    def test_profane_question_dropped(self):
        # These lines are fed to the script prompt for a monetised channel.
        self.assertFalse(yc._is_useful_question("Whats the fucking point of this patch?"))

    def test_is_clean_catches_variants(self):
        self.assertFalse(yc._is_clean("that was shitty"))
        self.assertTrue(yc._is_clean("that was rough"))


class TestThemes(unittest.TestCase):
    def test_drops_stopwords_and_topic_words(self):
        comments = [{"text": "the matchmaking is broken matchmaking again"} for _ in range(3)]
        themes = yc._themes(comments, "matchmaking update")
        self.assertNotIn("matchmaking", themes)  # it's in the topic already
        self.assertNotIn("the", themes)
        self.assertIn("broken", themes)

    def test_requires_repetition(self):
        # A word seen once isn't a theme.
        self.assertEqual(yc._themes([{"text": "unique zebra"}], "topic"), [])

    def test_profane_comments_excluded_from_themes(self):
        comments = [{"text": "shit balance shit balance"} for _ in range(3)]
        self.assertNotIn("shit", yc._themes(comments, "topic"))


class TestSignal(unittest.TestCase):
    def _run(self, threads, search_items=3, quota=True):
        client = MagicMock()
        client.commentThreads.return_value.list.return_value.execute.return_value = {
            "items": threads
        }
        with (
            patch("apis.youtube_api._youtube_key", return_value="k"),
            patch("apis.youtube_api._get_youtube_client", return_value=client),
            patch("apis.youtube_api._search_videos", return_value=_search(search_items)),
            patch.object(yc, "has_quota_for_search", return_value=quota),
            patch.object(yc, "record_usage"),
        ):
            return yc.get_youtube_comments_signal("Marvel Rivals season 9")

    def test_happy_path(self):
        # Must share a word with the topic ("Marvel Rivals season 9") — questions are
        # surfaced as content gaps *in our coverage*, so an unrelated one is not a gap.
        sig = self._run([_thread("Why did they nerf healing in Marvel Rivals season 9?", likes=50)])
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertTrue(sig["active"])
        self.assertTrue(sig["data"]["questions"])

    def test_off_topic_question_is_not_surfaced(self):
        # Run 66 surfaced only "What about Alaska?" from 25 comments on a GTA video.
        sig = self._run([_thread("What about Alaska?", likes=99)])
        self.assertEqual(sig["data"]["questions"], [])

    def test_no_comments_is_inactive_not_an_error(self):
        # Comments disabled on every top video is normal, not a failure.
        sig = self._run([])
        self.assertEqual(sig["status"], STATUS_INACTIVE)
        self.assertTrue(sig["connected"])

    def test_no_key(self):
        with patch("apis.youtube_api._youtube_key", return_value=""):
            self.assertEqual(yc.get_youtube_comments_signal("topic")["status"], STATUS_NO_KEY)

    def test_quota_exhausted_reports_quota(self):
        with (
            patch("apis.youtube_api._youtube_key", return_value="k"),
            patch.object(yc, "has_quota_for_search", return_value=False),
        ):
            self.assertEqual(yc.get_youtube_comments_signal("topic")["status"], STATUS_QUOTA)

    def test_api_failure_never_raises(self):
        with (
            patch("apis.youtube_api._youtube_key", return_value="k"),
            patch.object(yc, "has_quota_for_search", return_value=True),
            patch("apis.youtube_api._get_youtube_client", side_effect=OSError("boom")),
        ):
            sig = yc.get_youtube_comments_signal("topic")
        self.assertFalse(sig["active"])

    def test_comments_disabled_on_one_video_is_skipped(self):
        client = MagicMock()
        client.commentThreads.return_value.list.return_value.execute.side_effect = OSError(
            "commentsDisabled"
        )
        with (
            patch("apis.youtube_api._youtube_key", return_value="k"),
            patch("apis.youtube_api._get_youtube_client", return_value=client),
            patch("apis.youtube_api._search_videos", return_value=_search(2)),
            patch.object(yc, "has_quota_for_search", return_value=True),
            patch.object(yc, "record_usage"),
        ):
            sig = yc.get_youtube_comments_signal("topic")
        self.assertEqual(sig["status"], STATUS_INACTIVE)

    def test_video_count_is_capped(self):
        # Each video costs a quota unit; the cap keeps a topic bounded.
        with patch.dict("os.environ", {"YOUTUBE_COMMENTS_MAX_VIDEOS": "2"}, clear=False):
            sig = self._run(
                [_thread("Why is the meta so stale right now?", likes=5)], search_items=8
            )
        self.assertLessEqual(sig["data"]["videos_scanned"], 2)

    def test_signal_shape(self):
        sig = self._run([_thread("Why did they nerf the healing on that hero?", likes=5)])
        for field in ("connected", "active", "score", "confidence", "status", "data"):
            self.assertIn(field, sig)


class TestPromptWiring(unittest.TestCase):
    """signal_facts formats per-signal — without a branch the data is silently dropped."""

    def _facts(self, data):
        from core.signal_facts import format_signal_facts

        return format_signal_facts(
            {"youtube_comments": {"connected": True, "active": True, "data": data}}
        )

    def test_questions_are_labelled_unverified(self):
        out = self._facts({"questions": ["Why was the tank gutted?"], "themes": []})
        self.assertIn("Why was the tank gutted?", out)
        self.assertIn("unverified", out.lower())

    def test_never_presented_as_fact(self):
        out = self._facts({"questions": ["Did they confirm a new hero?"], "themes": []})
        self.assertNotIn("VERIFIED", out.upper().replace("UNVERIFIED", ""))

    def test_themes_rendered(self):
        self.assertIn("nerf", self._facts({"questions": [], "themes": ["nerf", "meta"]}))

    def test_empty_payload_adds_no_question_block(self):
        # format_signal_facts falls back to its own placeholder; what matters is that
        # an empty payload contributes no audience lines.
        out = self._facts({"questions": [], "themes": []})
        self.assertNotIn("AUDIENCE QUESTIONS", out)
        self.assertNotIn("Audience vocabulary", out)


class TestCostControls(unittest.TestCase):
    def test_pinned_during_variant_scoring(self):
        # Without this it re-runs per variant at ~103 units each.
        from apis.register_signals import _VARIANT_REUSE_DEFAULT

        self.assertIn("youtube_comments", _VARIANT_REUSE_DEFAULT)

    def test_has_a_long_cache_ttl(self):
        from apis.register_signals import _cache_ttl_for

        self.assertGreaterEqual(_cache_ttl_for("youtube_comments"), 3 * 60 * 60)

    def test_registered_as_a_signal(self):
        from apis.signals_bootstrap import get_signal_registry

        self.assertIn("youtube_comments", get_signal_registry().get_registered_signals())


if __name__ == "__main__":
    unittest.main()
