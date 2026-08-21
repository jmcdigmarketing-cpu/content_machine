"""OneDrive / nested .git hazard check."""

from __future__ import annotations

import os
import tempfile
import unittest

from core.workspace_hazards import gather, render


class TestWorkspaceHazards(unittest.TestCase):
    def test_clean_tmp_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = gather(tmp)
        self.assertFalse(data["onedrive"])
        self.assertEqual(data["hazards"], [])
        self.assertIn("ok", render(data))

    def test_onedrive_path_is_a_hazard(self):
        data = gather(r"C:\Users\x\OneDrive\content_machine")
        self.assertTrue(data["onedrive"])
        self.assertTrue(data["hazards"])
        self.assertIn("OneDrive", render(data))

    def test_nested_git_under_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "output", ".git"))
            data = gather(tmp)
        self.assertTrue(any("output/.git" in h for h in data["hazards"]))


if __name__ == "__main__":
    unittest.main()
