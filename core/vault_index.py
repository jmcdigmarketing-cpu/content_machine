"""mtime-invalidated vault note index (Pillar 4 — Obsidian knowledge OS).

`core/obsidian_facts.load_fact_records` previously re-read and re-parsed *every*
`.md` file in the vault on every call (`vault.rglob("*.md")` + `read_text` +
frontmatter/bullet parse). Batch drafting calls `load_facts` once per idea, so a
large vault was re-parsed N times per `batch-drafts` run.

This module caches the parse **per process**, keyed by file mtime: an unchanged
note is `stat()`ed but never re-read. The cache is authoritative within a run and
rebuilt on the next process — no on-disk index (that would accumulate stale
temp/rotated-vault entries and leak into `data/`). Parsing here is byte-identical
to the old obsidian_facts helpers, so downstream ranking/filtering is unchanged —
this is purely an I/O optimization, and fully fail-open.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.vault_index")

# Identical to the former obsidian_facts regexes — do not diverge.
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
_HEADING_RE = re.compile(r"^#+\s+(.*\S)\s*$")


@dataclass
class NoteEntry:
    rel_path: str
    meta: dict[str, str]
    stem: str
    headings: str  # space-joined heading text
    bullets: list[str]
    # The heading each bullet sits under, same length and order as `bullets`
    # ("" for a bullet before any heading). Additive: `bullets` is unchanged, so
    # the "byte-identical parse" promise above still holds for every existing
    # reader. `obsidian_facts.load_playbook` uses it to keep one section from
    # spending the whole prompt budget.
    bullet_sections: list[str] = field(default_factory=list)


_lock = threading.RLock()
# {vault_str: {rel_path: (mtime, NoteEntry)}}
_CACHE: dict[str, dict[str, tuple[float, NoteEntry]]] = {}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip()
    body = text[end + 4 :]
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = val.strip()
    return meta, body


def _extract_bullets_with_sections(body: str) -> tuple[list[str], list[str]]:
    """Bullets, plus the heading each one sits under (parallel lists)."""
    bullets: list[str] = []
    sections: list[str] = []
    current = ""
    for line in body.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            current = heading.group(1).strip()
            continue
        m = _BULLET_RE.match(line)
        if m:
            text = m.group(1).strip()
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            text = text.replace("**", "").replace("*", "").replace("`", "")
            if len(text) > 3:
                bullets.append(text)
                sections.append(current)
    return bullets, sections


def _parse_note(rel_path: str, text: str) -> NoteEntry:
    meta, body = _parse_frontmatter(text)
    headings = " ".join(_HEADING_RE.findall(body))
    bullets, sections = _extract_bullets_with_sections(body)
    return NoteEntry(
        rel_path=rel_path,
        meta=meta,
        stem=Path(rel_path).stem,
        headings=headings,
        bullets=bullets,
        bullet_sections=sections,
    )


def iter_notes(vault: Path) -> list[NoteEntry]:
    """Parsed entries for every `.md` note in the vault (mtime-cached, fail-open)."""
    vault_key = str(vault)
    try:
        md_files = list(vault.rglob("*.md"))
    except OSError as exc:
        logger.warning("Could not read vault %s: %s", vault, exc)
        return []

    with _lock:
        cache = _CACHE.setdefault(vault_key, {})
        seen: set[str] = set()
        entries: list[NoteEntry] = []
        for path in md_files:
            rel = str(path.relative_to(vault))
            seen.add(rel)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            cached = cache.get(rel)
            if cached and cached[0] == mtime:
                entries.append(cached[1])
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            entry = _parse_note(rel, text)
            cache[rel] = (mtime, entry)
            entries.append(entry)
        # Prune notes deleted from disk so the cache can't grow unbounded.
        for rel in set(cache) - seen:
            cache.pop(rel, None)
    return entries


def clear_cache() -> None:
    """Test/CLI helper — drop the in-process index."""
    with _lock:
        _CACHE.clear()
