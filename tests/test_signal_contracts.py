"""#626: every pinned signal is held to a recorded response, and to its pin.

No test fed a signal a real response shape: each signal's tests built the payload they
expected, so a parser and its fake could drift together. This file is generated from
`tests/fixtures/signal_payloads/<signal>.json` - one per pin in `apis/schema_pins` - and
for each fixture it:

1. serves the recorded response to the signal (no network) and requires a healthy,
   `make_signal`-shaped, active answer with data;
2. deletes each pinned key in turn (the container, then each item key from every item)
   and requires `STATUS_UPSTREAM` "schema drift: ..." instead of a quiet "no match".

A fixture whose signal has no pin fails, and so does a pin with no fixture.
"""

from __future__ import annotations

import copy
import importlib
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from apis.schema_pins import PINS
from apis.signal_contract import STATUS_OK, STATUS_UPSTREAM, normalize_signal

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "signal_payloads"


def _fixtures() -> dict[str, dict[str, Any]]:
    out = {}
    for path in sorted(FIXTURES.glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        out[body["signal"]] = body
    return out


def _response(body: Any, headers: dict[str, str] | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = copy.deepcopy(body)
    resp.text = json.dumps(body)
    resp.headers = dict(headers or {})
    return resp


def _call(fixture: dict[str, Any], response: Any) -> dict[str, Any]:
    """Run the fixture's signal with `response` as the pinned endpoint's body."""
    module_name, func_name = fixture["call"].split(":")
    module = importlib.import_module(module_name)
    others = fixture.get("other_responses") or {}

    def serve(url, *_a, **_kw):
        for fragment, body in others.items():
            if fragment in str(url):
                return _response(body)
        return _response(response, fixture.get("headers"))

    with ExitStack() as stack:
        stack.enter_context(patch.dict("os.environ", fixture.get("env") or {}))
        for attr, value in (fixture.get("attrs") or {}).items():
            value = tuple(value) if isinstance(value, list) else value
            stack.enter_context(patch.object(module, attr, value))
        for name in ("get_cached", "set_cache"):
            if hasattr(module, name):
                stack.enter_context(patch.object(module, name, return_value=None))
        method = fixture.get("method", "get")
        stack.enter_context(patch(f"requests.{method}", side_effect=serve))
        return getattr(module, func_name)(fixture["topic"])


def _drifted(fixture: dict[str, Any]) -> list[tuple[str, Any]]:
    """(label, payload) for each pinned key removed from the recorded response."""
    container, item_keys = PINS[fixture["signal"]]
    response = fixture["response"]
    out: list[tuple[str, Any]] = []
    if container is not None:
        gone = copy.deepcopy(response)
        del gone[container]
        out.append((f"no `{container}`", gone))
    for key in item_keys:
        gone = copy.deepcopy(response)
        items = gone if container is None else gone[container]
        for item in items:
            item.pop(key, None)
        out.append((f"items without `{key}`", gone))
    return out


class SignalContractTests(unittest.TestCase):
    def test_every_fixture_has_a_pin_and_every_pin_a_fixture(self):
        fixtures = _fixtures()
        self.assertEqual(sorted(fixtures), sorted(PINS))
        for name, body in fixtures.items():
            with self.subTest(signal=name):
                self.assertTrue(body.get("note"), "say where the payload came from")

    def test_the_recorded_response_is_healthy(self):
        for name, fixture in _fixtures().items():
            with self.subTest(signal=name):
                sig = _call(fixture, fixture["response"])
                self.assertEqual(sig.get("status"), STATUS_OK, sig.get("status_detail"))
                self.assertTrue(sig.get("active"))
                self.assertTrue(sig.get("data"))
                self.assertEqual(normalize_signal(sig), sig)

    def test_a_removed_pinned_key_is_reported_as_drift(self):
        for name, fixture in _fixtures().items():
            for label, payload in _drifted(fixture):
                with self.subTest(signal=name, drift=label):
                    sig = _call(fixture, payload)
                    self.assertEqual(sig.get("status"), STATUS_UPSTREAM, sig)
                    self.assertFalse(sig.get("active"))
                    self.assertTrue(str(sig.get("status_detail")).startswith("schema drift:"))


if __name__ == "__main__":
    unittest.main()
