"""Wave 18: batch for 3-5 a week, claim types, chapter measurement, labels, franchise pages.

Operator calls 2026-09-16: retire the five stale renders; one-pass morning review of the
overnight drafts; spaced uploads go public at their slot (never a run forced past the
grounding gate); a hedged rumor warns while a result/award/stat always blocks. Each test here
failed on unmodified d2790d2.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUN76_SEED = (
    "GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting "
    "the hype mean, is a goy candidate a failure? Long form predictions and content "
    "analysis so far"
)
_TAIL_WORDS = {"is", "the", "a", "an", "of", "and", "to", "that", "not", "in", "for", "with"}


# --- #756 chapter labels ------------------------------------------------------------


class TestChapterLabelsEndOnAPhrase(unittest.TestCase):
    """Run 77 after #750: "The only reason we know anything is", "...today is not the"."""

    def test_run_77_labels_do_not_end_on_a_dangling_word(self):
        from core.chapters import _label

        for sentence in (
            "The only reason we know anything is that Rockstar keeps leaking it on purpose.",
            "The gaming audience today is not the audience that bought GTA 5 in 2013.",
        ):
            with self.subTest(sentence=sentence):
                label = _label(sentence)
                self.assertLessEqual(len(label), 40)
                self.assertNotIn(label.split()[-1].lower(), _TAIL_WORDS, label)
                self.assertGreaterEqual(len(label.split()), 3, label)

    def test_a_clause_is_preferred_to_a_word_cut(self):
        from core.chapters import _label

        label = _label("Online is the real product, and the story mode is the trailer for it.")
        self.assertEqual(label, "Online is the real product")

    def test_short_sentences_are_untouched(self):
        from core.chapters import _label

        self.assertEqual(_label("Price is the whole story."), "Price is the whole story")


# --- #749 franchise pages -----------------------------------------------------------


class TestWikipediaFranchisePages(unittest.TestCase):
    def test_run_76_seed_asks_for_the_game_page_first(self):
        from apis.wikipedia_pageviews_api import _article_candidates

        self.assertEqual(_article_candidates(RUN76_SEED)[0], "Grand_Theft_Auto_VI")

    def test_other_known_franchises_map_to_their_pages(self):
        from apis.wikipedia_pageviews_api import _article_candidates

        self.assertIn("Grand_Theft_Auto_V", _article_candidates("GTA V online still prints money"))
        self.assertIn("Grand_Theft_Auto_VI", _article_candidates("Grand Theft Auto VI trailer 3"))
        self.assertIn("Ultimate_Fighting_Championship", _article_candidates("UFC 320"))
        # the #746 guarantees still hold
        self.assertIn("UFC_320", _article_candidates("UFC 320"))
        self.assertNotIn("Grand_Theft_Auto_V", _article_candidates(RUN76_SEED))


# --- #345 claim types ---------------------------------------------------------------


def _typed(rows):
    return {
        "total": len(rows),
        "supported": 0,
        "unsupported": [claim for claim, _type in rows],
        "unsupported_types": [claim_type for _claim, claim_type in rows],
        "claims": [{"claim": c, "supported": False, "type": t} for c, t in rows],
    }


