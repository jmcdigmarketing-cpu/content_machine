"""#578: cost per finished minute of video, not per run.

A 45-second Short and an eight-minute all-angles video cost very differently per run, so
"$/video" hid what the machine costs to make video. Each uploaded run's length now comes
from its render (`features["technical_qc"]["video_duration"]`, measured by ffprobe) or,
when it has none, from its word count at the voice's spoken pace - and the unit-economics
summary (`ops economics`, the weekly report) prints the cost per finished minute and how
many lengths were measured vs estimated.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _run(run_id, cost, *, seconds=None, words=0):
    features = {"cost": {"total": cost}}
    if seconds is not None:
        features["technical_qc"] = {"video_duration": seconds}
    # The spoken word count lives in timings_json (core/pipeline) - a record has no
    # `word_count` attribute; the first version of this test invented one and passed.
    return SimpleNamespace(
        id=run_id, features_json=json.dumps(features), title=f"t{run_id}", selected_topic="",
        input_topic="", timings_json=json.dumps({"word_count": words} if words else {}),
        quality_json="{}",
    )  # fmt: skip


def _log(run_id, *, privacy="unlisted", revenue=None):
    metrics = {}
    if revenue is not None:
        metrics["estimated_revenue_usd"] = revenue
    return SimpleNamespace(
        id=run_id,
        content_run_id=run_id,
        youtube_video_id=f"v{run_id}",
        metrics_json=json.dumps(metrics),
        privacy_status=privacy,
    )


class MinutesTests(unittest.TestCase):
    def _econ(self, runs, *, public=(), revenue=None):
        from core import unit_economics

        earned = revenue or {}

        def logs(_channel):
            return [
                _log(
                    r.id,
                    privacy="public" if r.id in public else "unlisted",
                    revenue=earned.get(r.id),
                )
                for r in runs
            ]

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_uploaded_for_channel=logs),
            ),
            patch("core.script_length.spoken_words_per_second", return_value=3.0),
        ):
            return unit_economics.channel_economics("tapin")

    def test_the_render_length_is_used(self):
        econ = self._econ([_run(1, 0.30, seconds=90)])
        self.assertEqual((econ.videos[0].minutes, econ.videos[0].minutes_source), (1.5, "render"))

    def test_without_a_render_the_words_estimate_it(self):
        econ = self._econ([_run(2, 0.30, words=360)])  # 360 words at 3.0/s = 2 min
        self.assertEqual((econ.videos[0].minutes, econ.videos[0].minutes_source), (2.0, "words"))

    def test_the_summary_prints_cost_per_minute(self):
        from core.unit_economics import summary_lines

        econ = self._econ([_run(1, 0.30, seconds=90), _run(2, 0.30, words=360)])
        text = "\n".join(summary_lines(econ))
        self.assertIn("cost per finished minute: $0.17 marginal", text)  # $0.60 / 3.5 min
        self.assertIn("1 measured from the render, 1 estimated from words", text)

    def test_nothing_to_time_says_nothing(self):
        from core.unit_economics import summary_lines

        econ = self._econ([_run(3, 0.30)])
        self.assertNotIn("per finished minute", "\n".join(summary_lines(econ)))

    def test_published_minute_leaves_out_an_unlisted_upload(self):
        """#1072: finished minute counts every upload. Published minute is the public ones."""
        from core.unit_economics import summary_lines

        econ = self._econ(
            [_run(1, 0.60, seconds=120), _run(2, 0.60, seconds=480)],
            public={1},
        )
        text = "\n".join(summary_lines(econ))
        self.assertIn("cost per finished minute: $0.12 marginal", text)
        self.assertIn("cost per published minute: $0.30 marginal", text)
        self.assertIn("2.0 min over 1 public", text)

    def test_published_minute_names_the_return_when_revenue_exists(self):
        from core.unit_economics import summary_lines

        econ = self._econ(
            [_run(1, 0.60, seconds=120)],
            public={1},
            revenue={1: 1.20},
        )
        text = "\n".join(summary_lines(econ))
        self.assertIn("cost per published minute: $0.30 marginal", text)
        self.assertIn("return $0.60", text)


if __name__ == "__main__":
    unittest.main()
