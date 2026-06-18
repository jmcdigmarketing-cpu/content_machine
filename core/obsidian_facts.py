"""Read verified facts from an Obsidian vault (or any folder of markdown notes).

An Obsidian vault is just a folder of `.md` files on disk, so "connecting" the
vault means pointing the pipeline at that folder and pulling the bullet lines from
notes relevant to the current topic. Those lines pre-fill the operator key-facts
prompt (the operator confirms/edits), feeding the script's highest-priority
ground-truth block.

Config:
    OBSIDIAN_VAULT_PATH — absolute path to the vault/notes folder. Unset = disabled.

Conventions (all optional — the reader degrades gracefully):
    - Notes under a subfolder named after the channel (e.g. vault/tapin/...) are
      treated as channel-scoped.
    - YAML-ish frontmatter `channel: tapin` scopes a note to one channel.
    - Frontmatter `tags:` containing "facts" or "evergreen" boosts a note so it is
      always considered for its channel even on a weak keyword match.

No external dependencies: frontmatter is parsed with a tiny hand-rolled reader so
the project doesn't need PyYAML.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.obsidian_facts")

_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
_HEADING_RE = re.compile(r"^#+\s+(.*\S)\s*$")
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "what",
    "when",
    "your",
    "from",
    "about",
    "into",
}


def _vault_path() -> Path | None:
    raw = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_dir():
        logger.warning("OBSIDIAN_VAULT_PATH is not a directory: %s", raw)
        return None
    return path


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter dict, body). Handles a leading `---` ... `---` block."""
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


def _note_matches_channel(meta: dict[str, str], rel_path: Path, channel_id: str) -> bool:
    declared = (meta.get("channel") or "").lower()
    if declared:
        return declared == channel_id.lower()
    # Subfolder named after the channel scopes the note to that channel.
    parts = {p.lower() for p in rel_path.parts}
    return channel_id.lower() in parts or "facts" in parts


def _is_evergreen(meta: dict[str, str]) -> bool:
    tags = (meta.get("tags") or "").lower()
    return "facts" in tags or "evergreen" in tags


def _extract_bullets(body: str) -> list[str]:
    bullets = []
    for line in body.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            text = m.group(1).strip()
            # Strip simple markdown emphasis/links for clean spoken facts.
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            text = text.replace("**", "").replace("*", "").replace("`", "")
            if len(text) > 3:
                bullets.append(text)
    return bullets


def load_facts(topic: str, channel_id: str = "default", *, limit: int = 8) -> list[str]:
    """Return relevant fact bullet lines from the vault for this topic + channel.

    Returns [] when the vault is unset/missing or nothing relevant is found, so it
    is always safe to call. Results are ranked by keyword overlap with the topic;
    evergreen notes for the channel are always considered.
    """
    vault = _vault_path()
    if not vault:
        return []

    topic_tokens = _tokens(topic)
    scored: list[tuple[float, str]] = []

    try:
        md_files = list(vault.rglob("*.md"))
    except OSError as exc:
        logger.warning("Could not read vault %s: %s", vault, exc)
        return []

    for path in md_files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        rel = path.relative_to(vault)
        if not _note_matches_channel(meta, rel, channel_id):
            continue

        # Relevance: overlap of topic tokens with filename + headings.
        headings = " ".join(_HEADING_RE.findall(body))
        note_tokens = _tokens(path.stem + " " + headings)
        overlap = len(topic_tokens & note_tokens)
        evergreen = _is_evergreen(meta)
        # A note qualifies if its title/headings match, it's an evergreen fact note,
        # or any individual bullet matches the topic (a fact can live in a note whose
        # title doesn't mention the topic).
        note_weight = overlap + (0.5 if evergreen else 0)
        for bullet in _extract_bullets(body):
            bullet_overlap = len(topic_tokens & _tokens(bullet))
            if overlap == 0 and not evergreen and bullet_overlap == 0:
                continue
            scored.append((note_weight + bullet_overlap, bullet))

    if not scored:
        return []

    scored.sort(key=lambda s: s[0], reverse=True)
    seen: set[str] = set()
    facts: list[str] = []
    for _, bullet in scored:
        key = bullet.lower()
        if key in seen:
            continue
        seen.add(key)
        facts.append(bullet)
        if len(facts) >= limit:
            break
    return facts
