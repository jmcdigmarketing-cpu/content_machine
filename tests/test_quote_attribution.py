"""#338. Quoted speech must map to a source that names the speaker."""

from __future__ import annotations

import unittest

from core.quote_attribution import check_quote_attribution


class TestQuoteAttribution(unittest.TestCase):
    def test_invented_quote_flags_when_facts_name_no_speaker(self):
        script = 'Dana White said, "This fight is off." The card still happens Saturday.'
        facts = "UFC 350 is this Saturday in Las Vegas."
        result = check_quote_attribution(script, facts)
        self.assertTrue(result.flagged)
        self.assertGreaterEqual(result.flagged_count, 1)
        self.assertIn("This fight is off", result.flagged[0].quote)

    def test_same_quote_passes_when_facts_name_the_speaker(self):
        script = 'Dana White said, "This fight is off." The card still happens Saturday.'
        facts = 'Dana White told ESPN "This fight is off." UFC 350 is Saturday.'
        result = check_quote_attribution(script, facts)
        self.assertFalse(result.flagged)
        self.assertEqual(result.flagged_count, 0)

    def test_short_title_quotes_do_not_fire(self):
        script = 'The trailer for "GTA 6" dropped last night and fans lost it.'
        facts = "Rockstar showed a GTA 6 trailer last night."
        result = check_quote_attribution(script, facts)
        self.assertFalse(result.flagged)

    def test_known_gap_nested_quotes_are_not_parsed(self):
        """Nested quotes need a real parser. Closing this would mean matching
        inner spans without treating the outer wrapper as one invented quote."""
        script = 'The host said, "Dana White told me, "this fight is off" yesterday."'
        facts = "The host recapped the presser. No speaker is named."
        result = check_quote_attribution(script, facts)
        self.assertTrue(
            result.known_gap,
            "nested quotes stay a documented gap until a real parser lands",
        )
