"""#1086 / #1087: the two commands the operator ran after wave 67, made safe.

2026-10-10 on the PC: `verify-claim --run-id 120 --claim 1 --source "LINK" --apply` recorded
the literal placeholder "LINK" as the source of run 120's confirmation (the to-do list showed
LINK as the place to paste the link). And `go-public --channel tapin --apply`, with no video
id, made "the newest unlisted hold" - CGFtzpiA1so - public, printing only the id: neither the
run nor the title. The listing also showed no "this run's own research says" line for run 120,
whose research carried the claim: `flagged_claims` read only `auto_research.kept_lines`.
"""

from __future__ import annotations

import argparse
import copy
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord

CLAIM = "Claude Opus 5.5 dropped on September 22"


def _features(claim: str = CLAIM) -> dict:
    return {
        "claim_verification": {
            "total": 3,
            "supported": 2,
            "unsupported": [claim],
            "unsupported_types": ["date"],
            "claims": [{"claim": claim, "supported": False}],
        },
        "grounding_override": True,
    }


class SourceTests(unittest.TestCase):
    def test_a_placeholder_is_not_a_source(self):
        from core.facts.claim_confirm import source_problem

        for bad in ("LINK", "link", "<LINK>", "URL", "source", "TODO", "", "   ", "here"):
            self.assertTrue(source_problem(bad), bad)
        for good in ("https://www.anthropic.com/news", "anthropic.com/news",
                     "ESPN broadcast, Oct 5"):  # fmt: skip
            self.assertEqual(source_problem(good), "", good)

    def test_confirm_refuses_a_placeholder(self):
        from core.facts.claim_confirm import confirm_claim

        with (
            patch("core.facts.claim_confirm.load_features", return_value=_features()),
            patch("core.facts.claim_confirm.merge_features") as merge,
        ):
            result = confirm_claim(120, 1, source="LINK", dry_run=False)
        self.assertEqual(result.status, "invalid")
        self.assertIn("placeholder", result.detail)
        merge.assert_not_called()


class RelistTests(unittest.TestCase):
    def test_a_placeholder_confirmation_is_listed_again(self):
        from core.facts.claim_confirm import flagged_claims

        feats = {
            "claim_verification": {"unsupported": [], "claims": []},
            "claims_confirmed": [{"claim": CLAIM, "source": "LINK"}],
        }
        rows = flagged_claims(feats)
        self.assertEqual([r.claim for r in rows], [CLAIM])
        self.assertTrue(rows[0].needs_source)
        self.assertFalse(rows[0].blocking)

    def test_re_confirming_replaces_the_source(self):
        from core.facts.claim_confirm import confirm_claim

        store = {120: {"claims_confirmed": [{"claim": CLAIM, "source": "LINK"}]}}

        def merge(run_id, updates):
            store[run_id].update(copy.deepcopy(updates))

        with (
            patch("core.facts.claim_confirm.load_features",
                  side_effect=lambda r: copy.deepcopy(store[r])),
            patch("core.facts.claim_confirm.merge_features", side_effect=merge),
            patch("core.facts.claim_confirm.merge_quality"),
        ):  # fmt: skip
            result = confirm_claim(120, 1, source="https://www.anthropic.com/news", dry_run=False)
        self.assertEqual(result.status, "confirmed")
        sources = [row["source"] for row in store[120]["claims_confirmed"]]
        self.assertEqual(sources, ["https://www.anthropic.com/news"])


class ResearchLineTests(unittest.TestCase):
    def test_the_signal_snapshot_counts_as_the_runs_research(self):
        from core.facts.claim_confirm import run_flagged_claims

        snapshot = {
            "web_research": {
                "data": {"lines": ["Anthropic released Claude Opus 5.5 on September 22, 2026."]}
            },
            "web_search": {"data": {"answer": "unrelated", "results": [{"title": "x"}]}},
        }
        with (
            patch("core.facts.claim_confirm.load_features", return_value=_features()),
            patch("core.runs.replay.load_snapshot", return_value=snapshot),
        ):
            rows = run_flagged_claims(120)
        self.assertIn("September 22, 2026", rows[0].found_in)


def _row(rid, vid, run_id, privacy="unlisted"):
    return PublishLogRecord(
        id=rid,
        content_run_id=run_id,
        channel_id="tapin",
        youtube_video_id=vid,
        privacy_status=privacy,
        status="uploaded",
    )


class GoPublicNamingTests(unittest.TestCase):
    def _go(self, rows, video_id="", dry_run=True):
        from publishing import go_public

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        titles = {119: "Rakhmonov 19-0", 120: "AI mods blend games"}
        with (
            patch("publishing.go_public.load_features", return_value={}),
            patch("publishing.go_public._run_title", side_effect=lambda r: titles.get(r, "")),
        ):
            return go_public.apply_go_public(
                video_id, channel_id="tapin", dry_run=dry_run, repo=repo
            )

    def test_the_dry_run_names_the_run_and_title(self):
        result = self._go([_row(1, "CGFtzpiA1so", 120)])
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.run_id, 120)
        self.assertEqual(result.title, "AI mods blend games")
        self.assertIn("run 120", result.label)
        self.assertIn("AI mods blend games", result.label)

    def test_several_holds_and_no_id_is_refused_on_apply(self):
        rows = [_row(1, "old", 119), _row(2, "new", 120)]
        preview = self._go(rows)
        self.assertEqual(preview.status, "dry_run")
        self.assertEqual(preview.video_id, "new")
        self.assertEqual(len(preview.holds), 2)
        result = self._go(rows, dry_run=False)
        self.assertEqual(result.status, "invalid")
        self.assertIn("old", result.detail)
        self.assertIn("new", result.detail)

    def test_the_ops_verb_prints_the_name(self):
        from scripts import ops

        out = io.StringIO()
        with (
            redirect_stdout(out),
            patch("publishing.go_public.get_publish_log_repository", create=True),
            patch("publishing.go_public.apply_go_public") as go,
        ):
            from publishing.go_public import GoPublicResult

            go.return_value = GoPublicResult(
                "dry_run", "{}", "CGFtzpiA1so", run_id=120, title="AI mods blend games"
            )
            ops.COMMANDS["go-public"][1](
                argparse.Namespace(target="", channel="tapin", apply=False)
            )
        self.assertIn("run 120", out.getvalue())
        self.assertIn("AI mods blend games", out.getvalue())


if __name__ == "__main__":
    unittest.main()
