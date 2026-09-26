"""#485. Re-entering a topic must not pay discovery twice."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core import pipeline


def _discovery_env(**extra: str):
    env = {"COMPETITOR_SYNC_ON_DISCOVERY": "off", "APIFY_CONTENT_MACHINE_KEY": "", **extra}
    # The suite runs with DISCOVERY_CACHE=false (tests/__init__.py, #828); this module is
    # the one that tests the cache, so it turns it on unless a test says otherwise.
    env.setdefault("DISCOVERY_CACHE", "true")
    return patch.dict(os.environ, env, clear=False)


class TestDiscoveryPersist(unittest.TestCase):
    def test_second_call_does_not_refetch(self):
        variants = patch("core.pipeline.generate_variants", return_value=["angle one"])
        registry = patch(
            "core.pipeline.build_registry",
            return_value={"youtube": {"score": 1, "status": "ok"}},
        )
        with (
            variants as v,
            registry as r,
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            _discovery_env(),
        ):
            first = pipeline.run_discovery("GTA 6 persist-a", channel_id="tapin")
            second = pipeline.run_discovery("GTA 6 persist-a", channel_id="tapin")
        self.assertEqual(v.call_count, 1)
        self.assertEqual(r.call_count, 2, "scoring calls build_registry once more on the first run")
        self.assertEqual(first.evaluated[0][0], second.evaluated[0][0])
        self.assertEqual(second.evaluated[0][0], "angle one")

    def test_the_operator_is_told_how_old_the_reused_discovery_is(self):
        """The reuse notice names the topic but not the age, and the TTL is 90
        minutes. An 89-minute-old discovery and a 2-minute-old one are the same
        line to the operator — on a breaking topic they are not the same thing,
        and freshness decay is the documented run-73 failure ("each run made the
        next less fresh").

        Precedent for naming it: `feed_health` prints "check is Nd old" and
        `competitor_context` prints the snapshot age in hours.
        """
        printed: list[str] = []
        with (
            patch("core.pipeline.generate_variants", return_value=["angle one"]),
            patch(
                "core.pipeline.build_registry",
                return_value={"youtube": {"score": 1, "status": "ok"}},
            ),
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            _discovery_env(),
        ):
            pipeline.run_discovery("GTA 6 persist-age", channel_id="tapin")
            with patch(
                "builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))
            ):
                pipeline.run_discovery("GTA 6 persist-age", channel_id="tapin")

        reuse = [ln for ln in printed if "Reused discovery" in ln]
        self.assertTrue(reuse, printed)
        self.assertRegex(
            reuse[0], r"\d+\s*(s|m|min)", f"reuse notice does not say how old: {reuse[0]!r}"
        )

    def test_channels_do_not_share_a_payload(self):
        with (
            patch("core.pipeline.generate_variants", side_effect=[["tapin angle"], ["mw angle"]]),
            patch(
                "core.pipeline.build_registry",
                return_value={"youtube": {"score": 1, "status": "ok"}},
            ),
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            _discovery_env(),
        ):
            tapin = pipeline.run_discovery("shared persist topic", channel_id="tapin")
            money = pipeline.run_discovery("shared persist topic", channel_id="moneywise")
        self.assertEqual(tapin.evaluated[0][0], "tapin angle")
        self.assertEqual(money.evaluated[0][0], "mw angle")

    def test_expired_payload_refetches(self):
        clock = {"now": 1_000_000.0}

        def _time():
            return clock["now"]

        variants = patch("core.pipeline.generate_variants", return_value=["fresh"])
        registry = patch(
            "core.pipeline.build_registry",
            return_value={"youtube": {"score": 1, "status": "ok"}},
        )
        with (
            variants as v,
            registry,
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            patch("apis.cache_manager.time.time", side_effect=_time),
            _discovery_env(DISCOVERY_CACHE_TTL_SECONDS="60"),
        ):
            pipeline.run_discovery("GTA 6 persist-ttl", channel_id="tapin")
            clock["now"] += 120
            pipeline.run_discovery("GTA 6 persist-ttl", channel_id="tapin")
        self.assertEqual(v.call_count, 2)
