"""#140 quota-increase playbook next to uploads-left when one upload cannot fit."""

from __future__ import annotations

import unittest

from apis.youtube_quota import quota_increase_advice


class TestQuotaIncreasePlaybook(unittest.TestCase):
    def test_when_no_upload_fits_the_playbook_is_attached(self):
        text = quota_increase_advice({"remaining": 100})
        self.assertIn("0 upload", text)
        self.assertIn("quota increase", text.lower())
        self.assertNotIn("99999", text)

    def test_when_an_upload_fits_only_the_count_line(self):
        text = quota_increase_advice({"remaining": 3200})
        self.assertIn("2 upload", text)
        self.assertNotIn("quota increase", text.lower())
