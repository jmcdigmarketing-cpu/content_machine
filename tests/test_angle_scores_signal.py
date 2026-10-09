"""#1014: angle scores that are not noise.

Runs 118-120 each printed "5 of 5 angles scored on the seed's signals - variant scoring hit
its 15s deadline": 91.69/89.99 ties in run 118, 100.0 x4 in run 119 (the stale UFC 305 angles
included) and "IT'S OVER 9000" on nearly every angle. Measured cause: `collect_scored_variants`
re-fetched every signal not pinned by `_VARIANT_REUSE_DEFAULT` once per angle, with the angle
text as the search topic, so every run hit the deadline, fell back to the seed's number, and
left the fetches running in the background. The composite reads the angle text only through
`infer_domain` and an exact-string history lookup, so a per-angle fetch could never rank the
angles anyway (tests/test_angle_ranker.py). The one cheap judge (`_cheap_judge`) saw the
thesis and nothing else.

Now each angle is scored on the seed's signals with the anchor and drift penalties - no
per-angle fetch, no deadline - unless VARIANT_SIGNAL_RESCORE is on; the judge sees the run's
facts and today's date; and a score every angle shares is printed once, not five times.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

TOPIC = "How the 0-4 chargers can turn it around this year"
ANGLES = [
    "The Chargers' three fixes: protect the ball, run the ball, win at home",
    "Why Herbert's interceptions decide the Chargers' season",
    "Only one team has ever done it - the Chargers can be the second",
]
FACTS = [
    "ESPN NFL: Los Angeles Chargers 0-4 (as of 2026-10-09)",
    "Herbert has thrown six interceptions, tied for second-most in the league.",
]


class SeedScoringTests(unittest.TestCase):
    def _collect(self, env):
        from core import pipeline

        with (
            patch.dict(os.environ, env),
            patch.object(pipeline, "build_registry") as fetch,
            patch.object(pipeline, "composite_score", return_value=95.0),
            patch("apis.topic_scorer.composite_score_raw", return_value=104.0),
        ):
            fetch.return_value = {"news": {"score": 1}}
            out = pipeline.collect_scored_variants(ANGLES, "tapin", {"news": {}}, TOPIC)
        return out, fetch

    def test_no_per_angle_fetch_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "VARIANT_SIGNAL_RESCORE"}
        with patch.dict(os.environ, env, clear=True):
            (evaluated, raw, meta), fetch = self._collect({})
        fetch.assert_not_called()
        self.assertEqual([v for v, *_ in evaluated], ANGLES)
        self.assertNotIn("fallback", meta)
        self.assertEqual(meta.get("scored_on"), "seed")
        self.assertEqual(set(raw), set(ANGLES))

    def test_rescoring_per_angle_is_opt_in(self):
        _out, fetch = self._collect({"VARIANT_SIGNAL_RESCORE": "true"})
        self.assertEqual(fetch.call_count, len(ANGLES))

    def test_an_angle_that_drops_the_subject_still_loses(self):
        from core import pipeline

        with (
            patch.object(pipeline, "build_registry") as fetch,
            patch.object(pipeline, "composite_score", return_value=95.0),
            patch.object(
                pipeline,
                "anchor_preservation_penalty",
                side_effect=lambda v, s: 0.0 if "Chargers" in v else 12.0,
            ),
            patch.object(pipeline, "mcu_drift_penalty", return_value=0.0),
        ):
            evaluated, _raw, _meta = pipeline.collect_scored_variants(
                [*ANGLES, "Why NFL comebacks are rare"], "tapin", {}, "Chargers comeback"
            )
        fetch.assert_not_called()
        scores = {v: s for v, s, _ in evaluated}
        self.assertLess(scores["Why NFL comebacks are rare"], scores[ANGLES[0]])

    def test_no_deadline_note_when_nothing_was_fetched(self):
        from core.pipeline import variant_fallback_note

        self.assertEqual(variant_fallback_note({"scored_on": "seed"}, total=5), "")


class JudgeTests(unittest.TestCase):
    def test_the_judge_sees_the_facts_and_the_date(self):
        from core.angle_ranker import rank_angles

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return '{"scores": [0.9, 0.7, 0.1]}'

        with patch("core.llm_router.complete", side_effect=fake):
            scores = rank_angles(
                ANGLES, seed_topic=TOPIC, llm_judge=True, facts=FACTS, today="2026-10-09"
            )
        self.assertIn("2026-10-09", prompts[0])
        self.assertIn("six interceptions", prompts[0])
        self.assertLess(scores[ANGLES[2]], scores[ANGLES[0]])

    def test_discovery_hands_the_judge_its_facts(self):
        from core import pipeline

        signals = {
            "live_scores": {
                "status": "ok",
                "score": 50,
                "data": {"line": "ESPN NFL: Los Angeles Chargers 0-4"},
            }
        }
        with (
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.build_registry", return_value=signals),
            patch("core.pipeline.generate_variants", return_value=list(ANGLES)),
            patch("core.angle_ranker._cheap_judge", return_value=None) as judge,
            patch(
                "core.signal_facts.format_signal_facts",
                return_value="- ESPN NFL: Los Angeles Chargers 0-4",
            ),
            patch.dict(
                os.environ,
                {"COMPETITOR_SYNC_ON_DISCOVERY": "off", "ANGLE_LLM_JUDGE": "true"},
            ),
        ):
            pipeline.run_discovery("chargers judge facts topic", channel_id="tapin")
        self.assertTrue(judge.called)
        kwargs = judge.call_args.kwargs
        self.assertIn("ESPN NFL: Los Angeles Chargers 0-4", " ".join(kwargs.get("facts") or []))
        self.assertTrue(kwargs.get("today"))


class MenuBadgeTests(unittest.TestCase):
    def test_a_shared_score_prints_once(self):
        from core.ui import display_variants

        lines: list[str] = []
        display_variants(
            [(a, 95.0, {}) for a in ANGLES],
            raw_scores=dict.fromkeys(ANGLES, 95.0),
            angle_scores={ANGLES[0]: 0.82, ANGLES[1]: 0.61, ANGLES[2]: 0.2},
            print_fn=lambda *a, **_k: lines.append(" ".join(str(x) for x in a)),
        )
        text = "\n".join(lines)
        self.assertEqual(text.count("[95.0]"), 1, text)
        self.assertIn("[fit 0.82]", text)
        self.assertIn("every angle", text)

    def test_different_scores_keep_their_badges(self):
        from core.ui import display_variants

        lines: list[str] = []
        display_variants(
            [(ANGLES[0], 95.0, {}), (ANGLES[1], 83.0, {})],
            print_fn=lambda *a, **_k: lines.append(" ".join(str(x) for x in a)),
        )
        text = "\n".join(lines)
        self.assertIn("[95.0]", text)
        self.assertIn("[83.0]", text)


if __name__ == "__main__":
    unittest.main()
