"""#565: diff the retention curves of two videos on the same franchise.

Every synced video keeps its audience-retention curve (`retention_curve`), and
`core/retention` only ever averaged them into one pacing hint. Two videos on the same
franchise - one that held, one that did not - say where a script lost people.
`retention_diff_lines` samples both curves at the same points, prints them side by side
and names the stretch where the gap opened most. With no runs named it takes the
franchise with the most measured curves and compares its best and worst engaged videos.
`ops retention-diff --run-id A B`.
"""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

HELD = [[x / 10, 1.0 - 0.02 * x] for x in range(11)]  # ends at 0.80
LOST = [[x / 10, 1.0 - (0.02 * x if x <= 2 else 0.04 + 0.08 * (x - 2))] for x in range(11)]


def _log(i, curve, rate):
    return SimpleNamespace(
        content_run_id=i, metrics_json=json.dumps({"engaged_rate": rate, "retention_curve": curve})
    )


RUNS = {
    1: SimpleNamespace(id=1, title="UFC 320: Topuria holds", selected_topic="UFC 320"),
    2: SimpleNamespace(id=2, title="UFC 320 recap", selected_topic="UFC 320"),
    3: SimpleNamespace(id=3, title="GTA 6 trailer", selected_topic="GTA 6"),
}
LOGS = [_log(1, HELD, 0.8), _log(2, LOST, 0.4), _log(3, HELD, 0.6)]


class DiffTests(unittest.TestCase):
    def setUp(self):
        self._patches = [
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_timed_outcomes=lambda c: LOGS),
            ),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(
                    get=lambda i: RUNS.get(int(i)), list_for_channel=lambda c: list(RUNS.values())
                ),
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def test_the_gap_is_named_where_it_opens(self):
        from core.retention import retention_diff_lines

        text = "\n".join(retention_diff_lines("tapin", 1, 2))
        self.assertIn("run 1", text)
        self.assertIn("run 2", text)
        self.assertIn("100%: 0.80 vs 0.32", text)
        self.assertIn("the gap opens most between 20% and 30%", text)

    def test_without_runs_it_takes_the_best_and_worst_of_one_franchise(self):
        from core.retention import retention_diff_lines

        text = "\n".join(retention_diff_lines("tapin"))
        self.assertIn("ufc", text)
        self.assertIn("run 1", text)
        self.assertIn("run 2", text)
        self.assertNotIn("run 3", text)

    def test_different_franchises_are_flagged(self):
        from core.retention import retention_diff_lines

        self.assertIn("different franchises", "\n".join(retention_diff_lines("tapin", 1, 3)))

    def test_a_run_without_a_curve_says_so(self):
        from core.retention import retention_diff_lines

        self.assertIn("no retention curve", "\n".join(retention_diff_lines("tapin", 1, 9)))

    def test_the_ops_verb(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["retention-diff"][1](Namespace(channel="tapin", run_id=1, target="2"))
        self.assertEqual(code, 0)
        self.assertIn("gap opens most", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
