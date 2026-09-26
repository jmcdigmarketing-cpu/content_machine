"""#872 / #866: one list of domains, resolved once per run, read at upload.

Wave 33 added `soccer` as a domain; `CATEGORY_BY_DOMAIN` never got it, so every football
upload - run 98 included - was filed under YouTube category 20 (Gaming). And the run's
own answer to "what is this about" (topic words + pasted facts + live signals) was never
stored: `features["domain"]` holds the channel-fallback weighting domain, so the upload
path re-guessed from the title alone. "Who wins Sunday's derby?" with Premier League
facts pasted is soccer to the run and gaming to the uploader.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DERBY = "Who wins Sunday's derby?"
DERBY_FACTS = ["Manchester City play Manchester United in the Premier League on Sunday."]
RUN98 = "Manchester City ofund guilty, what does this mean for the prem"


class KnownDomainsTests(unittest.TestCase):
    def test_known_domains_match_the_weight_profiles(self):
        from apis.topic_scorer import _LEARNED_PROFILES, KNOWN_DOMAINS

        self.assertEqual(set(KNOWN_DOMAINS), set(_LEARNED_PROFILES) - {"neutral"})

    def test_every_domain_has_a_youtube_category(self):
        from apis.topic_scorer import KNOWN_DOMAINS
        from core.youtube_meta import CATEGORY_BY_DOMAIN

        self.assertEqual([d for d in KNOWN_DOMAINS if d not in CATEGORY_BY_DOMAIN], [])

    def test_every_domain_has_a_length_default(self):
        from apis.topic_scorer import KNOWN_DOMAINS
        from core.length_recommender import _DEFAULT_BY_DOMAIN

        self.assertEqual([d for d in KNOWN_DOMAINS if d not in _DEFAULT_BY_DOMAIN], [])

    def test_football_is_filed_as_sports(self):
        from core.youtube_meta import category_id_for_topic

        self.assertEqual(category_id_for_topic(RUN98, "tapin"), "17")


class ResolveDomainsTests(unittest.TestCase):
    def test_three_answers(self):
        from apis.topic_scorer import resolve_domains

        got = resolve_domains(DERBY, "tapin", key_facts=DERBY_FACTS)
        self.assertEqual(got, {"topic": "soccer", "effective": "soccer", "weighting": "soccer"})

    def test_keywordless_topic_without_evidence_is_neutral_but_weights_as_channel(self):
        from apis.topic_scorer import resolve_domains

        got = resolve_domains("Is this the best one yet?", "tapin")
        self.assertEqual(got["topic"], "neutral")
        self.assertEqual(got["weighting"], "gaming")

    def test_build_features_stores_them(self):
        from core.run_features import build_features

        feats = build_features(
            topic=DERBY, channel_id="tapin", content_package={}, key_facts=DERBY_FACTS
        )
        self.assertEqual(feats["domains"]["effective"], "soccer")
        self.assertEqual(feats["domain"], "soccer")  # weighting keeps the fact override

    def test_run_domain_reads_the_stored_answer(self):
        from core.run_features import run_domain

        with patch(
            "core.run_features.load_features",
            return_value={"domain": "gaming", "domains": {"effective": "soccer"}},
        ):
            self.assertEqual(run_domain(7), "soccer")
        with patch("core.run_features.load_features", return_value={"domain": "gaming"}):
            self.assertEqual(run_domain(7), "gaming")  # runs from before #866
        self.assertEqual(run_domain(None), "")


class UploadReadsTheRunTests(unittest.TestCase):
    def test_request_domain_sets_the_category(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import dry_run_insert_body

        req = PublishRequest(file_path="x.mp4", title=DERBY, description="", domain="soccer")
        self.assertEqual(
            dry_run_insert_body(req, channel_id="tapin")["snippet"]["categoryId"], "17"
        )

    def test_publish_fills_the_domain_from_the_run(self):
        from publishing.base import PublishRequest
        from publishing.youtube_publisher import request_with_run_domain

        req = PublishRequest(file_path="x.mp4", title=DERBY, description="")
        with patch("core.run_features.run_domain", return_value="soccer"):
            self.assertEqual(request_with_run_domain(req, 12).domain, "soccer")
        self.assertEqual(request_with_run_domain(req, None).domain, "")
        kept = PublishRequest(file_path="x.mp4", title=DERBY, description="", domain="nba")
        with patch("core.run_features.run_domain", return_value="soccer"):
            self.assertEqual(request_with_run_domain(kept, 12).domain, "nba")


# Each caller of the channel-fallback `infer_domain`, and why the fallback is right there.
# A new caller must add itself here - i.e. decide - or use infer_topic_domain /
# effective_domain / the run's stored `domains`.
INFER_DOMAIN_CALLERS = {
    "analytics/post_timing.py": "post-time history is bucketed by the weighting domain",
    "analytics/youtube_metrics.py": "published-video metrics join history by weighting domain",
    "apis/reddit_signal.py": "retired signal (enabled: false)",
    "apis/twitter_signal.py": "retired signal (enabled: false)",
    "core/batch_review.py": "news-domain check; the channel fallback is never a news domain",
    "core/best_bet.py": "best-bet history and domain rates are keyed by weighting domain",
    "core/content_engine.py": "facts domain passes channel_id=None; trade check passes key_facts",
    "core/cross_channel_dup.py": "same subject on another channel; subject + facts",
    "core/engagement.py": "engagement history keyed by weighting domain",
    "core/intelligence_report.py": "variant weights use the weighting domain",
    "core/length_recommender.py": "length history keyed by weighting domain",
    "core/opportunity.py": "opportunity weights use the weighting domain",
    "core/run_features.py": "features['domain'] is the weighting domain history reads",
    "core/run_recorder.py": "channel memory is keyed by weighting domain",
    "core/topic_db.py": "topic buckets keyed by weighting domain",
    "core/topic_graph.py": "graph nodes keyed by weighting domain",
    "core/ui.py": "domain art when no run exists; a neutral topic shows the channel art",
    "core/unit_economics.py": "per-domain margins over stored runs",
    "core/win_notify.py": "toast chip when no run exists",
    "core/youtube_meta.py": "category when no run domain was passed",
    "publishing/youtube_publisher.py": "only when the request carries no run domain",
}


class InferDomainCallersTests(unittest.TestCase):
    def test_every_caller_is_a_decision(self):
        found = set()
        for folder in ("core", "apis", "analytics", "publishing", "video", "scripts", "youtube"):
            for path in (ROOT / folder).rglob("*.py"):
                rel = path.relative_to(ROOT).as_posix()
                if rel == "apis/topic_scorer.py":
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                        if name in ("infer_domain", "_infer_domain", "safe_infer_domain"):
                            found.add(rel)
        self.assertEqual(sorted(found - set(INFER_DOMAIN_CALLERS)), [])
        self.assertEqual(sorted(set(INFER_DOMAIN_CALLERS) - found), [], "stale allowlist entry")


if __name__ == "__main__":
    unittest.main()