class TestClaimTypes(unittest.TestCase):
    GOTY = "GTA 5 didn't win Game of the Year in 2013."
    RUMOR = "GTA 6 is reportedly getting a second trailer before the holidays."

    def test_run_77_award_claim_blocks(self):
        from core.claim_verifier import gate_blocks

        self.assertTrue(gate_blocks(_typed([(self.GOTY, "award")])))

    def test_a_hedged_rumor_warns_but_does_not_block(self):
        from core.claim_types import blocking_unsupported, warn_only_unsupported
        from core.claim_verifier import gate_blocks

        verification = _typed([(self.RUMOR, "rumor")])
        self.assertFalse(gate_blocks(verification))
        self.assertEqual(blocking_unsupported(verification), [])
        self.assertEqual(warn_only_unsupported(verification), [self.RUMOR])

    def test_an_unhedged_rumor_blocks(self):
        from core.claim_verifier import gate_blocks

        self.assertTrue(gate_blocks(_typed([("GTA 6 gets a second trailer next week.", "rumor")])))

    def test_opinion_never_blocks_unless_it_carries_a_number(self):
        from core.claim_verifier import gate_blocks

        self.assertFalse(gate_blocks(_typed([("Online is the real product.", "opinion")])))
        self.assertTrue(gate_blocks(_typed([(self.GOTY, "opinion")])))

    def test_untyped_rows_stay_strict(self):
        from core.claim_verifier import gate_blocks

        self.assertTrue(gate_blocks({"total": 1, "supported": 0, "unsupported": [self.RUMOR]}))

    def test_verifier_persists_the_type(self):
        from core.claim_verifier import verify_claims

        payload = {"claims": [{"claim": self.GOTY, "supported": False, "type": "award"}]}
        with (
            patch.dict(os.environ, {"CLAIM_VERIFIER_ENABLED": "true"}),
            patch("core.llm_router.complete_json", return_value=payload) as call,
        ):
            verification = verify_claims("script text", "- a fact", topic="GTA")
        self.assertIsNotNone(verification)
        data = verification.to_dict()
        self.assertEqual(data["claims"][0]["type"], "award")
        self.assertEqual(data["unsupported_types"], ["award"])
        self.assertIn('"type"', call.call_args.kwargs["system"])

    def test_override_and_publish_list_name_the_type(self):
        from core.claim_verifier import override_features
        from core.publish_blockers import blocking_publish_reasons

        features = override_features(_typed([(self.RUMOR, "rumor"), (self.GOTY, "award")]))
        self.assertEqual(features["grounding_override_claims"], [self.GOTY])
        self.assertEqual(features["grounding_override_types"], ["award"])
        blob = " ".join(blocking_publish_reasons(features=features))
        self.assertIn("award", blob)

    def test_display_marks_warn_only_rumors(self):
        from core.claim_verifier import display_claim_verification

        lines: list[str] = []
        display_claim_verification(
            _typed([(self.RUMOR, "rumor"), (self.GOTY, "award")]),
            print_fn=lambda *a: lines.append(" ".join(str(x) for x in a)),
        )
        blob = "\n".join(lines)
        self.assertIn("[award]", blob)
        self.assertIn("warn only", blob.lower())


# --- #755 chapter measurement -------------------------------------------------------


class TestChapterMeasurement(unittest.TestCase):
    SCRIPT = (
        "Rockstar sells the map first. Every trailer shows land, not missions. "
        "Online is where the money lives. Shark cards funded a decade of updates. "
        "The story mode is a trailer for Online. Players buy the world, then stay."
    )
    ANGLES = ("The map is the product", "Online is the money", "Story sells Online")

    def test_locate_chapters_records_the_keyword_path(self):
        from core.angle_chapters import locate_chapters

        with patch("core.angle_chapters._llm_chapter_starts", return_value=None):
            chapters = locate_chapters(self.SCRIPT, list(self.ANGLES))
        self.assertEqual({c.placed_by for c in chapters}, {"keyword"})

    def test_locate_chapters_records_the_llm_path_and_round_trips(self):
        from core.angle_chapters import (
            chapters_from_features,
            features_from_chapters,
            locate_chapters,
        )

        starts = [0, self.SCRIPT.index("Online is"), self.SCRIPT.index("The story")]
        with patch("core.angle_chapters._llm_chapter_starts", return_value=starts):
            chapters = locate_chapters(self.SCRIPT, list(self.ANGLES))
        restored = chapters_from_features(features_from_chapters(chapters))
        self.assertEqual([c.placed_by for c in restored], ["llm"] * 3)
        self.assertEqual(
            chapters_from_features([{"title": "old", "word_start": 0}])[0].placed_by, ""
        )

    def test_report_lines_show_path_length_and_cap(self):
        from core.angle_chapters import AngleChapter
        from core.chapter_shorts import ChapterSpan, chapter_report_lines

        chapters = [
            AngleChapter(0, "The map is the product", "a", 0, placed_by="llm"),
            AngleChapter(1, "Online is the money", "b", 40, placed_by="llm"),
        ]
        spans = [
            ChapterSpan(0, "The map is the product", "a", 3.0, 164.0, "x"),
            ChapterSpan(1, "Online is the money", "b", 164.0, 366.0, "y"),
        ]
        lines = chapter_report_lines(chapters, spans)
        self.assertIn("[llm]", lines[0])
        self.assertIn("2:41", lines[0])
        self.assertIn("fits", lines[0])
        self.assertIn("3:22", lines[1])
        self.assertIn("over", lines[1])

    def test_menu_and_ops_use_the_report(self):
        self.assertIn("chapter_report(", (ROOT / "main.py").read_text(encoding="utf-8"))
        ops = (ROOT / "scripts" / "ops.py").read_text(encoding="utf-8")
        self.assertIn('_register("chapters"', ops)


