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
        self.assertIn("xfade", joined)
        self.assertNotIn("concat=n=2", joined)
        self.assertIn("format=yuv420p", joined)
        self.assertIn("24.000", joined)
        # 36.500, not 36.000: an xfade output runs `offset + len(second input)`, so the
        # stock segment carries the fade back. Asserting the bare 60*0.6 split is what
        # let every hybrid background come out exactly `fade` short — measured against
        # real ffmpeg, a 6.000s request produced 5.500s. See
        # tests/test_hybrid_crossfade_duration.py, which checks the sum rather than the
        # individual trims so this cannot drift again.
        self.assertIn("36.500", joined)
        self.assertIn("-pix_fmt", cmd)
        self.assertIn("-an", cmd)

    def test_tapin_channel_uses_hybrid(self):
        profile = get_channel_profile("tapin")
        self.assertEqual(profile.background_mode, "hybrid")
        self.assertAlmostEqual(profile.hybrid_local_ratio, 0.70)
        self.assertEqual(profile.asset_provider_order[0], "local")
        self.assertEqual(profile.background_mode, "hybrid")

    def test_shipped_tapin_ratio_is_seventy_not_flipped_to_local(self):
        from config.validate_channels import _load_raw, validate_channel

        raw = _load_raw().get("channels", {})
        tapin = raw["tapin"]
        self.assertEqual(tapin.get("background_mode"), "hybrid")
        self.assertAlmostEqual(float(tapin["hybrid_local_ratio"]), 0.70)
        moneywise = raw["moneywise"]
        self.assertAlmostEqual(float(moneywise["hybrid_local_ratio"]), 0.45)
        errors, _ = validate_channel("tapin", tapin)
        self.assertEqual(errors, [])

    def test_hybrid_join_uses_xfade(self):
        cmd = build_hybrid_concat_command(
            local_path="C:/local/game.mp4",
            stock_path="C:/stock/broll.mp4",
            output_path="C:/out/hybrid.mp4",
            duration=60.0,
            local_ratio=0.7,
        )
        joined = " ".join(cmd)
        self.assertIn("xfade", joined)
        self.assertNotIn("concat=n=2", joined)


if __name__ == "__main__":
    unittest.main()
