"""Skip Tavily/Brave when the vault already grounds the topic (candidate 72).

The $0.008 query is small; the round-trip and junk-line risk are not. Vault
reads are local (mtime-cached). We never probe the signal cache or fetch RSS
just to decide this — extra cache probes would pollute hit-rate stats.

Default on with a high bar (6 distinctive vault facts). ``0`` / ``off``
disables. Empty vault (tests, unset OBSIDIAN_VAULT_PATH) never skips.

Two recency gates sit in front of the density bar, because density alone was the
wrong measure: an event-shaped topic never skips, and the backing facts must
carry a `verified_at` inside ``WEB_SEARCH_SKIP_MAX_AGE_DAYS``.
"""

from __future__ import annotations

import os

from core.logging import get_logger

logger = get_logger("core.web_search_skip")

_DEFAULT_MIN = 6
_DEFAULT_MAX_AGE_DAYS = 21

# A topic about a thing that JUST HAPPENED must never be answered from the vault,
# however dense the vault is. Run 73: run 1 fetched the web and saved what it
# found, which cleared the density bar, so runs 2 and 3 stopped fetching - and a
# reveal that was hours old was grounded on the system's own earlier notes.
_EVENT_CUES = (
    "reveal",
    "revealed",
    "extended look",
    "first look",
    "trailer",
    "announce",
    "announced",
    "announcement",
    "leak",
    "leaked",
    "drops",
    "dropped",
    "release date",
    "launch",
    "launches",
    "confirmed",
    "breaking",
    "patch notes",
    "results",
    "recap",
    "weigh-in",
    "just happened",
    "today",
    "tonight",
    "this week",
)


def is_event_shaped_topic(topic: str | None) -> bool:
    """True when the topic is about a dated event rather than an evergreen take."""
    low = (topic or "").lower()
    return any(cue in low for cue in _EVENT_CUES)


def max_fact_age_days() -> int:
    """0/off disables the age gate; the density bar alone then decides."""
    raw = os.getenv("WEB_SEARCH_SKIP_MAX_AGE_DAYS", str(_DEFAULT_MAX_AGE_DAYS)).strip()
    if raw.lower() in ("off", "false", "no"):
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_AGE_DAYS


def _recent_enough(records) -> bool:
    """True when at least one backing fact proves it is current.

    A note with no `verified_at` cannot prove anything, so it does not count -
    the same reasoning as candidate 331 refusing to date an undated paste.
    """
    max_age = max_fact_age_days()
    if max_age <= 0:
        return True
    import datetime

    cutoff = datetime.date.today() - datetime.timedelta(days=max_age)
    for rec in records:
        when = getattr(rec, "verified_at", None)
        if when is not None and when >= cutoff:
            return True
    return False


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
    if is_event_shaped_topic(topic):
        logger.debug("web-search skip declined: event-shaped topic %r", topic)
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
            if len(confident) < min_facts():
                return False
            if not _recent_enough(confident):
                logger.debug("web-search skip declined: backing vault facts are stale")
                return False
            return True

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
    return len(facts) >= min_facts()  # legacy path: no records, so no age to read
