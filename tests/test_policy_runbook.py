"""#132 policy-incident runbook is reachable from ops, not a silent markdown file."""

from __future__ import annotations

import argparse
import io
import unittest
from unittest.mock import patch

from core.policy_runbook import runbook_path, runbook_text
from scripts import ops


class TestPolicyRunbook(unittest.TestCase):
    def test_runbook_file_exists_and_names_the_incidents(self):
        path = runbook_path()
        self.assertTrue(path.is_file(), path)
        text = runbook_text()
        self.assertIn("Content ID", text)
        self.assertIn("strike", text.lower())
        self.assertIn("appeal", text.lower())

    def test_ops_prints_the_path(self):
        args = argparse.Namespace(channel="tapin", html=False)
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(ops.cmd_policy_runbook(args), 0)
        out = buf.getvalue()
        self.assertIn("policy", out.lower())
        self.assertTrue(str(runbook_path()) in out or runbook_path().name in out)
