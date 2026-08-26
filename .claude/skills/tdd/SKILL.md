---
name: tdd
description: >-
  Write the test first, watch it fail on unmodified code, then fix. Use when
  adding a gate, check, repair pass, or any behaviour that CI could otherwise
  score green while doing nothing.
---

# Fail-then-fix (Content OS)

This repo's last three audit passes were green in CI while the features did
nothing. The tests were sincere and structurally incapable of failing: they
mocked the call under test, asserted a key existed instead of a parser
returning a URL, or scored the post-rewrite number and threw away the
pre-repair one.

## The loop (non-negotiable)

1. **Write the behavioural test first.** Call the real function. Mock network,
   clock, filesystem, and LLM — never mock the function under test, and never
   the call the change depends on.
2. **Run it against unmodified code.** Confirm it fails for the reason you
   named. A test that was green before the fix is not testing the fix.
3. **Implement the smallest change that makes that failure go away.**
4. **Re-run the same test**, then lint, then the suite:
   `python -m unittest discover -s tests -t .` (the `-t .` is load-bearing).

## Assert behaviour, not shape

- Not `assertIn("source_url", meta)` — call the parser and assert it returns a URL.
- Not "the function exists" — call it with a real input and check what it does.
- Exercise shipped `config/channels.json` when production reads it.
- If a live run exposed the bug, put that run's actual strings in the test.
- When a fix does not cover a case, assert the remaining gap with a docstring
  that says why and what would close it.

## Fail-open is fail-visible

A swallowed exception logs: `warning` when a guarantee is lost, `debug` for
best-effort enrichment. A healthy run emits zero new warnings. A pass that
rewrites its input persists the pre-repair number too.

## Do not

- Copy unlicensed third-party skill files into this tree.
- Mock `quiet_hours_reason` to prove quiet hours work.
- Write real `data/` or the operator vault from a test.
