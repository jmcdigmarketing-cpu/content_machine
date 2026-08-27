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


def should_skip_web_search(
    topic: str,
    channel_id: str | None = None,
    *,
    signals: dict | None = None,
    corpus: str | None = None,
) -> bool:
    """True when vault facts already clear the density bar (no HTTP).

    Legacy counts distinctive vault facts with no corpus. Scored/shadow need
    signal/operator corpus and count *confident* records under the web_skip
    policy. Calling scored mode without a corpus returns False so discovery
    can fetch non-web signals first.
    """
    if not skip_enabled() or not (topic or "").strip():
        return False
    try:
        from core.vault_relevance import relevance_mode

        mode = relevance_mode()
        if mode in ("shadow", "scored"):
            if signals is None and corpus is None:
                return False
            from core.obsidian_facts import load_fact_records
            from core.vault_relevance import build_relevance_corpus

            text = (
                corpus
                if corpus is not None
                else build_relevance_corpus(signals or {}, include_web=False)
            )
            if not str(text).strip():
                return False
            records = load_fact_records(
                topic,
                channel_id or "default",
                limit=max(min_facts(), 8),
                require_distinctive=True,
                corpus=text,
                relevance_policy="web_skip",
            )
            confident = [
                rec
                for rec in records
                if getattr(rec, "relevance_band", "") == "confident"
                or not getattr(rec, "uncertain", False)
            ]
            return len(confident) >= min_facts()

        from core.obsidian_facts import load_facts

        facts = load_facts(
            topic,
            channel_id or "default",
            limit=max(min_facts(), 8),
            require_distinctive=True,
        )
    except Exception as exc:
        if signals is not None or corpus is not None:
            logger.warning("web-search skip scoring failed; fetching web: %s", exc)
        else:
            logger.debug("web-search skip vault read skipped: %s", exc)
        return False
    return len(facts) >= min_facts()
