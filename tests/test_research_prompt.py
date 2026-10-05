"""#965: the facts prompt says whether it needs the operator.

The key-facts prompt printed the same checklist on every run - "Cover the things that go
stale ... Who holds what NOW (champion, ranking, roster, CEO)" - whether the topic was
LeBron James (#963 now looks his team up) or a game released four days ago (#964 calls that
fresh). It now shows what was found and a verdict: settled says there is nothing to paste;
fresh names why and asks for a link. Pasting stays available either way. Headless drafts
carry the verdict, and `ops batch-review` names a fresh draft nobody pasted facts for.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import date
from unittest.mock import patch

from apis.signal_contract import make_signal
from tests.test_entity_lookup import TODAY as LOOKUP_TODAY
from tests.test_entity_lookup import _fake_get

NEWS = {"news": make_signal(connected=True, active=True, score=40, data={"headlines": []})}


def _prompt(topic, *, enabled=True, news_count=0):
    from core.ui import prompt_key_facts_result

    printed: list[str] = []
    env = {"ENTITY_RESEARCH_ENABLED": "true" if enabled else "false",
           "EVENT_RESEARCH_ENABLED": "false"}  # fmt: skip
    with (
        patch.dict(os.environ, env),
        patch("core.facts.entity_lookup.get_cached", return_value=None),
        patch("core.facts.entity_lookup.set_cache"),
        patch("core.facts.entity_lookup._today", return_value=LOOKUP_TODAY),
        patch("core.facts.entity_lookup.requests.get", side_effect=_fake_get),
        patch("core.facts.freshness.recent_news_count", return_value=news_count),
        patch("core.facts.freshness._today", return_value=date(2025, 10, 6)),
        patch("core.obsidian_facts.load_fact_records", return_value=[]),
    ):
        prompt_key_facts_result(
            topic,
            "tapin",
            signals=NEWS,
            print_fn=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
            input_fn=lambda *_: "",
        )
    return "\n".join(printed)


class PromptTests(unittest.TestCase):
    def test_a_settled_topic_says_nothing_to_paste(self):
        text = _prompt("Is LeBron James done?")
        self.assertIn("Who's who", text)
        self.assertIn("current team: Los Angeles Lakers", text)
        self.assertIn("Settled", text)
        self.assertIn("nothing to paste", text)
        self.assertNotIn("Who holds what NOW", text)

    def test_a_fresh_topic_asks_for_a_link(self):
        # The fixture game came out 2025-10-02; the clock reads 2025-10-06 here.
        text = _prompt("Ghost of Yotei first impressions")
        self.assertIn("Fresh", text)
        self.assertIn("released 2025-10-02", text)
        self.assertIn("link would help", text)

    def test_with_lookups_off_the_old_checklist_stays(self):
        text = _prompt("Is LeBron James done?", enabled=False)
        self.assertIn("Who holds what NOW", text)
        self.assertNotIn("Who's who", text)


class ReviewNoteTests(unittest.TestCase):
    def test_a_fresh_draft_nobody_pasted_for_is_named(self):
        from core.facts.freshness import review_note

        verdict = {"need": "fresh", "why": ["Ghost of Yōtei released 2026-10-01 (4 day(s) ago)"]}
        note = review_note(verdict, pasted=0)
        self.assertIn("fresh", note)
        self.assertIn("paste", note)
        self.assertEqual(review_note(verdict, pasted=3), "")
        self.assertEqual(review_note({"need": "settled", "why": []}, pasted=0), "")

    def test_batch_review_shows_it(self):
        from core.batch_review import PendingDraft, _show

        meta = {"run_id": 7, "title": "T", "research": {"need": "fresh", "why": ["new game"]},
                "key_facts_count": 0}  # fmt: skip
        printed: list[str] = []
        _show(PendingDraft(folder="/x", meta=meta, script="one two three"), 1, 1,
              lambda *a, **k: printed.append(" ".join(str(x) for x in a)))  # fmt: skip
        self.assertTrue(any("fresh" in line and "paste" in line for line in printed))


class DraftMetaTests(unittest.TestCase):
    def test_the_draft_keeps_the_verdict_and_the_paste_count(self):
        import tempfile
        from types import SimpleNamespace

        from core import batch_generation as bg
        from tests.test_batch_generation import _discovery

        result = SimpleNamespace(
            aborted=False, abort_reason=None, script="Hook line!\nBody.", title="T",
            description="D", tags=[], run_id=42,
            features={"research": {"need": "fresh", "why": ["new game"]}},
        )  # fmt: skip
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("core.output_paths.channel_output_root", return_value=tmp),
            patch("core.facts.enrichment.enrich_facts", return_value=""),
            patch("core.length_recommender.get_recommended_length", side_effect=RuntimeError),
            patch("core.pipeline.finalize_run_observability"),
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", return_value=result),
        ):
            out = bg.generate_draft("Ghost of Yotei", "tapin")
            with open(os.path.join(out.path, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        self.assertEqual(meta["research"]["need"], "fresh")
        self.assertEqual(meta["key_facts_count"], 0)


if __name__ == "__main__":
    unittest.main()
