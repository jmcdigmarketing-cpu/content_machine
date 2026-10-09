"""#1020: stock footage only as a last resort, and labelled (operator, 2026-10-08).

"the stock video really drives me crazy, i would rather download a lot of uncopyrighted
footage instead" - and, asked, "Stock only as a last resort". TapIn's `background_mode`
was `hybrid` at `hybrid_local_ratio` 0.70: whenever both existed, 30% of every background
was stock B-roll laid over owned gameplay.

- `local_first` (`assets.manager.VALID_BACKGROUND_MODES`): owned footage that matches the
  topic -> stock, with a warning naming `ops footage-gaps` -> the plain branded background.
  Owned and stock are never blended.
- TapIn uses it (`config/channels.json`); the validator accepts it.
- `assets.manager.footage_label` says what the background is; the render prints it, so a
  stock background reads "STOCK (last resort ...)" instead of a file name.

Also the operator's "talking speed has to be upped a bit" -> 1.05 (asked, 2026-10-08):
both channels' `tts.speed`.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from assets.types import AssetResult

LOCAL = AssetResult(path="g.mp4", provider="local", query="t")
STOCK = AssetResult(path="s.mp4", provider="pexels", query="t", attribution="Video by A on Pexels")
PLAIN = AssetResult(path="p.mp4", provider="plain", query="t")


class LocalFirstTests(unittest.TestCase):
    def _pick(self, local, stock):
        from assets import manager

        with (
            patch.object(manager, "resolve_background_mode", return_value="local_first"),
            patch.object(manager, "get_local_background_asset", return_value=local),
            patch.object(manager, "get_stock_background_asset", return_value=stock) as get_stock,
            patch.object(manager, "_plain_or_raise", return_value=PLAIN),
            patch.object(manager, "try_compose_hybrid") as compose,
        ):
            asset = manager.get_background_asset("chargers 0-4", "tapin", duration=60.0)
        compose.assert_not_called()
        return asset, get_stock

    def test_owned_footage_wins_and_stock_is_never_fetched(self):
        asset, get_stock = self._pick(LOCAL, STOCK)
        self.assertIs(asset, LOCAL)
        get_stock.assert_not_called()

    def test_stock_only_when_nothing_owned_matches(self):
        with self.assertLogs("content_machine.assets", level="WARNING") as logs:
            asset, _get_stock = self._pick(None, STOCK)
        self.assertEqual(asset.provider, "pexels")
        self.assertIn("last resort", "\n".join(logs.output))

    def test_plain_when_neither(self):
        asset, _get_stock = self._pick(None, None)
        self.assertIs(asset, PLAIN)

    def test_the_mode_is_valid_and_tapin_uses_it(self):
        from assets.manager import VALID_BACKGROUND_MODES
        from config.channels import get_channel_profile
        from config.validate_channels import _load_raw, validate_channel

        self.assertIn("local_first", VALID_BACKGROUND_MODES)
        self.assertEqual(get_channel_profile("tapin").background_mode, "local_first")
        raw = _load_raw()
        cfg = (raw.get("channels") or raw)["tapin"]
        errors, _warnings = validate_channel("tapin", cfg)
        self.assertFalse([e for e in errors if "background_mode" in e], errors)


class LabelTests(unittest.TestCase):
    def test_labels(self):
        from assets.manager import footage_label

        self.assertIn("STOCK", footage_label(STOCK))
        self.assertIn("last resort", footage_label(STOCK))
        self.assertNotIn("STOCK", footage_label(AssetResult(path="f", provider="fast_cut")))
        self.assertIn("owned", footage_label(AssetResult(path="f", provider="fast_cut")))
        self.assertIn("owned", footage_label(AssetResult(path="f", provider="owned")))
        self.assertIn("plain", footage_label(PLAIN))
        self.assertIn("stock", footage_label(AssetResult(path="h", provider="hybrid")))

    def test_the_render_prints_the_label(self):
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "video" / "render_video.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("footage_label(asset)", src)


class SpeedTests(unittest.TestCase):
    def test_both_channels_speak_at_1_05(self):
        import os

        from core.tts import speech_speed

        env = {k: v for k, v in os.environ.items() if k != "TTS_SPEED"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(speech_speed("tapin"), 1.05)
            self.assertEqual(speech_speed("moneywise"), 1.05)


if __name__ == "__main__":
    unittest.main()
