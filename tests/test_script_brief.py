import unittest

from core.script_brief import build_script_brief


class TestScriptBrief(unittest.TestCase):
    def test_ufc_brief_blocks_retired_contender_guessing(self):
        brief = build_script_brief("UFC 250 Topuria vs Gaethje title defense", "tapin")
        self.assertIn("UFC SCRIPT MATRIX", brief)
        self.assertIn("Poirier", brief)
        self.assertIn("featherweight", brief.lower())
        self.assertIn("UFC 250", brief)

    def test_gaming_brief(self):
        brief = build_script_brief("GTA 6 delay rumors", "tapin")
        self.assertIn("GAMING", brief)


if __name__ == "__main__":
    unittest.main()
