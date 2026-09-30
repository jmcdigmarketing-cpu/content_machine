"""#428: tags and hashtags are generated for every upload and never evaluated.

Each run keeps its YouTube tags (`tags_json`) and its description carries #hashtags; nothing
joined either to outcomes. `analytics/tag_performance.py` does, the same way #566 ranks
title patterns: each tag's engaged rate shrunk toward the channel, ranked by lift, three
videos minimum. A tag on nearly every video (80%+) cannot be told apart from the channel
and is listed as such, not ranked. `ops tag-report` prints it.
"""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


def _run(i, tags, description=""):
    return SimpleNamespace(id=i, tags_json=json.dumps(tags), description=description)


def _log(i, rate):
    return SimpleNamespace(content_run_id=i, metrics_json=json.dumps({"engaged_rate": rate}))


RUNS = [
    _run(1, ["ufc", "Topuria"], "Fight week. #UFC320 #shorts"),
    _run(2, ["ufc", "topuria"], "#ufc320 #shorts"),
    _run(3, ["UFC", "topuria"], "#shorts"),
    _run(4, ["ufc", "pereira"], "#shorts"),
    _run(5, ["ufc", "pereira"], "#shorts"),
    _run(6, ["ufc", "pereira"], "#UFC320 #shorts"),
]
LOGS = [_log(1, 0.8), _log(2, 0.7), _log(3, 0.75), _log(4, 0.3), _log(5, 0.35), _log(6, 0.4)]


class _Repos(unittest.TestCase):
    def setUp(self):
        self._patches = [
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: RUNS),
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_timed_outcomes=lambda c: LOGS),
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()


class TagTests(_Repos):
    def test_tags_and_hashtags_are_read_case_blind(self):
        from analytics.tag_performance import run_tags

        self.assertEqual(run_tags(RUNS[0]), {"ufc", "topuria", "#ufc320", "#shorts"})

    def test_tags_are_ranked_by_lift(self):
        from analytics.tag_performance import tag_lifts

        rows = tag_lifts("tapin")
        ranked = [r["tag"] for r in rows]
        self.assertEqual(ranked[0], "topuria")
        self.assertEqual(ranked[-1], "pereira")
        self.assertIn("#ufc320", ranked)

    def test_a_tag_on_every_video_is_not_ranked(self):
        from analytics.tag_performance import tag_lifts, universal_tags

        self.assertEqual(universal_tags("tapin"), {"ufc", "#shorts"})
        self.assertNotIn("ufc", [r["tag"] for r in tag_lifts("tapin")])

    def test_ops_tag_report(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["tag-report"][1](Namespace(channel="tapin"))
        text = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("topuria", text)
        self.assertIn("pp vs channel", text)
        self.assertIn("on nearly every video (no signal): #shorts, ufc", text)


if __name__ == "__main__":
    unittest.main()
