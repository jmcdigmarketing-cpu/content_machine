"""Ops commands registered for the follow-on 4 wave."""

from __future__ import annotations

import unittest

from scripts import ops


class TestWave4OpsCommands(unittest.TestCase):
    def test_commands_registered(self):
        for name in (
            "postmortem",
            "doctor",
            "apify-trueup",
            "tts-arms",
            "artifacts",
            "policy-canary",
            "moat-backup",
            "ypp",
        ):
            self.assertIn(name, ops.COMMANDS)
