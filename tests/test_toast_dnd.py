"""Quiet-hours toast DND, exercised through the real channel lookup.

Wave 4 shipped `#292` inert. `_toasts_muted()` called `quiet_hours_reason()` with no
channel, which resolves to the `default` channel — and `default` has no `quiet_hours`
block; only `tapin` and `moneywise` do (1-8am ET). So the reason was always `None` and
no toast was ever muted, at any hour.

It passed CI because the wave's own test mocked `quiet_hours_reason` to return a
string, proving only "given a reason, mute" — never that a reason could occur.

So these tests drive the **clock** and leave the **channel lookup live**, reading the
shipped `config/channels.json`. That is the half that was broken, so that is the half
that must not be mocked.
"""

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core import win_notify

# 07:00Z = 03:00 ET (EDT) — inside the shipped 1-8am quiet window.
QUIET = datetime(2026, 8, 23, 7, 0, tzinfo=timezone.utc)
# 18:00Z = 14:00 ET — plainly outside it.
AWAKE = datetime(2026, 8, 23, 18, 0, tzinfo=timezone.utc)


class TestMutedAgainstRealConfig(unittest.TestCase):
    """No mock on quiet_hours_reason — the real channels.json decides."""

    def test_quiet_hours_mute(self):
        with patch.dict(os.environ, {"CONTENT_TOAST_DND": "true", "QUIET_HOURS": "true"}):
            self.assertTrue(win_notify._toasts_muted(when=QUIET))

    def test_waking_hours_do_not(self):
        with patch.dict(os.environ, {"CONTENT_TOAST_DND": "true", "QUIET_HOURS": "true"}):
            self.assertFalse(win_notify._toasts_muted(when=AWAKE))

    def test_dnd_flag_off_never_mutes(self):
        with patch.dict(os.environ, {"CONTENT_TOAST_DND": "false", "QUIET_HOURS": "true"}):
            self.assertFalse(win_notify._toasts_muted(when=QUIET))

    def test_quiet_hours_master_switch_off_never_mutes(self):
        # QUIET_HOURS is the shipped #116 master flag; DND must respect it.
        with patch.dict(os.environ, {"CONTENT_TOAST_DND": "true", "QUIET_HOURS": "false"}):
            self.assertFalse(win_notify._toasts_muted(when=QUIET))

    def test_no_configured_quiet_hours_means_no_mute(self):
        with patch.dict(os.environ, {"CONTENT_TOAST_DND": "true", "QUIET_HOURS": "true"}):
            with patch("config.channels.list_channel_ids", return_value=["default"]):
                self.assertFalse(win_notify._toasts_muted(when=QUIET))

    def test_a_broken_lookup_fails_open_to_not_muted(self):
        with patch.dict(os.environ, {"CONTENT_TOAST_DND": "true"}):
            with patch("config.channels.list_channel_ids", side_effect=RuntimeError("boom")):
                self.assertFalse(win_notify._toasts_muted(when=QUIET))


class TestRoutineToastsAreMuted(unittest.TestCase):
    def setUp(self):
        win_notify._toasted.clear()

    def test_routine_toast_is_suppressed_in_quiet_hours(self):
        with patch.dict(
            os.environ,
            {"CONTENT_TOAST": "true", "CONTENT_TOAST_FORCE": "true", "CONTENT_TOAST_DND": "true"},
        ):
            with patch.object(win_notify, "_toasts_muted", return_value=True):
                with patch.object(win_notify, "_toast_powershell", return_value=True) as ps:
                    self.assertFalse(win_notify.toast("t", "b", key="dnd-routine"))
        ps.assert_not_called()

    def test_routine_toast_fires_outside_quiet_hours(self):
        with patch.dict(
            os.environ,
            {"CONTENT_TOAST": "true", "CONTENT_TOAST_FORCE": "true", "CONTENT_TOAST_DND": "true"},
        ):
            with patch.object(win_notify, "_toasts_muted", return_value=False):
                with patch.object(win_notify, "_toast_powershell", return_value=True) as ps:
                    self.assertTrue(win_notify.toast("t", "b", key="dnd-awake"))
        ps.assert_called_once()


class TestAlertsBypassDnd(unittest.TestCase):
    """Overnight batches run *inside* the quiet window, so breaker toasts must survive."""

    def setUp(self):
        win_notify._toasted.clear()

    def test_urgent_toast_ignores_the_mute(self):
        with patch.dict(
            os.environ,
            {"CONTENT_TOAST": "true", "CONTENT_TOAST_FORCE": "true", "CONTENT_TOAST_DND": "true"},
        ):
            with patch.object(win_notify, "_toasts_muted", return_value=True):
                with patch.object(win_notify, "_toast_powershell", return_value=True) as ps:
                    self.assertTrue(win_notify.toast("t", "b", key="dnd-urgent", urgent=True))
        ps.assert_called_once()

    def test_breaker_toast_still_fires_at_3am(self):
        with patch.dict(
            os.environ,
            {"CONTENT_TOAST": "true", "CONTENT_TOAST_FORCE": "true", "CONTENT_TOAST_DND": "true"},
        ):
            with patch.object(win_notify, "_toasts_muted", return_value=True):
                with patch.object(win_notify, "_toast_powershell", return_value=True) as ps:
                    win_notify.notify_breaker("Apify", "out of credits")
        ps.assert_called_once()

    def test_a_routine_notifier_does_not_claim_urgency(self):
        # Guards against `urgent=True` spreading to every notifier and re-killing DND.
        with patch.dict(
            os.environ,
            {"CONTENT_TOAST": "true", "CONTENT_TOAST_FORCE": "true", "CONTENT_TOAST_DND": "true"},
        ):
            with patch.object(win_notify, "_toasts_muted", return_value=True):
                with patch.object(win_notify, "_toast_powershell", return_value=True) as ps:
                    win_notify.notify_ffmpeg_done("clip.mp4")
        ps.assert_not_called()


if __name__ == "__main__":
    unittest.main()
