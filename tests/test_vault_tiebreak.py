"""P4 extract-tier tiebreak for operator-facing uncertain vault facts.

Measured: scored mode on the frozen eval set leaves 4/14 cases in the
uncertain band (holdout 2/4). The tiebreak is default-off, free-first, and
must never run from public Sources: or web-search skip.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.obsidian_facts import load_fact_records

TOPIC = "GTA 6 Leak and Wolverine Rage Signal a Cultural Backlash"
CORPUS = (
    "To find the Grand Theft Auto 6 leaker, the parent company of Rockstar Games "
    "has resorted to filing subpoenas in a US court to force Microsoft and Discord "
    "to hand over their records."
)
OTHER_CORPUS = CORPUS + " Discord was named in the same filing."
BULLET = "The subpoena demands account IDs and last-login IP addresses."


def _write_note(root: Path) -> None:
    (root / "gta6-subpoenas.md").write_text(
        "---\nchannel: tapin\ntier: link\ntags: [facts]\n---\n" "# GTA 6 leak\n" f"- {BULLET}\n",
        encoding="utf-8",
    )


class TestOperatorTiebreak(unittest.TestCase):
    def setUp(self):
        from core.vault_relevance import reset_tiebreak_cache

        reset_tiebreak_cache()

    def test_tiebreak_off_by_default_does_not_call_the_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                        "VAULT_RELEVANCE_MODE": "scored",
                    },
                    clear=False,
                ),
                patch("core.llm_router.complete_json") as llm,
            ):
                records = load_fact_records(TOPIC, "tapin", corpus=CORPUS, require_distinctive=True)
        rec = next(r for r in records if BULLET in r.claim)
        self.assertEqual(rec.relevance_band, "uncertain")
        llm.assert_not_called()

    def test_enabled_tiebreak_promotes_and_keeps_the_pre_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                        "VAULT_RELEVANCE_MODE": "scored",
                        "VAULT_RELEVANCE_TIEBREAK": "true",
                    },
                    clear=False,
                ),
                patch(
                    "core.llm_router.complete_json",
                    return_value={"band": "confident", "reason": "same investigation"},
                ) as llm,
            ):
                records = load_fact_records(TOPIC, "tapin", corpus=CORPUS, require_distinctive=True)
        rec = next(r for r in records if BULLET in r.claim)
        self.assertEqual(rec.relevance_band, "confident")
        self.assertEqual(rec.relevance_pre_tiebreak_band, "uncertain")
        self.assertEqual(rec.relevance_tiebreak_status, "ok")
        llm.assert_called_once()
        self.assertEqual(llm.call_args.kwargs.get("tier"), "extract")

    def test_tiebreak_reuses_cache_for_the_same_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            env = {
                "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                "VAULT_RELEVANCE_MODE": "scored",
                "VAULT_RELEVANCE_TIEBREAK": "true",
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch(
                    "core.llm_router.complete_json",
                    return_value={"band": "confident", "reason": "same"},
                ) as llm,
            ):
                load_fact_records(TOPIC, "tapin", corpus=CORPUS, require_distinctive=True)
                load_fact_records(TOPIC, "tapin", corpus=CORPUS, require_distinctive=True)
        self.assertEqual(llm.call_count, 1)

    def test_tiebreak_cache_invalidates_when_the_corpus_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            env = {
                "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                "VAULT_RELEVANCE_MODE": "scored",
                "VAULT_RELEVANCE_TIEBREAK": "true",
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch(
                    "core.llm_router.complete_json",
                    return_value={"band": "uncertain", "reason": "unclear"},
                ) as llm,
            ):
                first = load_fact_records(TOPIC, "tapin", corpus=CORPUS, require_distinctive=True)
                second = load_fact_records(
                    TOPIC, "tapin", corpus=OTHER_CORPUS, require_distinctive=True
                )
        rec1 = next(r for r in first if BULLET in r.claim)
        rec2 = next(r for r in second if BULLET in r.claim)
        self.assertEqual(rec1.relevance_band, "uncertain")
        self.assertEqual(rec2.relevance_band, "uncertain")
        self.assertEqual(llm.call_count, 2)

    def test_tiebreak_failure_keeps_uncertain_and_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                        "VAULT_RELEVANCE_MODE": "scored",
                        "VAULT_RELEVANCE_TIEBREAK": "true",
                    },
                    clear=False,
                ),
                patch(
                    "core.llm_router.complete_json",
                    side_effect=RuntimeError("router down"),
                ),
            ):
                records = load_fact_records(TOPIC, "tapin", corpus=CORPUS, require_distinctive=True)
        rec = next(r for r in records if BULLET in r.claim)
        self.assertEqual(rec.relevance_band, "uncertain")
        self.assertEqual(rec.relevance_pre_tiebreak_band, "uncertain")
        self.assertEqual(rec.relevance_tiebreak_status, "failed")

    def test_public_policy_never_invokes_the_tiebreak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                        "VAULT_RELEVANCE_MODE": "scored",
                        "VAULT_RELEVANCE_TIEBREAK": "true",
                    },
                    clear=False,
                ),
                patch("core.llm_router.complete_json") as llm,
            ):
                load_fact_records(
                    TOPIC,
                    "tapin",
                    corpus=CORPUS,
                    require_distinctive=True,
                    relevance_policy="public",
                )
        llm.assert_not_called()

    def test_web_skip_policy_never_invokes_the_tiebreak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault" / "tapin"
            root.mkdir(parents=True)
            _write_note(root)
            with (
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": str(Path(tmp) / "vault"),
                        "VAULT_RELEVANCE_MODE": "scored",
                        "VAULT_RELEVANCE_TIEBREAK": "true",
                    },
                    clear=False,
                ),
                patch("core.llm_router.complete_json") as llm,
            ):
                load_fact_records(
                    TOPIC,
                    "tapin",
                    corpus=CORPUS,
                    require_distinctive=True,
                    relevance_policy="web_skip",
                )
        llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
