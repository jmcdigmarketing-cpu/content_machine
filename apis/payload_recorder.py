"""Refresh the contract fixtures from the live APIs (#905).

`tests/fixtures/signal_payloads/<signal>.json` hold one response per pinned signal
(`apis/schema_pins`). They were written from each provider's documented shape, because
the build container cannot reach the APIs; this records the real ones on the operator's
PC. For each fixture it:

1. runs the fixture's signal once, with the operator's own keys (the fixture's test keys
   are never applied; its non-secret settings, such as `WEB_SEARCH_FALLBACK=false`, are),
   and the signal cache bypassed;
2. keeps the body of the pinned call (the first 200 whose URL is not one of the
   fixture's `other_responses`) and of each `other_responses` call;
3. checks the live body against its pin - a drifted answer is reported and never saved;
4. trims it to the fields the fixture already holds, with two items per list (or the
   fixture's `keep_items`), and names the fields the live answer no longer carries.

`apply=True` writes the trimmed bodies and dates the `note`. Dry run by default.
"""

from __future__ import annotations

import datetime
import importlib
import json
import os
import re
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from core.logging import get_logger

logger = get_logger("apis.payload_recorder")

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "signal_payloads"
_SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|_ID)$", re.IGNORECASE)


@dataclass
class Report:
    signal: str
    outcome: str  # recorded | skipped | failed | schema drift
    detail: str = ""
    missing: list[str] = field(default_factory=list)
    items: int = 0


def _merge(items: list[Any]) -> Any:
    """One template from a list's items: the union of their keys, recursively."""
    dicts = [i for i in items if isinstance(i, dict)]
    if not dicts:
        return items[0] if items else None
    merged: dict[str, Any] = {}
    for item in dicts:
        for key, value in item.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = _merge([merged[key], value])
            elif key not in merged:
                merged[key] = value
    return merged


def trim_like(live: Any, old: Any, *, keep_items: int = 2) -> Any:
    """`live` cut down to `old`'s shape: its keys only, `keep_items` per list."""
    if isinstance(old, dict) and isinstance(live, dict):
        return {k: trim_like(live[k], old[k], keep_items=keep_items) for k in old if k in live}
    if isinstance(old, list) and isinstance(live, list):
        if not old:
            return live[:keep_items]
        template = _merge(old)
        return [trim_like(item, template, keep_items=keep_items) for item in live[:keep_items]]
    return live


def _paths(node: Any, prefix: str = "") -> set[str]:
    out: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}{key}"
            out.add(path)
            out |= _paths(value, f"{path}.")
    elif isinstance(node, list):
        base = prefix[:-1] if prefix.endswith(".") else prefix
        for item in node:
            out |= _paths(item, f"{base}[].")
    return out


def missing_paths(old: Any, new: Any) -> list[str]:
    """Fields the fixture holds that the live answer no longer carries."""
    return sorted(_paths(old) - _paths(new))


def _live_env(fixture: dict[str, Any]) -> dict[str, str]:
    """The fixture's settings minus its test secrets (a blank still applies)."""
    return {
        name: value
        for name, value in (fixture.get("env") or {}).items()
        if value == "" or not _SECRET_NAME.search(name)
    }


def _spy(real: Any, calls: list[tuple[str, int, Any]]) -> Any:
    def wrapper(url: Any, *args: Any, **kwargs: Any) -> Any:
        resp = real(url, *args, **kwargs)
        body = None
        try:
            if resp.status_code == 200:
                body = resp.json()
        except Exception as exc:
            logger.debug("record-payloads: non-JSON body from %s: %s", url, exc)
        calls.append((str(url), int(resp.status_code), body))
        return resp

    return wrapper


def record(fixture: dict[str, Any]) -> tuple[Report, dict[str, Any] | None]:
    """(report, the fixture as it would be written, or None when nothing to save)."""
    import requests

    from apis.schema_pins import drift

    name = str(fixture.get("signal") or "")
    module_name, func_name = str(fixture["call"]).split(":")
    module = importlib.import_module(module_name)
    others = dict(fixture.get("other_responses") or {})
    calls: list[tuple[str, int, Any]] = []
    method = str(fixture.get("method") or "get")
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, _live_env(fixture)))
        for helper in ("get_cached", "set_cache"):
            if hasattr(module, helper):
                stack.enter_context(patch.object(module, helper, return_value=None))
        real = getattr(requests, method)
        stack.enter_context(patch(f"requests.{method}", side_effect=_spy(real, calls)))
        try:
            sig = getattr(module, func_name)(fixture["topic"])
        except Exception as exc:  # a signal must not raise; say so if one does
            return Report(name, "failed", f"{type(exc).__name__}: {exc}"), None
    status = str((sig or {}).get("status") or "")
    if status == "no_key":
        return Report(name, "skipped", str(sig.get("status_detail") or "no key")), None
    pinned = next(
        (
            body
            for url, code, body in calls
            if code == 200 and body is not None and not any(f in url for f in others)
        ),
        None,
    )
    if pinned is None:
        codes = ", ".join(str(code) for _url, code, _b in calls) or "no call"
        detail = str((sig or {}).get("status_detail") or "")
        return Report(
            name, "failed", f"no 200 from the pinned call ({codes}) {detail}".strip()
        ), None
    found = drift(name, pinned)
    if found:
        return Report(name, "schema drift", found), None
    keep = int(fixture.get("keep_items") or 2)
    new_response = trim_like(pinned, fixture.get("response"), keep_items=keep)
    new_others = dict(others)
    for fragment, old_body in others.items():
        body = next(
            (b for url, code, b in calls if code == 200 and b is not None and fragment in url),
            None,
        )
        if body is not None:
            new_others[fragment] = trim_like(body, old_body, keep_items=keep)
    missing = missing_paths(fixture.get("response"), new_response)
    items = _count_items(new_response)
    updated = dict(fixture)
    updated["response"] = new_response
    if others:
        updated["other_responses"] = new_others
    return Report(name, "recorded", status, missing, items), updated


def _count_items(node: Any) -> int:
    if isinstance(node, list):
        return len(node)
    if isinstance(node, dict):
        return max((_count_items(v) for v in node.values()), default=0)
    return 0


def record_all(
    folder: Path | str | None = None,
    *,
    only: str | None = None,
    apply: bool = False,
    today: str | None = None,
) -> list[Report]:
    """Record every fixture in `folder` (or the one named `only`); write when `apply`."""
    base = Path(folder or FIXTURES)
    day = today or datetime.date.today().isoformat()
    reports: list[Report] = []
    for path in sorted(base.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if only and fixture.get("signal") != only:
            continue
        report, updated = record(fixture)
        reports.append(report)
        if apply and updated is not None and report.outcome == "recorded":
            updated["note"] = (
                f"Recorded {day} from the live API by ops record-payloads (#905), trimmed "
                "to the fields the parser reads."
            )
            path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    return reports


def report_lines(reports: list[Report], *, apply: bool) -> list[str]:
    head = "Recorded payloads" + ("" if apply else " (dry run - nothing written; --apply saves)")
    lines = [head]
    for r in reports:
        if r.outcome == "recorded":
            what = f"{r.items} item(s)"
            gone = f"; no longer in the live answer: {', '.join(r.missing)}" if r.missing else ""
            lines.append(f"  {r.signal}: {'saved' if apply else 'would save'} {what}{gone}")
        else:
            lines.append(f"  {r.signal}: {r.outcome} - {r.detail}")
    if not reports:
        lines.append("  no fixture matched")
    return lines
