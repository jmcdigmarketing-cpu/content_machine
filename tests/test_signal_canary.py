"""#383 — exercise every signal at zero spend so a dead source is found before a
real run needs it.

The failure this exists to catch is the Tapology class: a source that answered
"no match" for 33 days while actually returning a Cloudflare 403, and nothing
noticed because no run ever asked whether the source was *alive* as opposed to
*empty*.

Isolation matters more than usual here. The canary touches signal fetching, and
`register_signals._fetch_one` both reads the shared cache and calls
`_record_signal_health`, which can persist a breaker trip to
`data/quota_state.json` for up to a billing cycle. A canary that tripped the real
breaker would disable a signal for the operator's *next live run* — the exact
harm it is supposed to prevent. These tests inherit the mandated isolation base
(tests/CLAUDE.md) and assert the no-trip property directly.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import apis.register_signals as rs
from apis.signal_contract import (
    STATUS_AUTH,
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    make_signal,
)
from core import quota_state, signal_canary


class _IsolatedStateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp.name, "q.json")
        )
        self._state_patch.start()
        rs.reset_session_breaker()

    def tearDown(self):
        rs.reset_session_breaker()
        self._state_patch.stop()
        self._tmp.cleanup()


def _ok(_topic):
    return make_signal(connected=True, active=True, score=50, status=STATUS_OK)


def _auth_dead(_topic):
    return make_signal(connected=False, active=False, status=STATUS_AUTH)


def _no_match(_topic):
    """Reached the source; it had nothing for this topic. Healthy."""
    return make_signal(connected=True, active=False, status=STATUS_INACTIVE)


def _no_key(_topic):
    return make_signal(connected=False, active=False, status=STATUS_NO_KEY)


def _raises(_topic):
    raise RuntimeError("boom")


class TestTheCanaryProbesWhatItClaimsTo(_IsolatedStateCase):
    def test_every_registered_signal_gets_a_row(self):
        rows = signal_canary.check_signals({"a": _ok, "b": _auth_dead})
        self.assertEqual({r["name"] for r in rows}, {"a", "b"})

    def test_a_dead_signal_is_reported_dead_not_empty(self):
        """The Tapology case: 'no match' and 'I am broken' must not look alike."""
        rows = {r["name"]: r for r in signal_canary.check_signals({"b": _auth_dead})}
        self.assertNotEqual(rows["b"]["status"], STATUS_OK)
        self.assertTrue(signal_canary.warnings(list(rows.values())))

    def test_a_raising_signal_is_caught_and_reported(self):
        rows = signal_canary.check_signals({"c": _raises})
        self.assertIn("RuntimeError", rows[0]["detail"])
        self.assertTrue(signal_canary.warnings(rows))

    def test_a_healthy_run_produces_no_warnings(self):
        self.assertEqual(signal_canary.warnings(signal_canary.check_signals({"a": _ok})), [])

    def test_no_match_is_not_a_dead_source(self):
        """Decision §18 turned inward. The probe topic is a UFC string, so
        `coingecko`, `igdb` and `tmdb` *should* answer empty — reporting those as
        dead would cry wolf on ~15 signals a night and the canary would be
        ignored, which is worse than not having one.

        Measured against the real registry before this distinction existed: 15 of
        33 were reported dead, and most were healthy sources with nothing to say.
        """
        rows = signal_canary.check_signals({"coingecko": _no_match})
        self.assertEqual(signal_canary.warnings(rows), [], rows)
        self.assertIn("coingecko", signal_canary.render(rows))

    def test_an_unconfigured_optional_key_is_not_a_dead_source(self):
        """`ops doctor` owns required-vs-optional keys. A canary that stays red
        because an optional key is unset is a canary nobody reads."""
        rows = signal_canary.check_signals({"api_sports": _no_key})
        self.assertEqual(signal_canary.warnings(rows), [], rows)


class TestItCannotSpendAndCannotTripTheBreaker(_IsolatedStateCase):
    def test_paid_signals_are_skipped_by_default(self):
        """`_APIFY_PAID_SIGNALS` is the authoritative set — not a second hand-list."""
        probed = {}

        def _spy(name):
            def fn(_topic):
                probed[name] = True
                return _ok(_topic)

            return fn

        registry = {name: _spy(name) for name in rs._APIFY_PAID_SIGNALS}
        registry["free_one"] = _spy("free_one")
        rows = {r["name"]: r for r in signal_canary.check_signals(registry)}

        self.assertEqual(probed, {"free_one": True}, f"a paid signal was called: {probed}")
        for paid in rs._APIFY_PAID_SIGNALS:
            self.assertEqual(rows[paid]["status"], "skipped", paid)
        self.assertEqual(signal_canary.warnings(list(rows.values())), [])

    def test_an_auth_failure_does_not_disable_the_signal_for_the_next_real_run(self):
        """The whole safety argument. A nightly canary that trips the persisted
        breaker would take a signal out of the operator's next live run."""
        before = set(rs.disabled_signals())
        signal_canary.check_signals({"tapology": _auth_dead})
        self.assertEqual(set(rs.disabled_signals()), before)

    def test_it_does_not_answer_from_cache(self):
        """A cache hit proves the cache is warm, not that the source is alive —
        which is precisely how Tapology stayed 'fine' for 33 days."""
        calls = []

        def counting(_topic):
            calls.append(1)
            return _ok(_topic)

        with patch.object(rs, "get_cached", return_value=_ok("x")) as cached:
            signal_canary.check_signals({"a": counting})
        self.assertEqual(len(calls), 1, "the real signal function was not called")
        cached.assert_not_called()


