"""#1021 — the angle the operator keeps is the frame the next run leads with."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.angle_intent import kept_frames, order_frames, record_pick


class AnglePickTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self._path = Path(self._dir.name) / "angle_picks.json"
        self._patch = patch("core.angle_intent.PICKS_FILE", self._path)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_a_kept_generated_frame_leads_the_next_table(self) -> None:
        record_pick("tapin", kind="one", frame="the_stat_that_proves_it", edited=False)
        record_pick("tapin", kind="one", frame="the_stat_that_proves_it", edited=False)
        record_pick("tapin", kind="one", frame="the_case_for_the_take", edited=False)
        record_pick("tapin", kind="own", frame="", edited=True)
        self.assertEqual(
            kept_frames("tapin"),
            ["the_stat_that_proves_it", "the_case_for_the_take"],
        )
        ordered = order_frames(
            ["the_case_for_the_take", "the_strongest_evidence", "the_stat_that_proves_it"],
            "tapin",
        )
        self.assertEqual(ordered[0], "the_stat_that_proves_it")
        self.assertEqual(
            ordered[1:],
            ["the_case_for_the_take", "the_strongest_evidence"],
        )

    def test_the_generator_asks_for_the_kept_frame_first(self) -> None:
        from apis.topic_variants import generate_variants

        record_pick("tapin", kind="one", frame="impact_analysis", edited=False)
        seen: dict[str, str] = {}

        def _capture(prompt, **_kwargs):
            seen["prompt"] = prompt
            return "\n".join(f"Angle line number {n} here" for n in range(1, 6))

        with patch("apis.topic_variants.complete", _capture):
            generate_variants(
                "Chargers week 5 bounce back",
                channel_id="tapin",
                intent="take",
            )
        block = seen["prompt"].split("Angle types")[1].split("Rules:")[0]
        lines = [
            line.strip()
            for line in block.splitlines()
            if line.strip() and not line.strip().startswith("(")
        ]
        self.assertEqual(lines[0], "impact_analysis")
