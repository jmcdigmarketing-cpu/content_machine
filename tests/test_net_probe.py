"""Wave 77 (#393): the internet being down reads as one thing, not seven signal failures."""

from __future__ import annotations

import unittest
from unittest.mock import patch


def _down(detail="HTTPSConnectionPool(host='x'): Max retries exceeded (NameResolutionError)"):
    return {"connected": False, "active": False, "status": "unavailable", "status_detail": detail}


def _up():
    return {"connected": True, "active": True, "status": "ok", "status_detail": ""}


OFFLINE = {name: _down() for name in ("news", "trends", "steam", "rawg", "youtube", "odds")}


class LooksOfflineTests(unittest.TestCase):
    def test_most_signals_failing_to_connect_is_the_network(self):
        from apis.net_probe import looks_offline

        self.assertEqual(
            looks_offline(OFFLINE), ["news", "odds", "rawg", "steam", "trends", "youtube"]
        )

    def test_a_few_failures_among_many_working_signals_is_not(self):
        from apis.net_probe import looks_offline

        signals = {f"ok{i}": _up() for i in range(10)}
        signals.update({name: _down() for name in ("news", "trends", "steam", "rawg")})
        self.assertEqual(looks_offline(signals), [])

    def test_fewer_than_four_is_not_enough(self):
        from apis.net_probe import looks_offline

        self.assertEqual(looks_offline({n: _down() for n in ("news", "trends", "steam")}), [])

    def test_a_quota_or_auth_failure_is_not_a_connection_failure(self):
        from apis.net_probe import failed_to_connect

        signals = {
            "a": _down("quota exceeded"),
            "b": _down("401 unauthorized"),
            "c": _down("read timed out"),
            "d": _down(""),
        }
        self.assertEqual(failed_to_connect(signals), ["c"])


class OfflineLineTests(unittest.TestCase):
    def test_a_failed_probe_says_it_once(self):
        from apis.net_probe import offline_line

        line = offline_line(OFFLINE, probe=lambda: False)
        self.assertIn("The internet looks down: 6 signals could not connect", line)
        self.assertIn("Nothing is wrong with them", line)

    def test_a_passing_probe_says_nothing(self):
        from apis.net_probe import offline_line

        self.assertEqual(offline_line(OFFLINE, probe=lambda: True), "")

    def test_the_probe_is_not_asked_when_signals_are_fine(self):
        from apis.net_probe import offline_line

        asked = []
        self.assertEqual(
            offline_line({"news": _up(), "steam": _down()}, probe=lambda: asked.append(1)), ""
        )
        self.assertEqual(asked, [])

    def test_online_is_false_when_the_request_raises(self):
        from apis import net_probe

        with patch("requests.head", side_effect=OSError("no route")):
            self.assertFalse(net_probe.online())

    def test_online_is_true_when_the_host_answers(self):
        from apis import net_probe

        with patch("requests.head", return_value=object()) as head:
            self.assertTrue(net_probe.online())
        head.assert_called_once_with(net_probe.PROBE_URL, timeout=2.0)

    def test_the_health_screen_prints_it_first(self):
        from core.ui import display_signal_health

        printed: list[str] = []
        with patch("apis.net_probe.online", return_value=False):
            display_signal_health(
                OFFLINE, print_fn=lambda *a: printed.append(" ".join(map(str, a))), ask=False
            )
        text = "\n".join(printed)
        self.assertIn("The internet looks down", text)

    def test_the_health_screen_says_nothing_when_online(self):
        from core.ui import display_signal_health

        printed: list[str] = []
        with patch("apis.net_probe.online", return_value=True):
            display_signal_health(
                OFFLINE, print_fn=lambda *a: printed.append(" ".join(map(str, a))), ask=False
            )
        self.assertNotIn("The internet looks down", "\n".join(printed))


class LedgerTests(unittest.TestCase):
    def test_an_offline_run_is_one_incident(self):
        from core.incident_ledger import rank_incidents

        incidents = rank_incidents([{"at": 1000.0, "signals": OFFLINE}], now=1000.0)
        self.assertEqual(
            [(i.kind, i.name, i.count) for i in incidents], [("network", "connection", 1)]
        )
        self.assertEqual(incidents[0].reasons, {"6 signals could not connect": 1})

    def test_other_failures_in_that_run_still_count(self):
        from core.incident_ledger import rank_incidents

        signals = dict(OFFLINE, tiktok_trends=_down("quota exceeded"))
        signals["tiktok_trends"]["status"] = "quota_exceeded"
        incidents = rank_incidents([{"at": 1000.0, "signals": signals}], now=1000.0)
        self.assertEqual(
            sorted((i.kind, i.name) for i in incidents),
            [("network", "connection"), ("signal", "tiktok_trends")],
        )

    def test_one_signal_failing_to_connect_is_still_its_own_incident(self):
        from core.incident_ledger import rank_incidents

        signals = {"news": _down(), "steam": _up(), "rawg": _up()}
        incidents = rank_incidents([{"at": 1000.0, "signals": signals}], now=1000.0)
        self.assertEqual([(i.kind, i.name) for i in incidents], [("signal", "news")])


if __name__ == "__main__":
    unittest.main()