class TestRenderIsOperatorSafe(_IsolatedStateCase):
    def test_render_is_cp1252_safe(self):
        """Candidate 250: the operator's console is cp1252 and a stray glyph
        raises UnicodeEncodeError mid-report."""
        rows = signal_canary.check_signals({"a": _ok, "b": _auth_dead})
        signal_canary.render(rows).encode("cp1252")

    def test_render_names_every_signal(self):
        rows = signal_canary.check_signals({"a": _ok, "b": _auth_dead})
        out = signal_canary.render(rows)
        self.assertIn("a", out)
        self.assertIn("b", out)


class TestTheOpsVerbIsRegistered(unittest.TestCase):
    def test_signal_canary_is_a_command(self):
        """Named `signal-canary`, not `canary`: `policy-canary` already exists."""
        from scripts.ops import COMMANDS

        self.assertIn("signal-canary", COMMANDS)

    def test_all_checks_does_not_run_the_canary(self):
        """#663. CI has no network; putting the canary in all-checks would fail
        every build. Inspect the live batch, not a comment."""
        import inspect

        from scripts import ops

        source = inspect.getsource(ops.cmd_all_checks)
        self.assertNotIn("signal-canary", source)
        self.assertIn("feeds", source)


class TestOvernightRunsTheCanary(_IsolatedStateCase):
    """#663. The module existed; nothing nightly called it."""

    def test_overnight_probes_and_persists(self):
        from core import overnight

        rows = [
            {
                "name": "wikipedia",
                "status": STATUS_OK,
                "connected": True,
                "active": True,
                "detail": "",
            }
        ]
        with (
            patch("core.batch_generation.collect_topics", return_value=["a"]),
            patch("core.batch_generation.run_batch", return_value=[]),
            patch("core.vault_dossiers.write_run_dossier", return_value=None),
            patch("core.channel_health.build_health"),
            patch("core.channel_health.health_line", return_value=""),
            patch("core.events.emit_event", return_value=True),
            patch("core.signal_canary.check_signals", return_value=rows) as probe,
            patch("core.signal_canary.save_results") as save,
        ):
            result = overnight.run_overnight("tapin", count=1)
        probe.assert_called_once()
        save.assert_called_once_with(rows)
        self.assertIn("wikipedia", result.canary_line)
        self.assertIn("wikipedia", overnight.render_overnight(result))

    def test_a_dead_signal_surfaces_in_the_overnight_report(self):
        from apis.signal_contract import STATUS_AUTH
        from core import overnight

        rows = [
            {
                "name": "tapology",
                "status": STATUS_AUTH,
                "connected": False,
                "active": False,
                "detail": "403",
            }
        ]
        with (
            patch("core.batch_generation.collect_topics", return_value=["a"]),
            patch("core.batch_generation.run_batch", return_value=[]),
            patch("core.vault_dossiers.write_run_dossier", return_value=None),
            patch("core.channel_health.build_health"),
            patch("core.channel_health.health_line", return_value=""),
            patch("core.events.emit_event", return_value=True),
            patch("core.signal_canary.check_signals", return_value=rows),
            patch("core.signal_canary.save_results"),
        ):
            result = overnight.run_overnight("tapin", count=1)
        self.assertIn("tapology", result.canary_line)
        self.assertIn("DEAD", result.canary_line)


if __name__ == "__main__":
    unittest.main()
