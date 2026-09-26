"""One place to ask "is the machine OK" (#869).

Seven verbs each answered part of it - doctor, free-doctor, secrets-doctor, health,
status, all-checks, reliability - so the operator had to know which to run. `ops status`
ends with these lines: one per family, each naming the verb that has the detail. Every
line is fail-open; a family that raises says so and the rest still print.
"""

from __future__ import annotations

from collections.abc import Callable

from core.logging import get_logger

logger = get_logger("core.status_summary")


def _doctor(channel_id: str) -> str:
    from core.ops_doctor import gather

    checks = gather(channel_id).get("checks") or []
    failing = [str(c.get("name")) for c in checks if not c.get("ok")]
    passed = len(checks) - len(failing)
    head = f"Doctor: {passed} of {len(checks)} checks pass"
    return head + (f"; failing: {', '.join(failing[:4])}" if failing else "")


def _secrets(channel_id: str) -> str:
    from core.secrets_doctor import gather

    data = gather(channel_id)
    missing = int(data.get("required_missing") or 0)
    placeholder = int(data.get("placeholder") or 0)
    if not missing and not placeholder:
        return "Keys: every required key present"
    bits = []
    if missing:
        bits.append(f"{missing} required key{'s' if missing != 1 else ''} missing")
    if placeholder:
        bits.append(f"{placeholder} placeholder{'s' if placeholder != 1 else ''}")
    return "Keys: " + ", ".join(bits)


def _health(channel_id: str) -> str:
    from core.channel_health import build_health, health_line

    return str(health_line(build_health(channel_id)))


def _budget(_channel_id: str) -> str:
    from core.reliability import summary_line

    return "Budget: " + summary_line()


FAMILIES: list[tuple[str, str, Callable[[str], str]]] = [
    ("Doctor", "ops doctor", _doctor),
    ("Keys", "ops secrets-doctor", _secrets),
    ("Health", "ops health", _health),
    ("Budget", "ops reliability", _budget),
]


def machine_lines(channel_id: str) -> list[str]:
    lines: list[str] = []
    for label, verb, fn in FAMILIES:
        try:
            lines.append(f"{fn(channel_id)}  (detail: {verb})")
        except Exception as exc:
            logger.debug("status %s line skipped: %s", label, exc)
            lines.append(f"{label}: unavailable (see {verb})")
    return lines
