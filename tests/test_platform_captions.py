"""#1197: two caption arms from sentences already written. No new claim.

The winner comes from experiment_stats.evaluate plus the views interval.
Stores are temp files. No network.
"""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

RUN = SimpleNamespace(
    id=41,
    title="Topuria keeps the belt",
    description="The first sentence names the fight. The second sentence names the round.",
    tags_json="[]",
    script_preview="",
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


class CaptionArmTests(unittest.TestCase):
    def test_the_swap_uses_only_sentences_already_in_the_caption(self):
        from publishing.platform_captions import caption_texts, choose_caption

        texts = caption_texts(RUN)
        self.assertTrue(texts["first_line"].startswith("The first sentence names the fight."))
        self.assertNotEqual(texts["caption"], texts["first_line"])
        allowed = _words(texts["caption"])
        self.assertTrue(_words(texts["first_line"]) <= allowed)
        self.assertNotIn("guaranteed", texts["first_line"])
        first, _ = choose_caption("tapin", RUN, "tiktok")
        again, _ = choose_caption("tapin", RUN, "tiktok")
        self.assertEqual(first, again)
        self.assertIn(first, ("caption", "first_line"))

    def test_the_report_names_the_winner_and_its_interval(self):
        from publishing import crosspost
        from publishing.platform_captions import caption_report
        from publishing.platform_metrics import _save

        posts = {}
        rows = {}
        for i in range(6):
            posts[str(i)] = {"tiktok": {"state": "sent", "arm": "first_line", "post_id": f"a{i}"}}
            rows[str(i)] = {"tiktok": {"measured": True, "views": 5000 + i}}
        for i in range(6, 12):
            posts[str(i)] = {"tiktok": {"state": "sent", "arm": "caption", "post_id": f"b{i}"}}
            rows[str(i)] = {"tiktok": {"measured": True, "views": 10 + i}}
        with (
            tempfile.TemporaryDirectory() as tmp,
            (
                patch(
                    "publishing.crosspost.CROSSPOST_TEMPLATE",
                    os.path.join(tmp, "crosspost_{channel}.json"),
                )
            ),
            patch(
                "publishing.platform_metrics.METRICS_TEMPLATE",
                os.path.join(tmp, "platform_metrics_{channel}.json"),
            ),
        ):
            crosspost._save("tapin", {"posts": posts})
            _save("tapin", {"rows": rows})
            won = caption_report("tapin", "tiktok")
            thin_posts = dict(list(posts.items())[:2])
            crosspost._save("tapin", {"posts": thin_posts})
            collecting = caption_report("tapin", "tiktok")
        self.assertIn("first_line", won)
        self.assertIn("won", won)
        self.assertIn("+/-", won)
        self.assertIn("collecting", collecting)
        self.assertNotIn("won", collecting)
