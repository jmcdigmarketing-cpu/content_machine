"""A3: /tdd skill is invokable and encodes write-test → watch-it-fail → fix.

Original text only — not a copy of unlicensed third-party skill files.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestTddSkillDiscoverable(unittest.TestCase):
    def test_claude_skill_encodes_fail_then_fix(self):
        path = ROOT / ".claude" / "skills" / "tdd" / "SKILL.md"
        self.assertTrue(path.is_file(), f"missing Claude Code skill at {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn("name: tdd", text)
        lowered = text.lower()
        self.assertIn("write", lowered)
        self.assertIn("fail", lowered)
        self.assertIn("fix", lowered)
        self.assertIn("never mock the function under test", lowered)
        self.assertNotIn("mattpocock", lowered)

    def test_cursor_skill_is_original_and_discoverable(self):
        path = ROOT / ".cursor" / "skills" / "tdd" / "SKILL.md"
        self.assertTrue(path.is_file(), f"missing Cursor skill at {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn("name: tdd", text)
        self.assertIn("watch it fail", text.lower())
        self.assertNotIn("mattpocock", text.lower())


if __name__ == "__main__":
    unittest.main()
