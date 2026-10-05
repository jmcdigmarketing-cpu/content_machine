"""#339: "unconfirmed" as a script mode for a fresh topic with thin facts.

Until now a claim the facts did not back had two fates: assert it, or the claim rewrite (#322)
drops it - and the description pass (#972) drops its sentence too. For a game out four days
ago with three fact lines, dropping leaves a script that says nothing about the news it is
about. Saying "this is not confirmed yet" is more honest and, under the 2026 policy, more
authentic. `core/facts/freshness.script_mode` reads the #964 verdict and the number of
verified fact lines: fresh with fewer than `UNCONFIRMED_MAX_FACTS` (5) -> "unconfirmed".

In that mode the script prompt asks for what is confirmed and what is not, labelled; the claim
rewrite restates an unbacked claim as unconfirmed instead of removing it; the description labels
such a sentence instead of dropping it. The mode is kept in the run's research verdict and
quality, and the dossier and `ops batch-review` name it.
"""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_status_from_memory import BASE


class ModeTests(unittest.TestCase):
    def test_fresh_and_thin_is_unconfirmed(self):
        from core.facts.freshness import script_mode

        self.assertEqual(script_mode({"need": "fresh"}, 2), "unconfirmed")
        self.assertEqual(script_mode({"need": "fresh"}, 8), "standard")
        self.assertEqual(script_mode({"need": "settled"}, 0), "standard")
        self.assertEqual(script_mode(None, 0), "standard")

    def test_the_threshold_can_be_set(self):
        from core.facts.freshness import script_mode

        with patch.dict(os.environ, {"UNCONFIRMED_MAX_FACTS": "10"}):
            self.assertEqual(script_mode({"need": "fresh"}, 8), "unconfirmed")


class PromptTests(unittest.TestCase):
    def test_the_prompt_says_what_is_confirmed_and_what_is_not(self):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(**BASE, script_mode="unconfirmed")
        text = system + user
        self.assertIn("UNCONFIRMED MODE", text)
        self.assertIn("not confirmed yet", text)

    def test_standard_mode_adds_nothing(self):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(**BASE)
        self.assertNotIn("UNCONFIRMED MODE", system + user)


class RewriteTests(unittest.TestCase):
    def _rewrite(self, mode):
        from core import content_engine

        claim = SimpleNamespace(claim="Ghost of Yotei sold 5 million copies")
        verification = SimpleNamespace(unsupported=[claim], total=3)
        with (
            patch.object(content_engine, "_claim_regen_enabled", return_value=True),
            patch.object(content_engine, "_call_content_llm",
                         return_value={"script": ""}) as llm,
        ):  # fmt: skip
            content_engine._maybe_rewrite_unsupported_claims(
                "Ghost of Yotei sold 5 million copies.", verification, "facts", "topic", [],
                script_mode=mode,
            )  # fmt: skip
        return llm.call_args.args[0]

    def test_unconfirmed_mode_restates_rather_than_removes(self):
        system = self._rewrite("unconfirmed")
        self.assertIn("not confirmed yet", system)
        self.assertIn("do not remove", system.lower())

    def test_standard_mode_is_unchanged(self):
        self.assertIn("REMOVED", self._rewrite("standard"))


class DescriptionTests(unittest.TestCase):
    def test_a_sentence_is_labelled_not_dropped(self):
        from core.youtube_meta import drop_unbacked_sentences

        desc = "Ghost of Yotei sold 5 million copies in three days. The open world is huge."
        got, dropped = drop_unbacked_sentences(
            desc, ["Ghost of Yotei sold 5 million copies"], label="Not confirmed yet:"
        )
        self.assertEqual(
            got,
            "Not confirmed yet: Ghost of Yotei sold 5 million copies in three days. "
            "The open world is huge.",
        )
        self.assertEqual(len(dropped), 1)


class RecordTests(unittest.TestCase):
    def test_the_mode_choice_reads_the_verdict_and_the_fact_lines(self):
        from core.content_engine import _script_mode_for

        thin = "- Ghost of Yotei released 2026-10-02\n- Developer: Sucker Punch"
        self.assertEqual(_script_mode_for({"need": "fresh"}, thin, []), "unconfirmed")
        self.assertEqual(_script_mode_for({"need": "fresh"}, thin, ["a", "b", "c"]), "standard")
        self.assertEqual(_script_mode_for(None, thin, []), "standard")

    def test_quality_and_the_dossier_name_it(self):
        from core.run_ledger import render_dossier
        from core.run_quality import build_quality

        features = {"research": {"need": "fresh", "script_mode": "unconfirmed",
                                 "why": ["released 4 days ago"]}}  # fmt: skip
        quality = build_quality(script="A short script about a new game.", features=features,
                                channel_id="tapin")  # fmt: skip
        self.assertEqual(quality["script_mode"], "unconfirmed")
        record = SimpleNamespace(
            id=7, channel_id="tapin", status="done", selected_topic="t", input_topic="t",
            title="T", composite_score=50.0, abort_reason="", features_json="{}",
            quality_json=json.dumps(quality), timings_json="{}")  # fmt: skip
        with patch("storage.repositories.content_runs.get_content_run_repository",
                   return_value=type("Repo", (), {"get": lambda self, i: record})()):  # fmt: skip
            self.assertIn("script mode: unconfirmed", render_dossier(7))

    def test_batch_review_names_it(self):
        from core.batch_review import PendingDraft, _show

        meta = {"run_id": 7, "title": "T", "key_facts_count": 2,
                "research": {"need": "fresh", "why": ["new game"],
                             "script_mode": "unconfirmed"}}  # fmt: skip
        printed: list[str] = []
        _show(PendingDraft(folder="/x", meta=meta, script="one two three"), 1, 1,
              lambda *a, **k: printed.append(" ".join(str(x) for x in a)))  # fmt: skip
        self.assertTrue(any("unconfirmed" in line for line in printed))

    def test_the_pipeline_keeps_it_in_the_verdict(self):
        with patch("core.pipeline.generate_content_package") as content:
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": [],
                                    "script_mode": "unconfirmed"}  # fmt: skip
            result = _run_pipeline()
        self.assertEqual(result.features["research"]["script_mode"], "unconfirmed")
        self.assertEqual(content.call_args.kwargs["research_need"]["need"],
                         result.features["research"]["need"])  # fmt: skip


def _run_pipeline():
    from unittest.mock import MagicMock

    from apis.signal_contract import make_signal
    from core.pipeline import DiscoveryResult, run_pipeline

    topic = "Ghost of Yotei review"
    signals = {"news": make_signal(connected=True, active=True, score=40, data={"headlines": []})}
    discovery = DiscoveryResult(input_topic=topic, base_signals=signals,
                                evaluated=[(topic, 90.0, signals)], channel_id="tapin")  # fmt: skip
    with (
        patch("core.pipeline.write_run_trace"),
        patch("core.pipeline.persist_quality"),
        patch("core.pipeline.build_quality", return_value={}),
        patch("core.pipeline.record_learning_outcome"),
        patch("core.pipeline.record_content_run", return_value=42),
        patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
    ):
        return run_pipeline(topic, discovery=discovery, variant_index=0, proceed_video=False,
                            channel_id="tapin")  # fmt: skip


if __name__ == "__main__":
    unittest.main()