# --- #760 public at slot ------------------------------------------------------------


class TestPublicAtSlot(unittest.TestCase):
    WHEN = datetime(2026, 9, 17, 22, 0, tzinfo=timezone.utc)

    def _queue(self, features: dict, parent_features: dict | None = None):
        from core.spaced_queue import SpacedSlot, queue_spaced_uploads

        record = SimpleNamespace(
            id=301,
            channel_id="tapin",
            title="One",
            description="d",
            tags_json="[]",
            mp4_path=__file__,
            features_json=json.dumps(features),
        )
        repo = SimpleNamespace(get=lambda run_id: record)
        slot = SpacedSlot(run_id=301, title="One", publish_at=self.WHEN)
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.spaced_queue.load_features", return_value=parent_features or {}),
            patch("core.spaced_queue.enqueue_repurpose_jobs") as enqueue,
        ):
            queue_spaced_uploads([slot], channel_id="tapin")
        return enqueue.call_args.kwargs["privacy_status"], slot

    def test_a_clean_run_goes_public_at_its_slot(self):
        privacy, slot = self._queue({})
        self.assertEqual(privacy, "public")
        self.assertEqual(slot.privacy, "public")

    def test_an_override_run_stays_unlisted(self):
        privacy, _slot = self._queue({"grounding_override": True})
        self.assertEqual(privacy, "unlisted")

    def test_a_short_of_an_override_parent_stays_unlisted(self):
        privacy, _slot = self._queue({"parent_run_id": 77}, {"grounding_override": True})
        self.assertEqual(privacy, "unlisted")


# --- #760 stale renders -------------------------------------------------------------


class TestRetireStaleRenders(unittest.TestCase):
    def test_old_unuploaded_renders_are_found_and_skipped_once_retired(self):
        from core import stale_renders

        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp, "old.mp4")
            new = Path(tmp, "new.mp4")
            old.write_bytes(b"x")
            new.write_bytes(b"x")
            month_ago = time.time() - 60 * 86400
            os.utime(old, (month_ago, month_ago))
            runs = [
                SimpleNamespace(id=1, mp4_path=str(old), title="UFC 250", features_json="{}"),
                SimpleNamespace(id=2, mp4_path=str(new), title="GTA 6", features_json="{}"),
            ]
            merged: dict[int, dict] = {}
            with (
                patch("scripts.requeue_upload.list_recyclable", return_value=runs),
                patch(
                    "core.stale_renders.merge_features",
                    side_effect=lambda run_id, updates: merged.setdefault(run_id, updates),
                ),
            ):
                stale = stale_renders.find_stale_renders("tapin", days=30)
                self.assertEqual([r.id for r in stale], [1])
                self.assertEqual(stale_renders.retire_renders(stale), [1])
        self.assertIn("retired_at", merged[1])

    def test_list_recyclable_skips_a_retired_run(self):
        from scripts import requeue_upload

        runs = [
            SimpleNamespace(
                id=1, status="rendered", mp4_path=__file__, features_json='{"retired_at": "x"}'
            ),
            SimpleNamespace(id=2, status="rendered", mp4_path=__file__, features_json="{}"),
        ]
        repo = SimpleNamespace(list_for_channel=lambda channel_id: runs)
        with (
            patch.object(requeue_upload, "get_content_run_repository", return_value=repo),
            patch.object(requeue_upload, "_is_uploaded", return_value=False),
        ):
            self.assertEqual([r.id for r in requeue_upload.list_recyclable("tapin")], [2])


# --- #760 batch review --------------------------------------------------------------


