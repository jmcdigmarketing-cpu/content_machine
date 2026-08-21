"""Skip Tavily/Brave when the vault already grounds the topic (candidate 72).

The $0.008 query is small; the round-trip and junk-line risk are not. Vault
reads are local (mtime-cached). We never probe the signal cache or fetch RSS
just to decide this — extra cache probes would pollute hit-rate stats.

Default on with a high bar (6 distinctive vault facts). ``0`` / ``off``
disables. Empty vault (tests, unset OBSIDIAN_VAULT_PATH) never skips.
"""

from __future__ import annotations

import os

from core.logging import get_logger

logger = get_logger("core.web_search_skip")

_DEFAULT_MIN = 6


def skip_enabled() -> bool:
    raw = os.getenv("WEB_SEARCH_SKIP_MIN_FACTS", str(_DEFAULT_MIN)).strip()
    if raw.lower() in ("off", "false", "no"):
        return False
    try:
        return int(raw) > 0
    except (TypeError, ValueError):
        return True


def min_facts() -> int:
    raw = os.getenv("WEB_SEARCH_SKIP_MIN_FACTS", str(_DEFAULT_MIN)).strip()
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MIN
    return val if val > 0 else _DEFAULT_MIN


def should_skip_web_search(topic: str, channel_id: str | None = None) -> bool:
    """True when vault facts already clear the density bar (no HTTP)."""
    if not skip_enabled() or not (topic or "").strip():
        return False
    try:
        from core.obsidian_facts import load_facts

        facts = load_facts(
            topic,
            channel_id or "default",
            limit=max(min_facts(), 8),
            require_distinctive=True,
        )
    except Exception as exc:
        logger.debug("web-search skip vault read skipped: %s", exc)
        return False
    return len(facts) >= min_facts()
