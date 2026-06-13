import unittest
from unittest.mock import patch

from apis.signal_chain import chain_signal
from apis.signal_contract import make_signal


class TestSignalChain(unittest.TestCase):
    def test_returns_first_active_provider(self):
        def good(_topic):
            return make_signal(connected=True, active=True, score=50)

        def unused(_topic):
            return make_signal(connected=True, active=True, score=90)

        result = chain_signal("test topic", [("first", good), ("second", unused)])
        self.assertTrue(result["active"])
        self.assertEqual((result.get("data") or {}).get("provider"), "first")

    def test_falls_through_on_failure(self):
        def fail(_topic):
            return make_signal(connected=False, active=False)

        def backup(_topic):
            return make_signal(connected=True, active=True, score=40)

        result = chain_signal(
            "test",
            [("a", fail), ("b", backup)],
            min_score=15,
        )
        self.assertEqual((result.get("data") or {}).get("provider"), "b")

    def test_records_fallback_chain(self):
        def low(_topic):
            return make_signal(connected=True, active=True, score=5)

        def high(_topic):
            return make_signal(connected=True, active=True, score=60)

        result = chain_signal("x", [("low", low), ("high", high)], min_score=15)
        chain = (result.get("data") or {}).get("fallback_chain") or []
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0]["provider"], "low")
        self.assertEqual(chain[1]["provider"], "high")


if __name__ == "__main__":
    unittest.main()
