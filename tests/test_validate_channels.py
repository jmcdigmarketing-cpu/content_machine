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


class TestShippedConfigRatchet(unittest.TestCase):
    """Candidate 33: validate the REAL config/channels.json, not only synthetic dicts.

    Every other test here builds its own dict, so a bad value in the shipped file
    passed the suite and only surfaced during a run - an unknown ui_theme silently
    falls back, a missing persona quietly drops the human-context block. This is the
    ratchet: errors fail here, before a render.

    Warnings are reported, not failed: `moneywise` has no persona today, and this
    test exists to stop NEW breakage, not to block on a known gap.
    """

    def _raw(self):
        from config.validate_channels import _load_raw

        raw = _load_raw()
        return raw.get("channels", raw) if isinstance(raw, dict) else {}

    def test_shipped_channels_have_no_errors(self):
        from config.validate_channels import validate_channel

        channels = self._raw()
        self.assertTrue(channels, "config/channels.json defines no channels")
        problems = {}
        for channel_id, cfg in channels.items():
            errors, _ = validate_channel(channel_id, cfg)
            if errors:
                problems[channel_id] = errors
        self.assertEqual(problems, {}, f"shipped channels.json has errors: {problems}")

    def test_every_channel_declares_a_known_theme_or_none(self):
        from core.themes import THEMES

        for channel_id, cfg in self._raw().items():
            theme = (cfg or {}).get("ui_theme")
            if theme is not None:
                self.assertIn(str(theme).strip().lower(), THEMES, channel_id)

    def test_an_unknown_theme_is_an_error(self):
        # Pins the ratchet itself: if this stops failing, the check has been lost.
        from config.validate_channels import validate_channel

        errors, _ = validate_channel("x", {"ui_theme": "not-a-skin"})
        self.assertTrue(any("unknown ui_theme" in e for e in errors), errors)

    def test_a_non_object_persona_is_an_error(self):
        from config.validate_channels import validate_channel

        errors, _ = validate_channel("x", {"persona": "a string"})
        self.assertTrue(any("persona must be an object" in e for e in errors), errors)

    def test_missing_persona_warns_but_does_not_fail(self):
        from config.validate_channels import validate_channel

        errors, warnings = validate_channel("x", {})
        self.assertFalse(any("persona" in e for e in errors))
        self.assertTrue(any("no persona" in w for w in warnings), warnings)

    def test_no_profile_field_is_unset_on_every_shipped_channel(self):
        """#644. Fields nobody sets are dead code (this is how 641-643 hid)."""
        from dataclasses import fields

        from config.channels import ChannelProfile, get_channel_profiles

        profiles = list(get_channel_profiles().values())
        self.assertTrue(profiles)

        def _blank(value) -> bool:
            if value is None or value == "":
                return True
            return value in ({}, (), [])

        dead = []
        for item in fields(ChannelProfile):
            if item.name == "id":
                continue
            if all(_blank(getattr(profile, item.name)) for profile in profiles):
                dead.append(item.name)
        self.assertEqual(
            dead,
            [],
            "ChannelProfile fields unset on every shipped channel — wire them or remove them: "
            + ", ".join(dead),
        )
