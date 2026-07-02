"""display_summary surfaces per-run cost and the Apify out-of-credits warning."""

import unittest
from unittest.mock import patch

from core.ui import display_summary


def _capture(**kwargs):
    lines: list[str] = []

    def p(*args):
        lines.append(" ".join(str(a) for a in args))

    display_summary(print_fn=p, **kwargs)
    return "\n".join(lines)


class TestDisplaySummary(unittest.TestCase):
    def test_cost_line_shown_when_cost_present(self):
        out = _capture(
            timings={},
            title="T",
            cost={"llm": 0.04, "tts": 0.02, "total": 0.06},
        )
        self.assertIn("Est. run cost: $0.0600", out)

    def test_no_cost_line_without_cost(self):
        out = _capture(timings={}, title="T")
        self.assertNotIn("Est. run cost", out)

    def test_apify_disabled_shows_session_reason(self):
        with (
            patch("apis.apify_client.apify_disabled", return_value=True),
            patch(
                "apis.apify_client.apify_status",
                return_value="OFF — Apify credits/auth (403) — skipping social signals",
            ),
        ):
            out = _capture(timings={}, title="T")
        self.assertIn("Apify disabled this session", out)
        self.assertIn("403", out)
        self.assertNotIn("ran out of credits", out.lower())

    def test_no_apify_warning_when_healthy(self):
        with patch("apis.apify_client.apify_disabled", return_value=False):
            out = _capture(timings={}, title="T")
        self.assertNotIn("Apify disabled", out)


if __name__ == "__main__":
    unittest.main()
