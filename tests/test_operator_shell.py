"""#147 thin FastAPI operator shell — localhost GET, no spend POST.

Hits the real app via TestClient. Mocks gather/store I/O, never the route
handlers or reliability.render. Missing FastAPI is a fail, not a silent skip
(the [dev]/[shell] extra is required in CI).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover — extra not installed
    TestClient = None  # type: ignore[misc, assignment]


class TestOperatorShell(unittest.TestCase):
    def test_fastapi_extra_is_installed(self):
        self.assertIsNotNone(
            TestClient,
            "fastapi extra missing; pip install -e '.[dev]' (or .[shell])",
        )

    def test_reliability_prints_cache_dollars_saved_not_scare(self):
        if TestClient is None:
            self.fail("fastapi extra missing")
        from core.operator_shell import create_app

        fixture = {
            "apify": {},
            "llm": {},
            "signals": {},
            "cache": {
                "hits": 5,
                "misses": 0,
                "total": 5,
                "hit_rate": 1.0,
                "by_prefix": {"tiktok_trends": {"hits": 5, "misses": 0}},
            },
        }
        with patch("core.reliability.gather", return_value=fixture):
            with patch.dict("os.environ", {"COST_APIFY_PER_RUN": "0.02"}):
                client = TestClient(create_app())
                resp = client.get("/reliability")
        self.assertEqual(resp.status_code, 200)
        body = resp.text.lower()
        self.assertIn("saved", body)
        self.assertIn("$0.10", resp.text)
        self.assertNotIn("error 500", body)

    def test_next_returns_a_sentence(self):
        if TestClient is None:
            self.fail("fastapi extra missing")
        from core.operator_shell import create_app, next_sentence

        with (
            patch("core.run_mode.projected_cost_block_reason", return_value=None),
            patch("core.fact_expiry.warning_lines", return_value=[]),
            patch(
                "core.publish_blockers.blocking_publish_sentence",
                return_value="Nothing is blocking publish: grade, authenticity, quota, and facts look clear.",
            ),
        ):
            self.assertIn("blocking publish", next_sentence("tapin").lower())
            client = TestClient(create_app())
            resp = client.get("/next")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("blocking publish", resp.text.lower())
        self.assertGreater(len(resp.text.strip()), 8)

    def test_index_lists_routes_and_has_no_spend_post(self):
        if TestClient is None:
            self.fail("fastapi extra missing")
        from core.operator_shell import create_app

        app = create_app()
        methods = {(r.path, m) for r in app.routes for m in getattr(r, "methods", []) or []}
        self.assertIn(("/", "GET"), methods)
        self.assertIn(("/reliability", "GET"), methods)
        self.assertIn(("/booth", "GET"), methods)
        self.assertIn(("/doctor", "GET"), methods)
        self.assertIn(("/next", "GET"), methods)
        self.assertIn(("/status", "GET"), methods)
        spend_posts = {
            p
            for p, m in methods
            if m == "POST"
            and any(k in p.lower() for k in ("tts", "apify", "publish", "llm", "generate"))
        }
        self.assertEqual(spend_posts, set())

    def test_bind_host_is_localhost_only(self):
        from core.operator_shell import BIND_HOST

        self.assertEqual(BIND_HOST, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
