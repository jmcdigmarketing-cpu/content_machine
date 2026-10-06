"""#988: the first second - what opens each video, recorded, shown and testable.

Every TapIn render had a 2.15 s channel intro (`config/channels.json`, prepended in
`video/render_video.py`) before the first word: most of the time a Shorts viewer takes to swipe.
`CHANNEL_INTRO_ENABLED` switched it for every video at once, and nothing recorded per run
whether a video had it, so nothing could compare the two. Now:

- `video.channel_intro.intro_for_run` decides per run; with the opt-in `INTRO_TEST=alternate`
  the intro is dropped on every even run id, so both kinds accumulate side by side;
- `render_vertical_video(with_intro=False)` skips the prepend; the pipeline records
  `quality["opening"] = {"intro": bool, "intro_seconds": s}` and checks the first frame at 0 s
  when there is no intro;
- the run card says what the video opens on;
- `analytics.growth` compares the stayed share with and without the intro (3+ videos each) in
  `ops growth`, the Analytics page and a ranked lever.
"""

from __future__ import annotations

import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class DecisionTests(unittest.TestCase):
    def test_default_keeps_the_intro(self):
        from video import channel_intro

        with (
            patch.object(channel_intro, "resolve_intro_path", return_value="/x/intro.mp4"),
            patch.dict("os.environ", {"INTRO_TEST": ""}),
        ):
            self.assertTrue(channel_intro.intro_for_run("tapin", 114))
            self.assertTrue(channel_intro.intro_for_run("tapin", 115))

    def test_alternate_drops_it_on_even_runs(self):
        from video import channel_intro

        with (
            patch.object(channel_intro, "resolve_intro_path", return_value="/x/intro.mp4"),
            patch.dict("os.environ", {"INTRO_TEST": "alternate"}),
        ):
            self.assertFalse(channel_intro.intro_for_run("tapin", 114))
            self.assertTrue(channel_intro.intro_for_run("tapin", 115))

    def test_no_intro_file_means_no_intro(self):
        from video import channel_intro

        with patch.object(channel_intro, "resolve_intro_path", return_value=None):
            self.assertFalse(channel_intro.intro_for_run("tapin", 115))


class RenderTests(unittest.TestCase):
    def test_render_takes_the_decision(self):
        from video.render_video import render_vertical_video

        self.assertIn("with_intro", inspect.signature(render_vertical_video).parameters)
        source = inspect.getsource(render_vertical_video)
        self.assertIn("with_intro", source[source.index("prepend_channel_intro") - 400 :])

    def test_the_pipeline_records_the_opening(self):
        from core import pipeline

        source = inspect.getsource(pipeline)
        self.assertIn("intro_for_run(", source)
        self.assertIn("with_intro=", source)
        self.assertIn('"opening"', source)

    def test_opening_record(self):
        from video.channel_intro import opening_record

        with patch("video.channel_intro._probe_duration", return_value=2.15):
            self.assertEqual(opening_record("tapin", True, "/x/intro.mp4"),
                             {"intro": True, "intro_seconds": 2.15})  # fmt: skip
        self.assertEqual(opening_record("tapin", False, "/x/intro.mp4"),
                         {"intro": False, "intro_seconds": 0.0})  # fmt: skip


class CardTests(unittest.TestCase):
    def test_the_run_card_says_what_opens_the_video(self):
        from core.run_ledger import render_dossier

        quality = {"opening": {"intro": True, "intro_seconds": 2.15}}
        record = SimpleNamespace(
            id=7, channel_id="tapin", status="done", selected_topic="t", input_topic="t",
            title="T", composite_score=50.0, abort_reason="", features_json="{}",
            quality_json=json.dumps(quality), timings_json="{}")  # fmt: skip
        with patch("storage.repositories.content_runs.get_content_run_repository",
                   return_value=type("Repo", (), {"get": lambda self, i: record})()):  # fmt: skip
            text = render_dossier(7)
        self.assertIn("2.15 s channel intro", text)


def _row(i, stayed, intro):
    metrics = {"views": 900, "stayed_share": stayed}
    return {"row": SimpleNamespace(content_run_id=600 + i, youtube_video_id=f"v{i}",
                                   metrics_json=json.dumps(metrics)),
            "opening": {"intro": intro, "intro_seconds": 2.15 if intro else 0.0}}  # fmt: skip


class GrowthTests(unittest.TestCase):
    def _split(self, items):
        from analytics import growth

        rows = [
            {"title": f"V{i}", "published": None, "views7": 500, "stayed": json.loads(
                it["row"].metrics_json)["stayed_share"], "feed": None, "views": 900, "paid": 0,
             "run_id": it["row"].content_run_id}
            for i, it in enumerate(items)
        ]  # fmt: skip
        openings = {it["row"].content_run_id: it["opening"] for it in items}
        with (
            patch("analytics.growth._rows", return_value=rows),
            patch("analytics.growth._opening", side_effect=lambda rid: openings.get(rid)),
        ):
            return growth.intro_split("tapin"), growth.intro_line("tapin")

    def test_with_and_without(self):
        items = [_row(i, s, True) for i, s in enumerate([0.50, 0.52, 0.48, 0.55])]
        items += [_row(10 + i, s, False) for i, s in enumerate([0.62, 0.60, 0.65])]
        split, line = self._split(items)
        self.assertEqual((split["n_with"], split["n_without"]), (4, 3))
        self.assertAlmostEqual(split["with"], 0.51)
        self.assertAlmostEqual(split["without"], 0.62)
        self.assertIn("without", line)
        self.assertIn("62%", line)

    def test_too_few_without_says_how_to_test(self):
        items = [_row(i, 0.5, True) for i in range(4)] + [_row(9, 0.6, False)]
        _split, line = self._split(items)
        self.assertIn("INTRO_TEST=alternate", line)

    def test_the_lever_names_the_intro_when_it_costs_viewers(self):
        from analytics.growth import levers

        rep = {
            "per_week": 7.5,
            "paid_share": 0.0,
            "intro_split": {"with": 0.50, "without": 0.62, "n_with": 6, "n_without": 4},
        }
        keys = [lever["key"] for lever in levers(rep)]
        self.assertIn("intro", keys)
        line = next(lv["line"] for lv in levers(rep) if lv["key"] == "intro")
        self.assertIn("CHANNEL_INTRO_ENABLED=false", line)


if __name__ == "__main__":
    unittest.main()
