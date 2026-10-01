"""#571: a cost cap that cuts before it refuses (operator: thumbnail, then length).

`PROJECTED_COST_MAX_USD` stopped the run whenever the worst case (the longest length,
plus the image since #923) was over the cap. Now, over the cap, the run first makes
its thumbnail with Pillow ($0), then caps the longest length you can pick to the
longest preset whose worst case fits; it refuses only when even the shortest does
not. What was cut is printed; voice and models are never changed; the cuts are undone
before the next run's check.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.run_mode import CostModeBlocked


def _fake_estimate(
    *, script="", signals=None, rendered=False, length_choice="", thumbnail_provider=None
):
    words = len(script.split())
    thumb = 0.05 if thumbnail_provider in ("flux", "ideogram", "recraft") else 0.0
    total = round(words / 1000.0 + thumb, 4)  # Extended worst case: $2.00 + $0.05
    return {"tts": words / 1000.0, "thumbnail": thumb, "total": total}


class _Cap(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(
            os.environ,
            {
                "BFL_API_KEY": "k",
                "THUMBNAIL_PROVIDER": "",
                "RUN_LENGTH_CAP": "",
                "FREE_MODE_STRICT": "",
            },
        )
        self._env.start()
        self._est = patch("core.cost_meter.estimate_run_cost", side_effect=_fake_estimate)
        self._est.start()

    def tearDown(self):
        from core import run_mode

        self._est.stop()
        run_mode.restore_cost_cuts()
        self._env.stop()

    def _guard(self, cap):
        from core.run_mode import guard_before_discovery

        os.environ["PROJECTED_COST_MAX_USD"] = cap  # setUp's patch.dict restores it
        return guard_before_discovery()


class DegradeTests(_Cap):
    def test_the_thumbnail_alone_can_bring_it_under(self):
        warnings = self._guard("2.02")
        self.assertEqual(os.environ["THUMBNAIL_PROVIDER"], "pillow")
        self.assertEqual(os.environ.get("RUN_LENGTH_CAP", ""), "")
        self.assertIn("Cost cap $2.02: thumbnail -> Pillow", "\n".join(warnings))

    def test_then_the_longest_length_is_capped(self):
        warnings = "\n".join(self._guard("0.80"))
        self.assertEqual(os.environ["RUN_LENGTH_CAP"], "3")
        self.assertIn("longest length -> Long", warnings)
        self.assertIn("worst case $0.75", warnings)

    def test_it_refuses_only_when_the_shortest_will_not_fit(self):
        with self.assertRaises(CostModeBlocked):
            self._guard("0.05")
        self.assertEqual(os.environ["THUMBNAIL_PROVIDER"], "")  # nothing left cut

    def test_the_cuts_are_undone_before_the_next_check(self):
        self._guard("0.80")
        self._guard("")  # the next run, no cap
        self.assertEqual(os.environ["THUMBNAIL_PROVIDER"], "")
        self.assertEqual(os.environ.get("RUN_LENGTH_CAP", ""), "")

    def test_under_the_cap_nothing_changes(self):
        self.assertEqual(self._guard("5"), [])
        self.assertEqual(os.environ["THUMBNAIL_PROVIDER"], "")


class LengthTests(_Cap):
    def test_a_capped_choice_is_clamped(self):
        from core.script_length import capped_choice

        with patch.dict(os.environ, {"RUN_LENGTH_CAP": "2"}):
            self.assertEqual(capped_choice("4"), "2")
            self.assertEqual(capped_choice("1"), "1")
        self.assertEqual(capped_choice("4"), "4")

    def test_the_pipeline_writes_at_the_capped_length(self):
        from core.pipeline import DiscoveryResult, run_pipeline
        from core.research_brief import ResearchBrief

        signals = {"youtube": {"connected": True, "active": True, "score": 50}}
        discovery = DiscoveryResult(
            input_topic="UFC 320",
            base_signals=signals,
            evaluated=[("UFC 320", 70.0, signals)],
            channel_id="tapin",
        )
        with (
            patch.dict(os.environ, {"RUN_LENGTH_CAP": "2"}),
            patch("core.pipeline.build_research_brief", return_value=ResearchBrief()),
            patch(
                "core.pipeline.generate_content_package",
                return_value={"title": "T", "script": "Hook.", "description": "D"},
            ) as gen,
            patch("core.pipeline.write_run_dossier"),
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=1),
        ):
            run_pipeline(
                "UFC 320",
                discovery=discovery,
                proceed_video=False,
                channel_id="tapin",
                length_choice="4",
            )
        self.assertEqual(gen.call_args.kwargs.get("length_choice"), "2")


if __name__ == "__main__":
    unittest.main()
