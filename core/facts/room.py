"""The facts room (#860): every pasted line and link, the vault offer, ranked, ticked once.

Run 98 spent 7.9 of 11.2 operator minutes at the key-facts prompt - one URL at a time,
an off-topic question per link, then a separate vault review. `gather()` does the reading
the prompt does, all at once: typed lines (operator tier), every link read with the same
link reader (link tier, the page title as the source), off-topic link lines flagged with
the same filter, and the same vault scan. Each row carries #548's confidence and the list
is sorted by it. `kept()` turns the ticked ids back into the lists the prompt already
consumes, so ranking, the prompt budget, vault saves and the audit are unchanged.

Used by `core/ui.prompt_key_facts_result` when a run window is attached (the window
answers a `facts_room` request), by `desktop/facts_room.py` (the table), and by
`ops facts-room` (the same table in a terminal).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from core.facts.confidence import (
    FactConfidence,
    corroboration_counts,
    fact_confidence,
    record_confidence,
)
from core.logging import get_logger

logger = get_logger("core.facts.room")

KIND_TYPED = "typed"
KIND_LINK = "link"
KIND_VAULT = "vault"


@dataclass
class RoomRow:
    id: int
    line: str
    kind: str  # typed | link | vault
    source: str  # "you", the page title, or the vault note
    tier: str
    confidence: FactConfidence
    keep: bool
    off_topic: bool = False
    uncertain: bool = False
    url: str = ""
    published: Any = None
    record: Any = None  # the vault FactRecord


@dataclass
class RoomResult:
    """The ticked rows, in the shapes `prompt_key_facts_result` already uses."""

    manual: list[str] = field(default_factory=list)
    link: list[str] = field(default_factory=list)
    link_provenance: list[tuple[str, str, Any]] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    vault_claims: set[str] = field(default_factory=set)
    vault_records: list[Any] = field(default_factory=list)  # ticked
    vault_offered: list[Any] = field(default_factory=list)  # every vault row shown


def room_enabled() -> bool:
    return os.getenv("FACTS_ROOM", "true").strip().lower() not in ("0", "false", "no", "off")


def _default_reader(url: str) -> tuple[list[str], dict[str, Any]]:
    from core.link_facts import extract_facts_from_url
    from core.link_facts import last_extract_report as link_extract_report

    lines = extract_facts_from_url(url)
    return list(lines or []), dict(link_extract_report() or {})


def _age_days(published: Any) -> int | None:
    day = published.date() if isinstance(published, datetime) else published
    if isinstance(day, date):
        return max(0, (date.today() - day).days)
    return None


def gather(
    topic: str,
    channel_id: str,
    *,
    pasted_lines: list[str],
    angle: str = "",
    signals: dict[str, Any] | None = None,
    read_url: Callable[[str], tuple[list[str], dict[str, Any]]] | None = None,
    flag_off_topic: Callable[..., list[str]] | None = None,
    load_vault: Callable[[str], list[Any]] | None = None,
    unread: list[str] | None = None,
) -> list[RoomRow]:
    """Every candidate line, ranked by confidence (ids 1..n in that order). Never raises
    for one bad link: a page that reads nothing is appended to `unread` (when given) so
    the caller can say so, and skipped."""
    from core.link_facts import looks_like_url
    from core.operator_facts import is_article_chrome, parse_pasted_block
    from core.vault.relevance import build_relevance_corpus

    read = read_url or _default_reader
    typed: list[str] = []
    links: list[tuple[str, str, str, Any]] = []  # line, url, title, published
    for raw in pasted_lines:
        text = str(raw or "").strip()
        if not text:
            continue
        if looks_like_url(text):
            try:
                lines, report = read(text)
            except Exception as exc:
                logger.debug("facts room: %s unreadable: %s", text, exc)
                lines, report = [], {}
            if not lines:
                if unread is not None:
                    unread.append(text)
                continue
            title = str(report.get("title") or "").strip() or text
            for line in lines:
                links.append((str(line), text, title, report.get("published")))
            continue
        for line in parse_pasted_block(text) if "\n" in text else [text]:
            if not is_article_chrome(line):
                typed.append(line)

    corpus = build_relevance_corpus(signals or {}, operator_facts=typed)
    off: set[str] = set()
    link_lines = [line for line, *_rest in links]
    if link_lines:
        if flag_off_topic is None:
            from core.facts.selection import flag_off_topic as _flag

            flag_off_topic = _flag
        reference = "\n".join(part for part in (angle, topic) if part)
        try:
            off = set(flag_off_topic(link_lines, reference=reference, corpus=corpus))
        except Exception as exc:
            logger.debug("facts room: off-topic filter skipped: %s", exc)

    vault: list[Any] = []
    try:
        if load_vault is not None:
            vault = list(
                load_vault(
                    build_relevance_corpus(signals or {}, operator_facts=[*typed, *link_lines])
                )
            )
        else:
            vault = _vault_records(topic, channel_id, signals, [*typed, *link_lines])
    except Exception as exc:
        logger.debug("facts room: vault scan skipped: %s", exc)

    sources = (
        [(line, "you") for line in typed]
        + [(line, url) for line, url, _t, _p in links]
        + [(r.claim, str(getattr(r, "note_path", "") or "vault")) for r in vault]
    )
    corroborated = corroboration_counts(sources)
    rows: list[RoomRow] = []
    i = 0
    for line in typed:
        rows.append(
            RoomRow(0, line, KIND_TYPED, "you", "operator",
                    fact_confidence(tier="operator", corroborations=corroborated[i]), keep=True)
        )  # fmt: skip
        i += 1
    for line, url, title, published in links:
        flagged = line in off
        conf = fact_confidence(
            tier="link",
            relevance=0.0 if flagged else None,
            corroborations=corroborated[i],
            age_days=_age_days(published),
        )
        if flagged:
            conf.label = "low"  # off-topic is never better than low, whatever the tier
        rows.append(
            RoomRow(0, line, KIND_LINK, title, "link", conf, keep=not flagged,
                    off_topic=flagged, url=url, published=published)
        )  # fmt: skip
        i += 1
    for record in vault:
        uncertain = bool(getattr(record, "uncertain", False))
        rows.append(
            RoomRow(0, record.claim, KIND_VAULT, str(getattr(record, "note_path", "") or "vault"),
                    str(getattr(record, "tier", "") or "vault"),
                    record_confidence(record, corroborations=corroborated[i]),
                    keep=not uncertain, uncertain=uncertain, record=record,
                    url=str(getattr(record, "source_url", "") or ""))
        )  # fmt: skip
        i += 1
    rows.sort(key=lambda r: (-r.confidence.value, r.off_topic))
    for n, row in enumerate(rows, 1):
        row.id = n
    return rows


def _vault_records(
    topic: str, channel_id: str, signals: dict[str, Any] | None, operator_facts: list[str]
) -> list[Any]:
    """The prompt's own vault scan: relevant lines, minus tips, playbook and rejects."""
    from core.obsidian_facts import is_playbook_line, load_fact_records
    from core.operator_facts import is_writing_tip
    from core.vault.relevance import build_relevance_corpus

    corpus = build_relevance_corpus(signals or {}, operator_facts=operator_facts)
    records = load_fact_records(topic, channel_id, require_distinctive=True, corpus=corpus)
    return [
        r
        for r in records
        if not is_writing_tip(r.claim)
        and not is_playbook_line(r.claim)
        and (getattr(r, "relevance_band", "") or "") != "reject"
    ]


