"""#1013: confirm a flagged claim without a re-render.

Runs 119 and 120 were rendered past the grounding gate and locked unlisted for claims the
operator could settle in a minute - run 120's "Claude Opus 5.5 dropped on September 22" is in
its own auto-research text. Nothing recorded an operator's confirmation, so the only way out
was a re-render that pays for the voice again ($0.84 and $1.33). The hold is the run's
`grounding_override` feature, read by `go_public.override_held`, a duplicate in
`spaced_queue._override_held`, `publish_blockers` and `hold_flagged_schedule`.

`core.facts.claim_confirm` lists a run's flagged claims (with the line of the run's own
research that carries each), records a confirmation and its source, recomputes the claim
counts and the grade, and releases the hold when no blocking claim is left; a rejected claim
lists the sentence to cut. `ops verify-claim` drives it; nothing is written without --apply.
"""

from __future__ import annotations

import argparse
import copy
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

CLAIM = "Claude Opus 5.5 dropped on September 22"
OTHER = "The mod scene doubled in size this year"
SOURCE = "https://www.anthropic.com/news"


def _verification(*claims: str) -> dict:
    return {
        "total": 6,
        "supported": 6 - len(claims),
        "support_rate": round((6 - len(claims)) / 6, 3),
        "unsupported": list(claims),
        "unsupported_types": ["stat"] * len(claims),
        "claims": [
            {"claim": "Modders blend games with AI", "supported": True, "citation_line": "x"},
            *[
                {"claim": c, "supported": False, "citation_line": "", "type": "stat"}
                for c in claims
            ],
        ],
    }


def _features(*claims: str) -> dict:
    return {
        "claim_verification": _verification(*claims),
        "grounding_override": True,
        "grounding_override_claims": list(claims),
        "auto_research": {
            "kept_lines": [
                "Anthropic released Claude Opus 5.5 on September 22, 2026, its new top model.",
                "Modding communities report steady growth.",
            ]
        },
    }


class StoreCase(unittest.TestCase):
    """A one-run features store in place of the content_runs table."""

    def setUp(self):
        self.store = {120: _features(CLAIM)}
        self.quality: dict = {}
        load = lambda run_id: copy.deepcopy(self.store.get(int(run_id or 0), {}))  # noqa: E731

        def merge(run_id, updates):
            self.store.setdefault(int(run_id), {}).update(copy.deepcopy(updates))

        def merge_q(run_id, updates):
            self.quality.update(updates)

        for target in (
            patch("core.facts.claim_confirm.load_features", side_effect=load),
            patch("core.facts.claim_confirm.merge_features", side_effect=merge),
            patch("core.facts.claim_confirm.merge_quality", side_effect=merge_q),
            patch("publishing.go_public.load_features", side_effect=load),
        ):
            target.start()
            self.addCleanup(target.stop)


class ApplyConfirmationTests(unittest.TestCase):
    def test_the_claim_is_counted_as_supported_with_its_source(self):
        from core.facts.claim_confirm import apply_confirmation

        before = _verification(CLAIM, OTHER)
        after = apply_confirmation(before, CLAIM, source=SOURCE)
        self.assertEqual(after["unsupported"], [OTHER])
        self.assertEqual(after["unsupported_types"], ["stat"])
        self.assertEqual(after["supported"], 5)
        self.assertAlmostEqual(after["support_rate"], 5 / 6, places=3)
        row = next(r for r in after["claims"] if r["claim"] == CLAIM)
        self.assertTrue(row["supported"])
        self.assertIn(SOURCE, row["citation_line"])
        self.assertEqual(after["pre_confirm_unsupported"], [CLAIM, OTHER])
        self.assertEqual(before["unsupported"], [CLAIM, OTHER])  # the input is not mutated


class FlaggedClaimTests(unittest.TestCase):
    def test_flagged_claims_show_where_the_run_found_them(self):
        from core.facts.claim_confirm import flagged_claims

        rows = flagged_claims(_features(CLAIM, OTHER))
        self.assertEqual([r.claim for r in rows], [CLAIM, OTHER])
        self.assertTrue(rows[0].blocking)
        self.assertIn("September 22, 2026", rows[0].found_in)
        self.assertEqual(rows[1].found_in, "")

    def test_an_older_run_without_the_verifier_payload(self):
        from core.facts.claim_confirm import flagged_claims

        rows = flagged_claims({"grounding_override": True, "grounding_override_claims": [CLAIM]})
        self.assertEqual([r.claim for r in rows], [CLAIM])


