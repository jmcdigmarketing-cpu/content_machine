"""Wave 78 (#1119): a game's patch notes as dated facts.

No signal returned them: the Steam signal found the game and its store row fed no fact line
at all. Steam's news API is keyless and per app id, so the game the topic names can carry the
developer's own update posts - each stated against today, like a release date (#1025).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

from apis.signal_contract import STATUS_OK

DAY = 86400
OCT_3 = 1790985600  # 2026-10-03 00:00 UTC


def _item(title, when=OCT_3, *, feed_type=1, tags=()):
    return {"title": title, "date": when, "feed_type": feed_type, "tags": list(tags), "url": "u"}


def _news(*items):
    return {"appnews": {"appid": 1145350, "newsitems": list(items)}}


class PatchNotesTests(unittest.TestCase):
    def test_the_developers_update_posts_are_kept_newest_first(self):
        from apis.steam_api import patch_notes

        rows = patch_notes(
            _news(
                _item("Patch 2 Notes", OCT_3 - 20 * DAY),
                _item("The Unseen Update is live", OCT_3),
                _item("Hades II wins an award", OCT_3 - DAY),
            )
        )
        self.assertEqual([r["title"] for r in rows], ["The Unseen Update is live", "Patch 2 Notes"])
        self.assertEqual(rows[0]["date"], "2026-10-03")

    def test_a_patchnotes_tag_counts_whatever_the_title_says(self):
        from apis.steam_api import patch_notes

        rows = patch_notes(_news(_item("1.0.4", feed_type=0, tags=["patchnotes"])))
        self.assertEqual([r["title"] for r in rows], ["1.0.4"])

    def test_press_coverage_is_not_a_patch_note(self):
        from apis.steam_api import patch_notes

        rows = patch_notes(_news(_item("Hades II patch reviewed by PC Gamer", feed_type=0)))
        self.assertEqual(rows, [])

    def test_a_reply_that_is_not_news_gives_nothing(self):
        from apis.steam_api import patch_notes

        self.assertEqual(patch_notes({"items": [{"name": "Hades II"}]}), [])
        self.assertEqual(patch_notes(None), [])
        self.assertEqual(patch_notes(_news(_item("Patch 3", "not a time"))), [])

    def test_at_most_three(self):
        from apis.steam_api import patch_notes

        rows = patch_notes(_news(*[_item(f"Patch {n}", OCT_3 - n * DAY) for n in range(6)]))
        self.assertEqual(len(rows), 3)


class SignalTests(unittest.TestCase):
    def _signal(self, news_reply, news_status=200):
        from apis import steam_api

        store = SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {
                "items": [{"id": 1145350, "name": "Hades II"}, {"id": 2, "name": "Hades"}]
            },
        )
        news = SimpleNamespace(status_code=news_status, text="", json=lambda: news_reply)
        urls: list[str] = []

        def _get(url, timeout=10):
            urls.append(url)
            return news if "ISteamNews" in url else store

        with patch.object(steam_api.requests, "get", side_effect=_get):
            return steam_api.get_steam_signal("Hades II update"), urls

    def test_the_named_game_carries_its_patch_notes(self):
        signal, urls = self._signal(_news(_item("Patch 3 Notes")))
        self.assertEqual(signal["status"], STATUS_OK)
        self.assertEqual(signal["data"][0]["patch_notes"][0]["title"], "Patch 3 Notes")
        self.assertNotIn("patch_notes", signal["data"][1])
        self.assertEqual(len(urls), 2)
        self.assertIn("appid=1145350", urls[1])

    def test_a_failed_news_request_leaves_the_store_result_standing(self):
        signal, _urls = self._signal({}, news_status=503)
        self.assertEqual(signal["status"], STATUS_OK)
        self.assertTrue(signal["active"])
        self.assertNotIn("patch_notes", signal["data"][0])

    def test_a_topic_with_extra_words_is_searched_again_by_name(self):
        """Measured 2026-10-10: "Hades II update" and "Marvel Rivals season" were inactive."""
        from apis import steam_api

        def _reply(payload):
            return SimpleNamespace(status_code=200, text="", json=lambda: payload)

        urls: list[str] = []

        def _get(url, timeout=10):
            urls.append(url)
            if "ISteamNews" in url:
                return _reply(_news(_item("Patch 3 Notes")))
            if "term=Hades+II&" in url:
                return _reply({"items": [{"id": 1145350, "name": "Hades II"}]})
            return _reply({"items": []})

        with patch.object(steam_api.requests, "get", side_effect=_get):
            signal = steam_api.get_steam_signal("Hades II update")
        self.assertEqual(signal["status"], STATUS_OK)
        self.assertEqual(signal["data"][0]["name"], "Hades II")
        self.assertEqual(signal["data"][0]["patch_notes"][0]["title"], "Patch 3 Notes")
        self.assertIn("term=Hades+II+update", urls[0])

    def test_the_name_comes_from_the_shared_tokenizer(self):
        from apis.steam_api import name_terms

        self.assertEqual(name_terms("Hades II update"), ["Hades II"])
        self.assertIn("Marvel Rivals", name_terms("Marvel Rivals season 10.5 changes"))
        self.assertEqual(name_terms("Hades II"), [])

    def test_nothing_by_name_either_is_still_inactive(self):
        from apis import steam_api
        from apis.signal_contract import STATUS_INACTIVE

        empty = SimpleNamespace(status_code=200, text="", json=lambda: {"items": []})
        with patch.object(steam_api.requests, "get", return_value=empty):
            signal = steam_api.get_steam_signal("Hades II update")
        self.assertEqual(signal["status"], STATUS_INACTIVE)
        self.assertFalse(signal["active"])

    def test_the_signal_keeps_its_shape(self):
        from apis.signal_contract import make_signal

        signal, _urls = self._signal(_news(_item("Patch 3 Notes")))
        self.assertEqual(set(signal), set(make_signal(connected=True, active=True)))


class FactLineTests(unittest.TestCase):
    NOTE: ClassVar[dict[str, str]] = {"title": "Patch 3 Notes", "date": "2026-10-03", "url": "u"}

    def test_the_date_is_stated_against_today(self):
        from core.signal_facts import patch_note_line

        self.assertEqual(
            patch_note_line("Hades II", self.NOTE, "2026-10-10"),
            'Steam: Hades II update - "Patch 3 Notes", posted 2026-10-03 (7 days ago)',
        )

    def test_an_old_patch_is_marked_not_recent(self):
        from core.signal_facts import patch_note_line

        line = patch_note_line("Hades II", self.NOTE, "2027-02-10")
        self.assertIn("(4 months ago - NOT recent)", line)

    def test_a_note_from_the_future_or_undated_is_dropped(self):
        from core.signal_facts import patch_note_line

        self.assertEqual(patch_note_line("Hades II", self.NOTE, "2026-09-01"), "")
        self.assertEqual(
            patch_note_line("Hades II", {"title": "Patch", "date": ""}, "2026-10-10"), ""
        )
        self.assertEqual(patch_note_line("", self.NOTE, "2026-10-10"), "")

    def test_the_fact_block_carries_the_line(self):
        from core import signal_facts

        signals = {
            "steam": {
                "connected": True,
                "active": True,
                "data": [{"id": 1, "name": "Hades II", "patch_notes": [self.NOTE]}],
            }
        }
        with patch.object(signal_facts, "_today", return_value="2026-10-10"):
            text = self._facts(signal_facts, signals)
        self.assertIn('Steam: Hades II update - "Patch 3 Notes", posted 2026-10-03', text)

    def test_a_steam_row_with_no_notes_adds_no_line(self):
        from core import signal_facts

        signals = {
            "steam": {"connected": True, "active": True, "data": [{"id": 1, "name": "Hades II"}]}
        }
        with patch.object(signal_facts, "_today", return_value="2026-10-10"):
            self.assertNotIn("Steam:", self._facts(signal_facts, signals))

    @staticmethod
    def _facts(module, signals) -> str:
        return module.format_signal_facts(signals)


if __name__ == "__main__":
    unittest.main()