def kept(rows: list[RoomRow], kept_ids: list[int] | set[int]) -> RoomResult:
    """The ticked rows as the prompt's lists: typed, link (with provenance), vault claims."""
    wanted = {int(i) for i in kept_ids}
    result = RoomResult()
    seen_urls: set[str] = set()
    result.vault_offered = [r.record for r in rows if r.kind == KIND_VAULT and r.record is not None]
    for row in sorted(rows, key=lambda r: r.id):
        if row.id not in wanted:
            continue
        if row.kind == KIND_TYPED:
            result.manual.append(row.line)
        elif row.kind == KIND_LINK:
            result.link.append(row.line)
            result.link_provenance.append((row.line, row.url, row.published))
            if row.url and row.url not in seen_urls:
                seen_urls.add(row.url)
                result.sources.append({"url": row.url, "title": row.source})
        else:
            result.vault_claims.add(row.line)
            if row.record is not None:
                result.vault_records.append(row.record)
    return result


def unread_lines(unread: list[str]) -> list[str]:
    """What to say about links that gave nothing: paste their text instead."""
    if not unread:
        return []
    out = [f"  {len(unread)} link(s) read nothing - paste the article text instead:"]
    out.extend(f"    · {url}" for url in unread[:5])
    return out


def table_lines(rows: list[RoomRow], *, width: int = 96) -> list[str]:
    """The ranked table, for `ops facts-room` and the run log."""
    if not rows:
        return ["  (nothing to review - no pasted lines, links or vault matches)"]
    out = []
    for row in rows:
        tick = "[x]" if row.keep else "[ ]"
        flag = " off-topic" if row.off_topic else " uncertain" if row.uncertain else ""
        line = row.line if len(row.line) <= width else row.line[: width - 1] + "…"
        out.append(
            f"  {tick} {row.id:>2}. conf {row.confidence.value:.2f} {row.confidence.label:<6}"
            f" {row.tier:<8} {line}"
        )
        out.append(f"          from {row.source[:70]}{flag}")
    return out
