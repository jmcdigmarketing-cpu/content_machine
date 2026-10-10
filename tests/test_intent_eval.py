"""#1094: every idea the operator has typed reads the way it was meant, and keeps its angles.

Planned 2026-10-10 ("anything else we can plan when it comes to topic to angle
miscommunication?"). The intent table is a lexicon, and nothing pinned how the operator's own
past ideas must read - a cue added for one run could quietly break another. The table lives in
`tests/fixtures/intent_eval.json`; every angle complaint adds a row. A row with `needs` waits
for that backlog item and is enforced once the item is ticked in `docs/backlog.md`.

Measured on 6b5f648: "Jets are doomed" read neutral and its own agreeing angle was dropped as
mockery (#1090); "Is there any hope for the Jets?" read neutral because `_NO_HOPE` took "any
hope" for "no hope".
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "tests" / "fixtures" / "intent_eval.json"


def _rows() -> list[dict]:
    return json.loads(TABLE.read_text(encoding="utf-8"))["rows"]


def _done(item: str) -> bool:
    backlog = (ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    return bool(re.search(rf"^- \[x\] {re.escape(item)}\.", backlog, re.M))


class IntentEvalTests(unittest.TestCase):
    def _enforced(self) -> list[dict]:
        return [r for r in _rows() if not r.get("needs") or _done(str(r["needs"]))]

    def test_every_idea_reads_as_meant(self):
        from core.angle_intent import detect_angle_intent

        wrong = [
            f"{r['idea']!r} ({r['source']}): {detect_angle_intent(r['idea'])}, want {r['intent']}"
            for r in self._enforced()
            if not r.get("phrase") and detect_angle_intent(r["idea"]) != r["intent"]
        ]
        self.assertEqual(wrong, [])

    def test_slang_rows_read_through_the_model(self):
        """#1089: a `phrase` row is slang the cue words miss; the model naming that phrase
        must carry the run (a read naming words the idea lacks is refused - see
        tests/test_model_stance_read.py). The real model's agreement is `ops intent-check
        --table`, on the PC."""
        import json
        import os
        from unittest.mock import patch

        from core.angle_intent import detect_angle_intent, reset_model_reads, resolve_intent

        wrong: list[str] = []
        for row in [r for r in self._enforced() if r.get("phrase")]:
            mode = {"default": "neutral"}.get(row["intent"], row["intent"])
            reply = json.dumps({"mode": mode, "phrase": row["phrase"]})
            reset_model_reads()
            with (
                patch.dict(os.environ, {"STANCE_MODEL_READ": "true"}),
                patch("core.llm_router.complete", return_value=reply),
            ):
                read = resolve_intent(row["idea"])
            if (read.intent, read.cue) != (row["intent"], row["phrase"]):
                wrong.append(f"{row['idea']!r}: {read.intent} [{read.cue}]")
            if detect_angle_intent(row["idea"]) == row["intent"]:
                wrong.append(f"{row['idea']!r} now reads by cue - drop its phrase")
        reset_model_reads()
        self.assertEqual(wrong, [])

    def test_angles_kept_and_dropped(self):
        from core.angle_intent import stance_flip

        wrong: list[str] = []
        for row in self._enforced():
            for angle in row.get("keep") or []:
                reason = stance_flip(angle, row["intent"], idea=row["idea"])
                if reason:
                    wrong.append(f"{row['idea']!r} dropped {angle!r}: {reason}")
            for angle in row.get("drop") or []:
                if not stance_flip(angle, row["intent"], idea=row["idea"]):
                    wrong.append(f"{row['idea']!r} kept {angle!r}")
        self.assertEqual(wrong, [])

    def test_the_table_covers_the_record(self):
        rows = _rows()
        sources = " ".join(r["source"] for r in rows)
        for run in ("run 73", "run 113", "run 118", "run 124", "run 125"):
            self.assertIn(run, sources)
        self.assertEqual(len({r["idea"] for r in rows}), len(rows), "an idea is listed twice")
        for row in rows:
            self.assertIn(row["intent"], _intents(), row["idea"])

    def test_a_waiting_row_names_a_real_item(self):
        backlog = (ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
        for row in _rows():
            if row.get("needs"):
                self.assertRegex(backlog, rf"(?m)^- \[[ x]\] {row['needs']}\.", row["idea"])


def _intents() -> tuple[str, ...]:
    from core.angle_intent import ALL_INTENTS

    return ALL_INTENTS


if __name__ == "__main__":
    unittest.main()
