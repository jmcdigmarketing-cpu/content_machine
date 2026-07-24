"""Agent Skills generator (Pillar 7 C1) — SKILL.md rendered from the ops registry."""

import os
import tempfile
import unittest

from core import ops_skills


class TestOpsSkills(unittest.TestCase):
    def test_render_has_frontmatter_and_commands(self):
        md = ops_skills.render_skill(
            [("status", "Show pipeline status"), ("reliability", "Budget")]
        )
        self.assertTrue(md.startswith("---\n"))
        self.assertIn("name: content-ops", md)
        self.assertIn("description:", md)
        self.assertIn("| `status` | Show pipeline status |", md)
        self.assertIn("| `reliability` | Budget |", md)

    def test_pipe_in_help_is_escaped(self):
        # A '|' in help text must be escaped so the markdown table stays valid.
        md = ops_skills.render_skill([("x", "does a | b")])
        self.assertIn("does a \\| b", md)

    def test_registry_commands_nonempty(self):
        cmds = ops_skills._registry_commands()
        self.assertTrue(cmds)
        self.assertTrue(all(isinstance(n, str) and isinstance(h, str) for n, h in cmds))

    def test_write_skill_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "content-ops", "SKILL.md")
            written = ops_skills.write_skill(path)
            self.assertEqual(written, path)
            with open(path, encoding="utf-8") as f:
                self.assertIn("name: content-ops", f.read())


if __name__ == "__main__":
    unittest.main()
