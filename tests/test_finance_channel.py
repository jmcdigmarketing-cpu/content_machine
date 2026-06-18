"""Tests for the MoneyWise finance channel + domain inference word-boundary fix."""

import unittest

from apis.topic_scorer import infer_domain


class TestFinanceDomainInference(unittest.TestCase):
    def test_finance_topics(self):
        for topic in (
            "Nvidia earnings beat expectations",
            "Fed holds interest rates",
            "How to build an emergency fund",
            "S&P 500 hits record high",
            "Bitcoin ETF inflows surge",
            "Ethereum upgrade goes live",
        ):
            self.assertEqual(infer_domain(topic), "finance", topic)

    def test_inflows_is_not_nfl(self):
        # Regression: substring match used to route 'inflows' -> nfl.
        self.assertNotEqual(infer_domain("Bitcoin ETF inflows surge"), "nfl")

    def test_other_domains_unbroken(self):
        self.assertEqual(infer_domain("Marvel Rivals Season 3 tier list"), "gaming")
        self.assertEqual(infer_domain("UFC 320 main card predictions"), "ufc")
        self.assertEqual(infer_domain("Mahomes leads Chiefs comeback"), "nfl")


class TestMoneyWiseChannel(unittest.TestCase):
    def test_profile_loads(self):
        from config.channels import get_channel_profile

        p = get_channel_profile("moneywise")
        self.assertEqual(p.name, "MoneyWise")
        self.assertEqual(p.domain, "finance")

    def test_on_brand_is_finance(self):
        from core.channel_context import on_brand_domains

        self.assertEqual(on_brand_domains("moneywise"), {"finance"})

    def test_apify_finance_targets(self):
        from apis.apify_catalog import domain_targets

        subs = domain_targets("finance").get("subreddits", [])
        self.assertIn("stocks", subs)
        self.assertIn("CryptoCurrency", subs)

    def test_seo_profile(self):
        from config.seo import get_seo_profile

        prof = get_seo_profile("moneywise")
        self.assertIn("finance", prof.get("niche", ""))
        # Finance compliance: disclosure mentions "not financial advice".
        self.assertIn("financial advice", prof.get("ai_disclosure", "").lower())

    def test_finance_post_slots(self):
        from analytics.post_timing import DEFAULT_DOMAIN_SLOTS

        self.assertIn("finance", DEFAULT_DOMAIN_SLOTS)


if __name__ == "__main__":
    unittest.main()
