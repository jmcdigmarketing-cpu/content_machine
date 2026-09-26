"""A half-built ExitStack must not leak its patches into the rest of the suite.

`tests/test_ops_doctor._stack()` entered a dozen `patch()`es into an ExitStack and
returned it for a `with`. When a *later* target failed to import — `youtube.oauth`
on any box missing `googleapiclient` or a working `cryptography` — `_stack()` raised
before the `with` ever received the stack, so the patches already entered were never
exited. `core.run_mode._ollama_ready` stayed mocked to `(False, None)` and
`free_backend_readiness` to a `SimpleNamespace` for the rest of the process, which is
exactly how `tests/test_run69_fixes.py` passed 13/13 alone and failed under discovery
on a partial install (docs/audit_2026-09-26.md). On a full install the stack built
completely, so the operator's box never saw it.

This simulates the failure by making the Nth `patch()` raise, and asserts the
targets patched before it are restored. No network.
"""

from __future__ import annotations

import unittest
from unittest import mock

from core import run_mode


class TestStackUnwindsOnPartialFailure(unittest.TestCase):
    def test_a_failing_later_patch_restores_the_earlier_ones(self):
        from tests import test_ops_doctor as tod

        original_ready = run_mode._ollama_ready
        original_readiness = run_mode.free_backend_readiness
        real_patch = mock.patch
        calls = {"n": 0}

        def flaky_patch(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 4:  # the youtube.oauth target, in the real failure
                raise ImportError("simulated: target module cannot import")
            return real_patch(*args, **kwargs)

        with mock.patch.object(tod, "patch", flaky_patch):
            with self.assertRaises(ImportError):
                with tod._stack():
                    pass

        self.assertIs(run_mode._ollama_ready, original_ready, "_ollama_ready leaked a mock")
        self.assertIs(run_mode.free_backend_readiness, original_readiness)


if __name__ == "__main__":
    unittest.main()
