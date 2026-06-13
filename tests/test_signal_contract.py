import unittest

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    make_signal,
    normalize_signal,
)


class TestSignalContract(unittest.TestCase):
    def test_connected_active_ok(self):
        sig = make_signal(connected=True, active=True, score=50)
        self.assertEqual(sig["status"], STATUS_OK)
        self.assertTrue(sig["connected"])
        self.assertTrue(sig["active"])

    def test_connected_inactive(self):
        sig = make_signal(connected=True, active=False, score=0)
        self.assertEqual(sig["status"], STATUS_INACTIVE)

    def test_disconnected_unavailable(self):
        sig = make_signal(connected=False, active=False)
        self.assertEqual(sig["status"], STATUS_UNAVAILABLE)

    def test_normalize_fills_status(self):
        raw = {"connected": True, "active": True, "score": 10}
        out = normalize_signal(raw)
        self.assertEqual(out["status"], STATUS_OK)


if __name__ == "__main__":
    unittest.main()
