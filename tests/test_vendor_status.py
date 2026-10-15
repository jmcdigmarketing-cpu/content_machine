"""#392: ops doctor says whether Apify is down or we are.

The status page body is a fixture. Nothing in this file calls the network.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.test_ops_doctor import _stack


def _body(indicator: str) -> dict:
    return {"status": {"indicator": indicator, "description": "x"}}


class VendorStatusTests(unittest.TestCase):
    def test_a_major_incident_is_them_and_a_clean_page_with_our_failure_is_us(self):
        from core.ops_doctor import vendor_line

        down_ok, down = vendor_line(_body("major"), set())
        self.assertFalse(down_ok)
        self.assertIn("they are down", down)
        self.assertNotIn("we broke it", down)

        ours_ok, ours = vendor_line(_body("none"), {"tiktok_trends"})
        self.assertFalse(ours_ok)
        self.assertIn("we broke it", ours)
        self.assertNotIn("they are down", ours)

        ok, quiet = vendor_line(_body("none"), set())
        self.assertTrue(ok)
        self.assertIn("operational", quiet)

        # A failure that is not an Apify signal does not blame us for Apify.
        other_ok, other = vendor_line(_body("none"), {"espn"})
        self.assertTrue(other_ok)
        self.assertNotIn("we broke it", other)

    def test_a_status_page_that_cannot_be_read_is_not_a_warning(self):
        from core.ops_doctor import gather

        def fetch(_url):
            raise OSError("down")

        with (
            _stack(),
            patch("core.ops_doctor._local_signal_failures", return_value=set()),
            self.assertNoLogs("content_machine.core.ops_doctor", level="WARNING"),
        ):
            data = gather("tapin", status_fetch=fetch)
        check = next(c for c in data["checks"] if c["name"] == "apify_status")
        self.assertTrue(check["ok"])
        self.assertIn("status page unreachable", check["detail"])
