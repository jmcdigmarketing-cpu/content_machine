"""#134 n8n weekly-report recipe ships next to the other workflows."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class TestN8nWeeklyReport(unittest.TestCase):
    def test_workflow_filters_or_runs_weekly_report(self):
        path = Path("workflows/n8n/weekly_report.json")
        self.assertTrue(path.is_file(), path)
        data = json.loads(path.read_text(encoding="utf-8"))
        blob = json.dumps(data).lower()
        self.assertIn("weekly-report", blob)
        self.assertIn("n8n-nodes-base", blob)
