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


def _log(run_id):
    return SimpleNamespace(
        id=run_id, content_run_id=run_id, youtube_video_id=f"v{run_id}", metrics_json="{}"
    )


class MinutesTests(unittest.TestCase):
    def _econ(self, runs):
        from core import unit_economics

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=SimpleNamespace(list_for_channel=lambda c: runs),
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(
                    list_uploaded_for_channel=lambda c: [_log(r.id) for r in runs]
                ),
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


if __name__ == "__main__":
    unittest.main()
