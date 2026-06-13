import unittest

from assets.composite import build_hybrid_concat_command
from config.channels import get_channel_profile


class TestHybridBackground(unittest.TestCase):
    def test_build_hybrid_concat_command(self):
        cmd = build_hybrid_concat_command(
            local_path="C:/local/game.mp4",
            stock_path="C:/stock/broll.mp4",
            output_path="C:/out/hybrid.mp4",
            duration=60.0,
            local_ratio=0.4,
        )
        joined = " ".join(cmd)
        self.assertIn("concat=n=2", joined)
        self.assertIn("format=yuv420p", joined)
        self.assertIn("24.000", joined)
        self.assertIn("36.000", joined)
        self.assertIn("-pix_fmt", cmd)
        self.assertIn("-an", cmd)

    def test_tapin_channel_uses_hybrid(self):
        profile = get_channel_profile("tapin")
        self.assertEqual(profile.background_mode, "hybrid")
        self.assertAlmostEqual(profile.hybrid_local_ratio, 0.45)
        self.assertEqual(profile.asset_provider_order[0], "local")


if __name__ == "__main__":
    unittest.main()
