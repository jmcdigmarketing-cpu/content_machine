import unittest

from config.validate_channels import validate_channel


class TestValidateChannels(unittest.TestCase):
    def test_tapin_profile_valid(self):
        cfg = {
            "name": "TapIn Media",
            "domain": "gaming",
            "tts": {"voice_id": "nPczCjzI2devNBz1zQrb"},
            "weight_overrides": {"youtube": 0.5, "blog_rss": 0.5},
            "post_schedule": {"default_slots": [{"weekday": 4, "hour": 18, "minute": 0}]},
        }
        errors, warnings = validate_channel("tapin", cfg)
        self.assertEqual(errors, [])

    def test_unknown_weight_key_fails(self):
        errors, _ = validate_channel("x", {"weight_overrides": {"not_a_signal": 1.0}})
        self.assertTrue(any("unknown weight_overrides" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
