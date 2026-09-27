"""#853: the Anthropic defaults follow the current Claude family.

`core/llm_router._DEFAULT_MODELS["anthropic"]["premium"]` was `claude-sonnet-4-20250514`,
and `.env.example` shipped an *uncommented* `ANTHROPIC_MODEL=claude-sonnet-4-20250514`.
The router reads the bare `{PREFIX}_MODEL` for every tier, so a `.env` copied from the
example pinned all three tiers to the old Sonnet whatever the defaults said.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_CLAUDE = {"claude-sonnet-5", "claude-opus-5-5", "claude-haiku-4-5-20251001"}


class ClaudeDefaultTests(unittest.TestCase):
    def test_the_router_defaults_are_current_models(self):
        from core.llm_router import _DEFAULT_MODELS

        anthropic = _DEFAULT_MODELS["anthropic"]
        self.assertEqual(anthropic["premium"], "claude-sonnet-5")
        self.assertLessEqual(set(anthropic.values()), CURRENT_CLAUDE)

    def test_the_example_does_not_pin_every_tier(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^ANTHROPIC_MODEL=", text, re.M))
        self.assertNotIn("claude-sonnet-4-", text)


if __name__ == "__main__":
    unittest.main()