def _draft(root: Path, name: str, *, topic: str, run_id: int, review=None, claims=None):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "draft.md").write_text(
        f"# Title {run_id}\n\n**Topic:** {topic}\n\n## Script\n\nLine one. Line two.\n\n"
        "## Description\n\nDesc\n",
        encoding="utf-8",
    )
    meta = {
        "topic": topic,
        "variant": topic,
        "title": f"Title {run_id}",
        "run_id": run_id,
        "channel_id": "tapin",
        "hook_score": 7,
        "hook_verdict": "ok",
        "authenticity_verdict": "pass",
        "length_choice": "2",
        "claim_verification": claims,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    if review is not None:
        meta["review"] = review
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


class TestBatchReview(unittest.TestCase):
    def test_pending_skips_reviewed_but_keeps_accepted_unrendered(self):
        from core.batch_review import pending_drafts

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "a", topic="A", run_id=1)
            _draft(root, "b", topic="B", run_id=2, review={"decision": "rejected"})
            _draft(root, "c", topic="C", run_id=3, review={"decision": "accepted"})
            _draft(root, "d", topic="D", run_id=4, review={"decision": "rendered"})
            pending = pending_drafts("tapin", root=str(root))
        self.assertEqual(sorted(d.run_id for d in pending), [1, 3])
        self.assertEqual(pending[0].script, "Line one. Line two.")

    def test_one_pass_review_renders_accepted_and_spaces_them(self):
        from core.batch_review import review_drafts

        blocked = _typed([("GTA 5 didn't win Game of the Year in 2013.", "award")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "1-a", topic="A", run_id=11)
            _draft(root, "2-b", topic="B", run_id=12)
            _draft(root, "3-c", topic="C", run_id=13, claims=blocked)
            answers = iter(["y", "n", "hook", "y", "no thanks"])
            rendered: list[int] = []
            slot = SimpleNamespace(run_id=11, title="Title 11", publish_at=datetime(2026, 9, 18))
            with (
                patch(
                    "core.batch_review._render",
                    side_effect=lambda draft, override: rendered.append(draft.run_id) or True,
                ),
                patch("core.batch_review.plan_spaced_uploads", return_value=[slot]) as plan,
                patch("core.batch_review.queue_spaced_uploads", return_value=[11]) as queue,
            ):
                summary = review_drafts(
                    "tapin",
                    root=str(root),
                    ask=lambda prompt: next(answers),
                    print_fn=lambda *a: None,
                )
            metas = {
                p.parent.name: json.loads(p.read_text(encoding="utf-8"))
                for p in root.glob("*/meta.json")
            }
        self.assertEqual(rendered, [11])
        self.assertEqual(plan.call_args.args[0], [(11, "Title 11")])
        queue.assert_called_once()
        self.assertEqual(summary.queued, [11])
        self.assertEqual(metas["1-a"]["review"]["decision"], "rendered")
        self.assertEqual(metas["2-b"]["review"]["decision"], "rejected")
        # a blocking claim without typing `force` is left for later, not accepted
        self.assertNotIn("review", metas["3-c"])

    def test_force_records_the_grounding_override(self):
        from core.batch_review import review_drafts

        blocked = _typed([("GTA 5 didn't win Game of the Year in 2013.", "award")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "a", topic="A", run_id=21, claims=blocked)
            answers = iter(["y", "force"])
            overrides: list[bool] = []
            with (
                patch(
                    "core.batch_review._render",
                    side_effect=lambda draft, override: overrides.append(override) or True,
                ),
                patch("core.batch_review.plan_spaced_uploads", return_value=[]),
                patch("core.batch_review.queue_spaced_uploads", return_value=[]),
            ):
                review_drafts(
                    "tapin", root=str(root), ask=lambda p: next(answers), print_fn=lambda *a: None
                )
        self.assertEqual(overrides, [True])

    def test_batch_does_not_repay_for_an_unreviewed_draft(self):
        from core import batch_generation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "a", topic="GTA 6 Online", run_id=31)
            with (
                patch.object(batch_generation, "_drafts_dir", return_value=str(root)),
                patch.object(batch_generation, "generate_draft") as generate,
                patch("apis.register_signals.franchise_batch_cache"),
                patch("core.pipeline.finalize_run_observability"),
                patch("core.events.emit_event"),
            ):
                outcomes = batch_generation.run_batch("tapin", ["gta 6 online", "UFC 320"])
        generated = [call.args[0] for call in generate.call_args_list]
        self.assertEqual(generated, ["UFC 320"])
        self.assertTrue(outcomes[0].reused)
        self.assertEqual(outcomes[0].run_id, 31)

    def test_ops_wires_review_and_retire(self):
        ops = (ROOT / "scripts" / "ops.py").read_text(encoding="utf-8")
        self.assertIn('_register("batch-review"', ops)
        self.assertIn('_register("retire-renders"', ops)


if __name__ == "__main__":
    unittest.main()
