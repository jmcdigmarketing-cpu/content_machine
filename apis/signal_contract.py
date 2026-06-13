"""
Standard signal result shape and health display labels.

Every signal should include:
  connected, active, score, confidence, data (optional),
  status, status_detail (optional human-readable hint)
"""

from __future__ import annotations

STATUS_OK = "ok"
STATUS_INACTIVE = "inactive"
STATUS_NO_KEY = "no_key"
STATUS_QUOTA = "quota_exceeded"
STATUS_RATE_LIMIT = "rate_limited"
STATUS_AUTH = "auth_error"
STATUS_UPSTREAM = "upstream_error"
STATUS_HTTP = "http_error"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ERROR = "error"

HEALTH_LABELS = {
    STATUS_OK: "ON",
    STATUS_INACTIVE: "ON (not active)",
    STATUS_NO_KEY: "OFF (no API key)",
    STATUS_QUOTA: "QUOTA EXCEEDED",
    STATUS_RATE_LIMIT: "RATE LIMITED",
    STATUS_AUTH: "AUTH FAILED",
    STATUS_UPSTREAM: "UPSTREAM ERROR",
    STATUS_HTTP: "HTTP ERROR",
    STATUS_UNAVAILABLE: "OFF",
    STATUS_ERROR: "ERROR",
}


def make_signal(
    *,
    connected: bool,
    active: bool,
    score: float = 0,
    confidence: float = 0,
    data=None,
    status: str | None = None,
    status_detail: str | None = None,
):
    if status is None:
        if not connected:
            status = STATUS_UNAVAILABLE
        elif active:
            status = STATUS_OK
        else:
            status = STATUS_INACTIVE

    return {
        "connected": connected,
        "active": active,
        "score": score,
        "confidence": confidence,
        "data": data,
        "status": status,
        "status_detail": status_detail,
    }


def classify_http(status_code: int, body_text: str = ""):
    text = (body_text or "").lower()

    if status_code == 429:
        return STATUS_RATE_LIMIT, "Too many requests (429)"

    if status_code == 401:
        return STATUS_AUTH, "Unauthorized (401)"

    if status_code == 403:
        if any(
            token in text for token in ("quota", "limit exceeded", "daily limit", "usage limit")
        ):
            return STATUS_QUOTA, "API quota or usage limit (403)"
        return STATUS_AUTH, "Forbidden (403)"

    if status_code == 402:
        return STATUS_QUOTA, "Payment or quota required (402)"

    if status_code >= 500:
        return STATUS_UPSTREAM, f"Server error ({status_code})"

    if status_code >= 400:
        return STATUS_HTTP, f"Request failed ({status_code})"

    return STATUS_ERROR, f"Unexpected status ({status_code})"


def classify_exception(exc: BaseException):
    message = str(exc).lower()

    if "quota" in message or "quotaexceeded" in message:
        return STATUS_QUOTA, str(exc)[:120]

    if "rate limit" in message or "too many requests" in message:
        return STATUS_RATE_LIMIT, str(exc)[:120]

    if "invalid api key" in message or "unauthorized" in message or "forbidden" in message:
        return STATUS_AUTH, str(exc)[:120]

    return STATUS_ERROR, str(exc)[:120]


def normalize_signal(signal: dict) -> dict:
    """Fill status on older results; infer quota/rate hints from detail text."""
    if not signal:
        return make_signal(connected=False, active=False, status=STATUS_UNAVAILABLE)

    signal = dict(signal)
    detail = signal.get("status_detail") or ""
    detail_lower = detail.lower()

    if signal.get("status"):
        return signal

    if not signal.get("connected"):
        status = STATUS_UNAVAILABLE
        if "quota" in detail_lower:
            status = STATUS_QUOTA
        elif "rate" in detail_lower or "429" in detail_lower:
            status = STATUS_RATE_LIMIT
        elif "401" in detail_lower or "403" in detail_lower or "auth" in detail_lower:
            status = STATUS_AUTH
        signal["status"] = status
        return signal

    if signal.get("active"):
        signal["status"] = STATUS_OK
    else:
        signal["status"] = STATUS_INACTIVE

    return signal


def format_health_line(name: str, signal: dict) -> str:
    signal = normalize_signal(signal)
    label = HEALTH_LABELS.get(signal.get("status"), signal.get("status", "?").upper())
    detail = signal.get("status_detail")

    line = f"{name.capitalize()}: {label}"
    if detail:
        line += f" — {detail}"

    return line
