"""Process-global state must not leak from one test into the next.

`tests/test_run69_fixes.py` passes 13/13 alone and failed 5 under full discovery
(docs/audit_2026-09.md §1.3): `core/llm_router._ollama_probe_cache` is a module
global, and once any earlier test warms it, patching `ollama_installed_models`
stops mattering. The polluter is `tests/test_run66_fixes.py` calling
`ollama_installed_models(refresh=True)` with `requests.get` mocked to fail, which
leaves `(False, [])` in the cache for every later test in the process.

Three files reset that one global by hand; ~35 other module-level mutables have
no reset path at all (audit_2026-09-26.md). The fix is one registry
(`core.process_state`) that every state-owning module registers with at import,
and one hook in `tests/__init__.py` that calls `reset_all()` before every test.

No network. Requires `-t .` (the hook lives in the tests package __init__).
"""

from __future__ import annotations

import unittest

from core import llm_router


class TestRegistry(unittest.TestCase):
    def test_reset_all_calls_every_registered_reset(self):
        from core import process_state

        calls: list[str] = []
        process_state.register_reset("tests.probe", lambda: calls.append("x"))
        try:
            process_state.reset_all()
            self.assertEqual(calls, ["x"])
        finally:
            process_state.unregister_reset("tests.probe")

    def test_registration_is_idempotent_by_name(self):
        # A module re-imported by a test (importlib.reload) must not stack resets.
        from core import process_state

        calls: list[str] = []
        process_state.register_reset("tests.probe", lambda: calls.append("first"))
        process_state.register_reset("tests.probe", lambda: calls.append("second"))
        try:
            process_state.reset_all()
            self.assertEqual(calls, ["second"])
        finally:
            process_state.unregister_reset("tests.probe")

    def test_a_failing_reset_names_its_owner(self):
        from core import process_state

        def boom() -> None:
            raise RuntimeError("bad reset")

        process_state.register_reset("tests.boom", boom)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                process_state.reset_all()
            self.assertIn("tests.boom", str(ctx.exception))
        finally:
            process_state.unregister_reset("tests.boom")

    def test_the_state_owning_modules_are_registered(self):
        # The modules the survey found with no reset path. Importing them is what
        # registers them, so import here, then check the registry names.
        import apis.apify_catalog
        import core.analyst_accuracy
        import core.grade_calibration
        import core.tts
        import core.vault_relevance
        from core import process_state

        names = set(process_state.registered())
        for owner in (
            "core.llm_router",
            "core.tts",
            "core.vault_relevance",
            "core.grade_calibration",
            "core.analyst_accuracy",
            "apis.apify_catalog",
        ):
            with self.subTest(owner=owner):
                self.assertIn(owner, names)


class TestSuiteResetsBetweenTests(unittest.TestCase):
    """Alphabetical method order makes this deterministic: `test_a_*` runs first."""

    def test_a_warms_the_ollama_probe_cache(self):
        llm_router._ollama_probe_cache = (False, [])
        self.assertIsNotNone(llm_router._ollama_probe_cache)

    def test_b_starts_with_it_cleared(self):
        self.assertIsNone(
            llm_router._ollama_probe_cache,
            "test_a's probe result leaked into this test — reset_all() did not run",
        )

    def test_c_the_client_cache_is_cleared_too(self):
        # _clients captures the first api_key it sees; a stale client is how a test
        # with one provider key can score against another test's key.
        self.assertEqual(llm_router._clients, {})


if __name__ == "__main__":
    unittest.main()
