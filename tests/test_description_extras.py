"""Tests for AI-disclosure + monetization CTA description extras."""

import unittest
from unittest.mock import patch

from core.description_extras import (
    DEFAULT_AI_DISCLOSURE,
    apply_description_extras,
)


class TestDescriptionExtras(unittest.TestCase):
    def test_disclosure_appended_by_default(self):
        with patch("core.description_extras.get_seo_profile", return_value={}):
            out = apply_description_extras("Great fight breakdown.", "tapin")
        self.assertIn("Great fight breakdown.", out)
        self.assertIn(DEFAULT_AI_DISCLOSURE, out)

    def test_disclosure_idempotent(self):
        with patch("core.description_extras.get_seo_profile", return_value={}):
            once = apply_description_extras("Body.", "tapin")
            twice = apply_description_extras(once, "tapin")
        self.assertEqual(once, twice)
        self.assertEqual(twice.count(DEFAULT_AI_DISCLOSURE), 1)

    def test_disclosure_disabled_by_env(self):
        with (
            patch.dict("os.environ", {"AI_DISCLOSURE_ENABLED": "false"}),
            patch("core.description_extras.get_seo_profile", return_value={}),
        ):
            out = apply_description_extras("Body.", "tapin")
        self.assertNotIn(DEFAULT_AI_DISCLOSURE, out)
        self.assertEqual(out, "Body.")

    def test_custom_disclosure_overrides_default(self):
        with patch(
            "core.description_extras.get_seo_profile",
            return_value={"ai_disclosure": "AI narration used."},
        ):
            out = apply_description_extras("Body.", "tapin")
        self.assertIn("AI narration used.", out)
        self.assertNotIn(DEFAULT_AI_DISCLOSURE, out)

    def test_monetization_ctas_appended(self):
        with patch(
            "core.description_extras.get_seo_profile",
            return_value={"monetization_cta": ["Gear: example.com", "Sponsor: Acme"]},
        ):
            out = apply_description_extras("Body.", "tapin")
        self.assertIn("Gear: example.com", out)
        self.assertIn("Sponsor: Acme", out)

    def test_empty_description_gets_disclosure(self):
        with patch("core.description_extras.get_seo_profile", return_value={}):
            out = apply_description_extras("", "tapin")
        self.assertEqual(out, DEFAULT_AI_DISCLOSURE)

    def test_moneywise_finance_disclaimer(self):
        from core.description_extras import DEFAULT_FINANCE_DISCLAIMER

        with patch("core.description_extras.get_seo_profile", return_value={}):
            out = apply_description_extras("Rates rose.", "moneywise")
        self.assertIn(DEFAULT_FINANCE_DISCLAIMER, out)
        self.assertIn(DEFAULT_AI_DISCLOSURE, out)

    def test_tapin_has_no_finance_disclaimer(self):
        from core.description_extras import DEFAULT_FINANCE_DISCLAIMER

        with patch("core.description_extras.get_seo_profile", return_value={}):
            out = apply_description_extras("Great fight breakdown.", "tapin")
        self.assertNotIn(DEFAULT_FINANCE_DISCLAIMER, out)


if __name__ == "__main__":
    unittest.main()
