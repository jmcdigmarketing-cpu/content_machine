"""display_summary surfaces per-run cost and the Apify out-of-credits warning."""

import unittest
from unittest.mock import patch

from core.ui import display_summary


def _capture(**kwargs):
    lines: list[str] = []

    def p(*args):
        lines.append(" ".join(str(a) for a in args))

    with patch(
        "apis.apify_client.apify_credit_exhausted", return_value=kwargs.pop("exhausted", False)
    ):
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

    def test_apify_exhausted_warning(self):
        out = _capture(timings={}, title="T", exhausted=True)
        self.assertIn("Apify ran out of credits", out)

    def test_no_apify_warning_when_healthy(self):
        out = _capture(timings={}, title="T", exhausted=False)
        self.assertNotIn("Apify ran out of credits", out)


if __name__ == "__main__":
    unittest.main()
