"""Capture external links brought into a run into the Obsidian vault.

When an operator pastes a link in the key-facts prompt (the links "we bring in
from outside"), the URL + title are appended to a per-channel, append-only
research log: ``<vault>/<channel>/_sources.md``. ``core.obsidian_facts.load_facts``
reads it back on related future topics, so research brought in once becomes
reusable instead of being discarded after the run.

Mirrors ``core.vault_writeback`` safety:
- own clearly-marked, auto-managed file per channel; never touches human notes,
- no-op when ``OBSIDIAN_VAULT_PATH`` is unset,
- never raises (a vault hiccup must never block video creation),
- append-only with URL de-duplication (a link already logged is not re-added).

The file is channel-scoped (subfolder + ``channel:`` frontmatter) and tagged
``[sources, research]`` — deliberately NOT ``evergreen``, so a captured source
only resurfaces on a topic that overlaps it, not on every unrelated topic.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from config.channels import resolve_channel_id
from core.logging import get_logger
from core.obsidian_facts import _vault_path

logger = get_logger("core.source_capture")

_FILENAME = "_sources.md"


def _header(channel_id: str) -> str:
    return (
        "---\n"
        f"channel: {channel_id}\n"
        "tags: [sources, research]\n"
        "tier: link\n"
        "source: content-machine (auto-captured)\n"
        "---\n\n"
        f"# Captured sources — {channel_id} (auto-appended)\n\n"
        "> External links brought into runs (pasted facts / web search). Reusable\n"
        "> research — read back by core.obsidian_facts on related topics. New entries\n"
        "> are appended below; safe to prune or annotate by hand.\n\n"
    )


def _clean(text: str | None, limit: int) -> str:
    return " ".join((text or "").split())[:limit]


def _normalize(sources: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    """(url, title) pairs from raw source dicts; drops anything without an http URL."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for s in sources or []:
        if not isinstance(s, dict):
            continue
        url = _clean(s.get("url"), 500)
        if not url.lower().startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append((url, _clean(s.get("title"), 200) or url))
    return out


def capture_sources(
    channel_id: str | None = None,
    topic: str = "",
    sources: list[dict[str, Any]] | None = None,
    *,
    today: date | None = None,
) -> Path | None:
    """Append external sources to the channel's vault research log.

    Returns the file path (even when nothing new was added), or None when the
    vault is unset / there are no valid sources / a write fails.
    """
    channel_id = resolve_channel_id(channel_id)
    vault = _vault_path()
    if not vault:
        logger.debug("source capture skipped: OBSIDIAN_VAULT_PATH not set")
        return None

    items = _normalize(sources)
    if not items:
        return None

    path = vault / channel_id / _FILENAME
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        existing = ""

    # De-dupe: skip URLs already recorded in this channel's log.
    fresh = [(url, title) for url, title in items if url not in existing]
    if not fresh:
        return path

    day = (today or date.today()).isoformat()
    topic_clean = _clean(topic, 120)
    suffix = f" (re: {topic_clean})" if topic_clean else ""
    block = "".join(f"- {day} · {title} — {url}{suffix}\n" for url, title in fresh)

    try:
        (vault / channel_id).mkdir(parents=True, exist_ok=True)
        content = (
            (existing.rstrip("\n") + "\n" + block) if existing else (_header(channel_id) + block)
        )
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        logger.warning("source capture failed for %s: %s", channel_id, exc)
        return None

    logger.info("Captured %d source(s) to %s", len(fresh), path)
    return path


def capture_web_sources(
    channel_id: str | None,
    topic: str,
    signals: dict[str, Any] | None,
) -> Path | None:
    """Log the web_search signal's result URLs to ``_sources.md`` (Pillar 3 quick win).

    The web-search signal grounds scripts with title+snippet but its URLs were
    discarded after the run. Same append-only, URL-deduped log as pasted links,
    so a source found once is findable (and re-readable) on related topics.
    """
    data = ((signals or {}).get("web_search") or {}).get("data") or {}
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return None
    sources = [
        {"url": r.get("url"), "title": r.get("title")} for r in results if isinstance(r, dict)
    ]
    return capture_sources(channel_id, topic, sources)
