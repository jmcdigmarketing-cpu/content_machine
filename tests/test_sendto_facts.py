"""#294 Explorer Send-to facts.txt writer — temp SendTo dir, not %APPDATA%."""

from __future__ import annotations

import os
import tempfile
import unittest

from core.win_shell import install_sendto_facts_shortcut


class TestSendToFacts(unittest.TestCase):
    def test_writes_shortcut_into_given_sendto_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = install_sendto_facts_shortcut(
                sendto_dir=tmp, facts_path=os.path.join(tmp, "facts.txt")
            )
            self.assertIsNotNone(dest)
            self.assertTrue(os.path.isfile(dest))
            self.assertTrue(dest.lower().endswith(".lnk") or dest.lower().endswith(".txt"))
            self.assertTrue(dest.startswith(tmp))