class ConfirmTests(StoreCase):
    def test_a_dry_run_writes_nothing(self):
        from core.facts.claim_confirm import confirm_claim

        result = confirm_claim(120, 1, source=SOURCE, dry_run=True)
        self.assertTrue(result.released)
        self.assertTrue(self.store[120]["grounding_override"])
        self.assertEqual(self.quality, {})

    def test_confirming_the_last_blocking_claim_releases_the_hold(self):
        from core.facts.claim_confirm import confirm_claim
        from publishing.go_public import override_held

        self.assertTrue(override_held(120))
        result = confirm_claim(120, 1, source=SOURCE, note="their blog", dry_run=False)
        self.assertTrue(result.released)
        self.assertFalse(override_held(120))
        saved = self.store[120]
        self.assertEqual(saved["grounding_override_cleared_by"], "verify-claim")
        self.assertEqual(saved["claims_confirmed"][0]["source"], SOURCE)
        self.assertEqual(self.quality["unsupported_claim_count"], 0)
        self.assertEqual(self.quality["claims_confirmed_count"], 1)

    def test_a_claim_still_flagged_keeps_the_hold(self):
        from core.facts.claim_confirm import confirm_claim
        from publishing.go_public import override_held

        self.store[120] = _features(CLAIM, OTHER)
        result = confirm_claim(120, 1, source=SOURCE, dry_run=False)
        self.assertFalse(result.released)
        self.assertEqual(result.remaining, [OTHER])
        self.assertTrue(override_held(120))

    def test_a_short_cut_from_the_run_is_released_with_it(self):
        from core.facts.claim_confirm import confirm_claim
        from publishing.go_public import override_held

        self.store[121] = {"parent_run_id": 120}
        self.assertTrue(override_held(121))
        confirm_claim(120, 1, source=SOURCE, dry_run=False)
        self.assertFalse(override_held(121))


class RejectTests(StoreCase):
    def test_a_rejected_claim_lists_the_sentence_to_cut(self):
        from core.facts.claim_confirm import reject_claim

        script = (
            "AI modding is everywhere. Claude Opus 5.5 dropped on September 22 and modders "
            "noticed. The rest is up to the studios."
        )
        with patch("core.facts.claim_confirm.full_script", return_value=script):
            result = reject_claim(120, 1, dry_run=False)
        self.assertEqual(
            result.sentences, ["Claude Opus 5.5 dropped on September 22 and modders noticed."]
        )
        self.assertEqual(self.store[120]["claims_rejected"][0]["claim"], CLAIM)
        self.assertTrue(self.store[120]["grounding_override"])  # still held


class OneRuleTests(unittest.TestCase):
    def test_the_queue_asks_go_public_about_a_parent(self):
        from core import spaced_queue

        with patch("publishing.go_public.override_held", return_value=False) as held:
            self.assertFalse(spaced_queue._override_held('{"parent_run_id": 120}'))
        held.assert_called_once_with(120)


class OpsVerbTests(StoreCase):
    def _run(self, **kw):
        from scripts import ops

        defaults = {"run_id": 120, "claim": None, "source": None, "note": "", "reject": False,
                    "apply": False, "channel": "tapin"}  # fmt: skip
        defaults.update(kw)
        out = io.StringIO()
        with redirect_stdout(out):
            code = ops.COMMANDS["verify-claim"][1](argparse.Namespace(**defaults))
        return code, out.getvalue()

    def test_listing_the_claims(self):
        code, text = self._run()
        self.assertEqual(code, 0)
        self.assertIn(CLAIM, text)
        self.assertIn("September 22, 2026", text)

    def test_confirm_is_a_preview_until_apply(self):
        code, text = self._run(claim=1, source=SOURCE)
        self.assertEqual(code, 0)
        self.assertIn("--apply", text)
        self.assertTrue(self.store[120]["grounding_override"])
        code, text = self._run(claim=1, source=SOURCE, apply=True)
        self.assertEqual(code, 0)
        self.assertFalse(self.store[120]["grounding_override"])
        self.assertIn("go-public", text)

    def test_a_confirmation_needs_a_source(self):
        code, _text = self._run(claim=1)
        self.assertNotEqual(code, 0)


class GoPublicPointerTests(unittest.TestCase):
    def test_the_refusal_names_the_way_out(self):
        from unittest.mock import MagicMock

        from publishing.go_public import apply_go_public
        from storage.repositories.publish_log import PublishLogRecord

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [
            PublishLogRecord(
                id=1,
                content_run_id=120,
                channel_id="tapin",
                youtube_video_id="abc",
                privacy_status="unlisted",
                status="uploaded",
            )
        ]
        with patch("publishing.go_public.load_features", return_value={"grounding_override": 1}):
            result = apply_go_public("abc", channel_id="tapin", repo=repo)
        self.assertEqual(result.status, "refused")
        self.assertIn("verify-claim --run-id 120", result.detail)


if __name__ == "__main__":
    unittest.main()
