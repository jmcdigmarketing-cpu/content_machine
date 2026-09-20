"""#806: a rejected draft must record why, in one keystroke.

The operator has rejected six drafts in two weeks and every reason lives as
prose in planning_log.md. `ops batch-review` already writes `review.decision`
into the draft's meta.json; it never asks why. That column is the only
operator-labelled dataset this project could have.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from core.batch_review import review_drafts


def _draft(root: Path, name: str, *, topic: str, run_id: int) -> Path:
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
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


def _meta(root: Path, name: str) -> dict:
    return json.loads((root / name / "meta.json").read_text(encoding="utf-8"))


class TestRejectionReason(unittest.TestCase):
    def test_rejecting_with_n_then_hook_persists_the_reason(self) -> None:
        """Unmodified review_drafts writes decision=rejected and never asks why."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "a", topic="A", run_id=88)
            answers = iter(["n", "hook"])
            with patch("core.batch_review._render"):
                summary = review_drafts(
                    "tapin",
                    root=str(root),
                    ask=lambda prompt: next(answers),
                    print_fn=lambda *a: None,
                )
            review = _meta(root, "a")["review"]
        self.assertEqual(summary.rejected, [88])
        self.assertEqual(review["decision"], "rejected")
        self.assertEqual(review["reason"], "hook")

    def test_an_unknown_or_empty_keystroke_is_other_not_a_blocked_reject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "a", topic="A", run_id=89)
            _draft(root, "b", topic="B", run_id=90)
            answers = iter(["n", "", "n", "xyz"])
            with patch("core.batch_review._render"):
                review_drafts(
                    "tapin",
                    root=str(root),
                    ask=lambda prompt: next(answers),
                    print_fn=lambda *a: None,
                )
            self.assertEqual(_meta(root, "a")["review"]["reason"], "other")
            self.assertEqual(_meta(root, "b")["review"]["reason"], "other")

    def test_enter_for_later_does_not_write_a_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _draft(root, "a", topic="A", run_id=91)
            answers = iter([""])
            with patch("core.batch_review._render"):
                summary = review_drafts(
                    "tapin",
                    root=str(root),
                    ask=lambda prompt: next(answers),
                    print_fn=lambda *a: None,
                )
            meta = _meta(root, "a")
        self.assertEqual(summary.later, [91])
        self.assertNotIn("review", meta)


if __name__ == "__main__":
    unittest.main()
