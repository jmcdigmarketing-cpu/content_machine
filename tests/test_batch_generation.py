"""Tests for core/batch_generation.py — headless N-drafts batch.

Discovery, pipeline, facts, and observability are all mocked: no network, no
LLM spend, no real output/ or data/ writes.
"""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import batch_generation as bg

_EVALUATED = [
    ("Angle one", 55.0, {"youtube": {"score": 40}}),
    ("Angle two (best)", 82.0, {"youtube": {"score": 80}}),
    ("Angle three", 61.0, {"youtube": {"score": 50}}),
]


def _discovery():
    return SimpleNamespace(evaluated=list(_EVALUATED), channel_id="tapin", timings={})


def _pipeline_result(script="Hook line!\nBody line."):
    return SimpleNamespace(
        aborted=False,
        abort_reason=None,
        script=script,
        title="A Great Title",
        description="Desc.",
        tags=["ufc", "shorts"],
        run_id=42,
        features={"ungrounded_entities": ["Phantom Fighter"], "cost": {"total": 0.01}},
    )


class BatchCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patches = [
            patch("core.output_paths.channel_output_root", return_value=self._tmp.name),
            patch("core.fact_enrichment.enrich_facts", return_value=""),
            patch(
                "core.authenticity.evaluate_authenticity",
                return_value=SimpleNamespace(verdict="ok"),
            ),
            patch(
                "core.length_recommender.get_recommended_length",
                side_effect=RuntimeError("no analytics"),
            ),
            patch("core.pipeline.finalize_run_observability"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()


class TestCollectTopics(unittest.TestCase):
    def test_explicit_topics_win(self):
        out = bg.collect_topics("tapin", topics=[" a ", "", "b"], file="ignored", count=1)
        self.assertEqual(out, ["a", "b"])

    def test_file_lines_skip_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ideas.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("topic one\n\n# a comment\n topic two \n")
            self.assertEqual(bg.collect_topics("tapin", file=path), ["topic one", "topic two"])

    def test_best_bets_fallback(self):
        bets = [SimpleNamespace(topic="bet 1"), SimpleNamespace(topic="bet 2")]
        with patch("core.best_bet.get_best_bets", return_value=bets) as gb:
            out = bg.collect_topics("tapin", count=2)
        gb.assert_called_once_with("tapin", 2)
        self.assertEqual(out, ["bet 1", "bet 2"])

    def test_best_bets_unavailable_returns_empty(self):
        with patch("core.best_bet.get_best_bets", side_effect=RuntimeError("no db")):
            self.assertEqual(bg.collect_topics("tapin"), [])


class TestGenerateDraft(BatchCase):
    def test_happy_path_saves_draft_and_meta(self):
        with (
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", return_value=_pipeline_result()) as rp,
        ):
            out = bg.generate_draft("UFC 320", "tapin")

        self.assertTrue(out.ok)
        # Best-scoring variant picked, not the first.
        self.assertEqual(out.variant, "Angle two (best)")
        self.assertEqual(rp.call_args.kwargs["variant_index"], 1)
        self.assertEqual(rp.call_args.kwargs["length_choice"], "2")  # recommender down
        self.assertFalse(rp.call_args.kwargs["proceed_video"])
        self.assertEqual(out.title, "A Great Title")
        self.assertEqual(out.authenticity_verdict, "ok")
        self.assertEqual(out.ungrounded, ["Phantom Fighter"])
        self.assertIsNotNone(out.hook_score)  # real hook scorer, pure function

        draft_md = os.path.join(out.path, "draft.md")
        meta_json = os.path.join(out.path, "meta.json")
        self.assertTrue(os.path.exists(draft_md))
        with open(meta_json, encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["run_id"], 42)
        self.assertEqual(meta["variant"], "Angle two (best)")
        with open(draft_md, encoding="utf-8") as f:
            body = f.read()
        self.assertIn("Hook line!", body)
        self.assertIn("A Great Title", body)

    def test_headless_draft_passes_a_signal_corpus(self):
        signals = {
            "news": {
                "connected": True,
                "active": True,
                "data": {
                    "headlines": [{"title": "Rockstar Games filed subpoenas", "source": "wire"}]
                },
            }
        }
        discovery = SimpleNamespace(
            evaluated=[("GTA 6 leak", 80.0, signals)],
            channel_id="tapin",
            timings={},
        )
        with (
            patch("core.pipeline.run_discovery", return_value=discovery),
            patch("core.pipeline.run_pipeline", return_value=_pipeline_result()) as rp,
        ):
            bg.generate_draft(
                "GTA 6 leak",
                "tapin",
                key_facts=["Microsoft received the subpoena."],
            )
        corpus = rp.call_args.kwargs.get("relevance_corpus") or ""
        self.assertIn("Rockstar Games filed subpoenas", corpus)
        self.assertIn("Microsoft received the subpoena.", corpus)

    def test_empty_discovery_fails_cleanly(self):
        empty = SimpleNamespace(evaluated=[], channel_id="tapin", timings={})
        with patch("core.pipeline.run_discovery", return_value=empty):
            out = bg.generate_draft("UFC 320", "tapin")
        self.assertFalse(out.ok)
        self.assertIn("no scored variants", out.error)

    def test_aborted_pipeline_fails_cleanly(self):
        aborted = SimpleNamespace(
            aborted=True,
            abort_reason="LLM unavailable",
            script="",
            title="",
            description="",
            tags=[],
            run_id=None,
            features={},
        )
        with (
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", return_value=aborted),
        ):
            out = bg.generate_draft("UFC 320", "tapin")
        self.assertFalse(out.ok)
        self.assertEqual(out.error, "LLM unavailable")


class TestRunBatch(BatchCase):
    def test_one_failure_does_not_kill_the_batch(self):
        results = [RuntimeError("boom"), _pipeline_result()]

        def _pipeline(*a, **k):
            r = results.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with (
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", side_effect=_pipeline),
        ):
            outcomes = bg.run_batch("tapin", ["bad topic", "good topic"])

        self.assertEqual([o.ok for o in outcomes], [False, True])
        self.assertIn("boom", outcomes[0].error)
        summary = bg.render_summary(outcomes)
        self.assertIn("FAIL bad topic", summary)
        self.assertIn("1/2 drafts saved", summary)


class TestSlug(unittest.TestCase):
    def test_slug_normalises(self):
        self.assertEqual(bg._slug("UFC 320: Pereira vs. Ankalaev!!"), "ufc-320-pereira-vs-ankalaev")
        self.assertEqual(bg._slug("???"), "draft")


if __name__ == "__main__":
    unittest.main()
