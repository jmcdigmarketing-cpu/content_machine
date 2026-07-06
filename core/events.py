"""Outbound webhook events — run/publish/batch notifications for automation.

Roadmap "Webhook / n8n / Zapier out": POST a small JSON envelope to
EVENT_WEBHOOK_URL whenever something automatable happens (a run finished, a
video published, a batch completed), so a self-hosted n8n / Zapier / any HTTP
catcher can chain notifications, cross-posting, retries, spreadsheets, etc.

Strictly fire-and-forget: unset EVENT_WEBHOOK_URL = fully disabled (zero
overhead); delivery runs on a daemon thread with a short timeout and NEVER
raises or blocks the pipeline. EVENT_WEBHOOK_EVENTS (csv) filters event types.

    EVENT_WEBHOOK_URL=http://localhost:5678/webhook/content-machine
    EVENT_WEBHOOK_EVENTS=video_published            # optional filter
    EVENT_WEBHOOK_TIMEOUT=5

Envelope: {"event": "<type>", "at": "<iso8601>", "payload": {...}}
Event types emitted today: run_completed, video_published, batch_completed.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.events")


def webhook_url() -> str:
    return os.getenv("EVENT_WEBHOOK_URL", "").strip()


def events_enabled() -> bool:
    return bool(webhook_url())


def _wanted(event_type: str) -> bool:
    raw = os.getenv("EVENT_WEBHOOK_EVENTS", "").strip()
    if not raw:
        return True
    return event_type in {e.strip().lower() for e in raw.split(",") if e.strip()}


def _timeout() -> float:
    try:
        return float(os.getenv("EVENT_WEBHOOK_TIMEOUT", "5"))
    except ValueError:
        return 5.0


def _deliver(url: str, envelope: dict[str, Any]) -> None:
    try:
        import requests

        requests.post(url, json=envelope, timeout=_timeout())
    except Exception as exc:
        logger.debug("event delivery failed (%s): %s", envelope.get("event"), exc)


def emit_event(event_type: str, payload: dict[str, Any], *, wait: bool = False) -> bool:
    """Send one event. Returns True when a delivery was attempted.

    wait=True delivers synchronously (tests / shutdown hooks); the default is
    a daemon thread so a slow or dead webhook can't stall the pipeline.
    """
    url = webhook_url()
    if not url or not _wanted(event_type.lower()):
        return False
    envelope = {
        "event": event_type,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "payload": payload,
    }
    if wait:
        _deliver(url, envelope)
        return True
    threading.Thread(
        target=_deliver, args=(url, envelope), name=f"event-{event_type}", daemon=True
    ).start()
    return True
