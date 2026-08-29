"""Rumor voice (#346) — leak topics must not assert unattributed delays.

Mirrors ``core/odds_language.py``: prompt rules already ask for attribution;
this pass enforces it on leak/rumor topics. A result/recap topic is left
alone. Default-on; fail-open at the call site.
"""

from __future__ import annotations

import os
import re

from core.logging import get_logger

logger = get_logger("core.rumor_language")

_LEAK_TOPIC = re.compile(
    r"\b(leak|leaked|rumor|rumour|unconfirmed|reportedly)\b",
    re.IGNORECASE,
)
_OUTLET = re.compile(
    r"\b(bloomberg|reuters|espn|the athletic|insider|kotaku|ign|"
    r"gamespot|polygon|resetera|twitter|tweet|according to)\b",
    re.IGNORECASE,
)
_ATTRIBUTED = re.compile(
    r"\b(reportedly|reports? (?:claim|say|said)|the rumor is|unconfirmed|" r"according to)\b",
    re.IGNORECASE,
)
_REPORTS_TO = re.compile(r"\breports to\b", re.IGNORECASE)
_ASSERT_DELAY = re.compile(
    r"\b(is delayed|has been delayed|will (?:slip|be delayed)|slips to)\b",
    re.IGNORECASE,
)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def rumor_language_enabled() -> bool:
    return _flag("RUMOR_LANGUAGE", True)


def is_leak_topic(topic: str) -> bool:
    return bool(_LEAK_TOPIC.search(topic or ""))


def apply_rumor_language(script: str, *, topic: str = "") -> tuple[str, list[str]]:
    """Soften unattributed assertions on leak/rumor topics.

    Requires an outlet-shaped token *in the script* (known gap: corpus outlets
    are not copied in). Leaves result lines and 'reports to <employer>' alone.
    """
    if not rumor_language_enabled() or not (script or "").strip():
        return script, []
    if not is_leak_topic(topic):
        return script, []
    notes: list[str] = []
    lines = (script or "").splitlines()
    out: list[str] = []
    for line in lines:
        if _REPORTS_TO.search(line):
            out.append(line)
            continue
        if _ATTRIBUTED.search(line) or _OUTLET.search(line):
            out.append(line)
            continue
        if _ASSERT_DELAY.search(line) or re.search(r"\b(is coming|will launch)\b", line, re.I):
            softened = re.sub(
                r"^(\s*)",
                r"\1Reports claim ",
                line,
                count=1,
            )
            if softened == line:
                softened = f"Reports claim {line}"
            out.append(softened)
            notes.append("rumor language: attributed an unconfirmed leak claim")
            continue
        out.append(line)
    return "\n".join(out), notes
