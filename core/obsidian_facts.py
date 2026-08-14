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
from datetime import date
from pathlib import Path

from core.fact_store import FactRecord, note_metadata, rank_bonus
from core.logging import get_logger
from core.vault_index import iter_notes

logger = get_logger("core.obsidian_facts")

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
    # Generic / temporal words that cause false topic matches (e.g. a gaming note
    # mentioning "Summer Game Fest" matching a UFC topic that says "this summer").
    "summer",
    "winter",
    "spring",
    "autumn",
    "fall",
    "season",
    "year",
    "week",
    "weekly",
    "daily",
    "today",
    "tonight",
    "recent",
    "update",
    "news",
    "video",
    "channel",
    "best",
    "top",
    "new",
    "next",
    "biggest",
    "most",
    "will",
    "show",
    "watch",
}


_STRATEGY_TAGS = frozenset({"strategy", "playbook", "heuristic", "content-tips", "tips"})
_STRATEGY_PATH_PARTS = frozenset({"strategy", "playbook", "heuristics", "content-tips"})
# Machine-written folders that must never feed back into load_facts as ground truth
# (dossiers/reports are records of what we made, not verified facts about the world).
_MACHINE_PATH_PARTS = frozenset({"_runs", "_reports"})
# Bullets that read as content-strategy heuristics, not verifiable event facts.
_STRATEGY_BULLET_MARKERS = (
    "outperform",
    "engagement",
    "framing",
    "angles",
    "drive comments",
    "narratives",
    "narrative",
    "tier-list",
    "tier list",
    "travel further",
    "age better",
    "heuristic",
    "clickbait",
    "content strategy",
    "underdog/upset",
    "decline takes",
    "disrespected",
    "beef framing",
    "implication hooks",
    "invite debate",
    "defensive engagement",
    "not facts",
    "reports suggest",
    "facts are thin",
    "always verify",
    "competitor video",
    "corporate-jargon",
    "spoken-word cadence",
    "opinionated",
    "corporate anchor",
    "short-form punchy",
    "retention pivot",
    "longer analysis for rankings",
    "breaking reactions",
)
# Factual anchors — if present, keep the bullet even when strategy-flavored.
_FACT_ANCHOR_RE = re.compile(
    r"\b(?:traded|trade|signed|draft(?:ed)?|acquired|waived|released|"
    r"defeated|beat|won|lost|score|final|champion|ranking|record|"
    r"\$[\d,]+|\d{1,3}-\d{1,3}|20\d{2})\b",
    re.I,
)


def _tag_set(meta: dict[str, str]) -> set[str]:
    """Frontmatter tags as a lowercased set, tolerant of `[a, b]` / `a, b` forms."""
    raw = (meta.get("tags") or "").strip().strip("[]")
    return {t.strip().strip("\"'").lower() for t in re.split(r"[,;\s]+", raw) if t.strip()}


def _is_strategy_note(meta: dict[str, str], rel_path: Path) -> bool:
    if _tag_set(meta) & _STRATEGY_TAGS:
        return True
    parts = {p.lower() for p in rel_path.parts}
    return bool(parts & _STRATEGY_PATH_PARTS)


def _is_machine_record(rel_path: Path) -> bool:
    """Run dossiers / weekly reports the system writes — never read back as facts."""
    return bool({p.lower() for p in rel_path.parts} & _MACHINE_PATH_PARTS)


def _is_playbook_only_note(meta: dict[str, str], rel_path: Path) -> bool:
    """Machine beliefs + strategy notes — playbook layer only, never load_facts."""
    if rel_path.stem == "_machine-beliefs":
        return True
    if "beliefs" in _tag_set(meta):
        return True
    return _is_strategy_note(meta, rel_path)


def is_playbook_line(text: str) -> bool:
    """True for strategy/voice guidance that must not be operator ground truth."""
    return _is_strategy_bullet(text)


def _is_strategy_bullet(text: str) -> bool:
    """True for engagement/playbook lines that must not be operator ground truth."""
    from core.operator_facts import is_writing_tip

    if is_writing_tip(text):
        return True
    stripped = (text or "").strip()
    if stripped.lower().startswith("machine belief:"):
        return False
    if _FACT_ANCHOR_RE.search(text or ""):
        return False
    low = stripped.lower()
    return any(m in low for m in _STRATEGY_BULLET_MARKERS)


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


# Words too generic to establish TOPIC relevance on their own. A one-token overlap
# on "patch"/"massive" is how NBA facts surfaced on a Palworld topic — genre-level
# vocabulary matches everything in a channel's vault. Distinctive relevance requires
# a token outside this set (names, games, events: "palworld", "gaethje", "lakers").
_GENERIC_TOKENS = {
    "patch",
    "notes",
    "note",
    "update",
    "updates",
    "updated",
    "game",
    "games",
    "gaming",
    "gamers",
    "player",
    "players",
    "playing",
    "season",
    "seasons",
    "news",
    "massive",
    "video",
    "videos",
    "community",
    "content",
    "release",
    "released",
    "reveal",
    "revealed",
    "announced",
    "announcement",
    "official",
    "officially",
    "launch",
    "launched",
    "trailer",
    "record",
    "records",
    "team",
    "teams",
    "fans",
    "sport",
    "sports",
    "league",
    "match",
    "event",
    "events",
    "source",
    "sources",
    "report",
    "reports",
    "rumor",
    "rumors",
    "year",
    "years",
    "week",
    "month",
    "today",
    "2024",
    "2025",
    "2026",
    "2027",
    # Generic English verbs/adverbs/prepositions that survive `_tokens` (len > 3, not
    # a stopword) but carry no topic identity. A live run titled "...Salkilld,
    # Thainara break through" pulled Marvel Rivals facts into a UFC script on the
    # single token "break" (from "I break down the buffs") — genre vocabulary is not
    # the only way a one-token overlap matches everything.
    "break",
    "breaks",
    "breaking",
    "broke",
    "through",
    "down",
    "back",
    "over",
    "after",
    "before",
    "around",
    "still",
    "first",
    "last",
    "more",
    "full",
    "real",
    "huge",
    "major",
    "make",
    "makes",
    "made",
    "take",
    "takes",
    "give",
    "gets",
    "sets",
    "goes",
    "come",
    "comes",
}


def _distinctive_tokens(text: str) -> set[str]:
    """`_tokens` minus genre-generic vocabulary — the tokens that mark TOPIC identity."""
    return _tokens(text) - _GENERIC_TOKENS


def _note_matches_channel(meta: dict[str, str], rel_path: Path, channel_id: str) -> bool:
    declared = (meta.get("channel") or "").lower()
    if declared:
        return declared == channel_id.lower()
    # Subfolder named after the channel scopes the note to that channel.
    parts = {p.lower() for p in rel_path.parts}
    return channel_id.lower() in parts or "facts" in parts


def _is_evergreen(meta: dict[str, str]) -> bool:
    # Only the explicit "evergreen" tag bypasses topic matching. A plain
    # tags:[facts] note marks eligibility but still surfaces only on topic match,
    # so dated fact notes (e.g. ufc-current) don't leak onto unrelated topics.
    tags = (meta.get("tags") or "").lower()
    return "evergreen" in tags


def load_facts(
    topic: str,
    channel_id: str = "default",
    *,
    limit: int = 8,
    require_distinctive: bool = False,
) -> list[str]:
    """Return relevant fact bullet lines from the vault for this topic + channel.

    Returns [] when the vault is unset/missing or nothing relevant is found, so it
    is always safe to call. Results are ranked by keyword overlap with the topic,
    then by provenance tier + freshness (core/fact_store.py) so a fact verified
    last week outranks an equally relevant undated one; expired notes are dropped.
    Evergreen notes for the channel are always considered.

    require_distinctive: only return facts sharing a TOPIC-distinctive token with
    the topic (generic genre words like "patch"/"season" don't count, and evergreen
    notes get no bypass) — use for operator-facing suggestions so a Palworld topic
    can never surface NBA facts.
    """
    return [
        r.claim
        for r in load_fact_records(
            topic, channel_id, limit=limit, require_distinctive=require_distinctive
        )
    ]


def load_fact_records(
    topic: str,
    channel_id: str = "default",
    *,
    limit: int = 8,
    today: date | None = None,
    require_distinctive: bool = False,
) -> list[FactRecord]:
    """`load_facts` with provenance — one FactRecord per relevant bullet (Pillar 3).

    Frontmatter drives the metadata: ``tier:`` (else inferred from the path —
    ``_operator_facts/`` → operator, ``_sources.md`` → link, else vault),
    ``verified_at:`` (falls back to ``date:``), ``expires:`` (note dropped once
    past), ``source:`` when it is a URL.
    """
    vault = _vault_path()
    if not vault:
        return []

    today = today or date.today()
    topic_tokens = _tokens(topic)
    topic_distinctive = _distinctive_tokens(topic)
    scored: list[tuple[float, FactRecord]] = []

    for note in iter_notes(vault):
        rel = Path(note.rel_path)
        meta = note.meta
        if not _note_matches_channel(meta, rel, channel_id):
            continue
        if _is_playbook_only_note(meta, rel) or _is_machine_record(rel):
            continue

        tier, verified_at, expires, source_url = note_metadata(meta, rel)
        if expires is not None and expires < today:
            continue  # stale by declaration — champions/rosters age out

        # Relevance: overlap of topic tokens with filename + headings.
        note_tokens = _tokens(note.stem + " " + note.headings)
        overlap = len(topic_tokens & note_tokens)
        evergreen = _is_evergreen(meta)
        # A note qualifies if its title/headings match, it's an evergreen fact note,
        # or any individual bullet matches the topic (a fact can live in a note whose
        # title doesn't mention the topic).
        note_weight = overlap + (0.5 if evergreen else 0)
        provenance = rank_bonus(tier=tier, verified_at=verified_at, today=today)
        # Distinctive gate: for operator-facing suggestions, note-level relevance
        # needs a topic-identity token (not just genre vocabulary), with no
        # evergreen bypass — computed once per note, refined per bullet below.
        note_distinctive = (
            len(topic_distinctive & _distinctive_tokens(note.stem + " " + note.headings))
            if require_distinctive
            else 0
        )
        for bullet in note.bullets:
            if _is_strategy_bullet(bullet):
                continue
            bullet_overlap = len(topic_tokens & _tokens(bullet))
            if overlap == 0 and not evergreen and bullet_overlap == 0:
                continue
            if require_distinctive:
                bullet_distinctive = len(topic_distinctive & _distinctive_tokens(bullet))
                if note_distinctive == 0 and bullet_distinctive == 0:
                    continue  # genre-only match (e.g. "patch"/"massive") — not this topic
            record = FactRecord(
                claim=bullet,
                tier=tier,
                source_url=source_url,
                verified_at=verified_at,
                expires=expires,
                note_path=str(rel),
            )
            scored.append((note_weight + bullet_overlap + provenance, record))

    if not scored:
        return []

    scored.sort(key=lambda s: s[0], reverse=True)
    seen: set[str] = set()
    records: list[FactRecord] = []
    for _, record in scored:
        key = record.claim.lower()
        if key in seen:
            continue
        seen.add(key)
        records.append(record)
        if len(records) >= limit:
            break
    return records


def load_playbook(channel_id: str = "default", *, limit: int = 10) -> list[str]:
    """Strategy/playbook bullets for a channel — the notes `load_facts` excludes.

    The mirror of `load_facts`: it reads exactly the strategy notes (`_is_strategy_note`)
    and machine-belief lines that the fact loader deliberately skips, so they can feed
    the script prompt as **style guidance, not ground truth** (Pillar 4). Topic-agnostic
    by design — a channel's voice/angle rules apply to every video. Returns [] when the
    vault is unset. Machine-belief notes (`_machine-beliefs.md`, tagged strategy-free but
    evergreen) are included since they read as priors, not facts.
    """
    vault = _vault_path()
    if not vault:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for note in iter_notes(vault):
        rel = Path(note.rel_path)
        if not _note_matches_channel(note.meta, rel, channel_id) or _is_machine_record(rel):
            continue
        strategy_note = _is_strategy_note(note.meta, rel)
        is_belief = note.stem == "_machine-beliefs" or "machine" in _tag_set(note.meta)
        for bullet in note.bullets:
            # A playbook line is exactly what load_facts drops as non-factual guidance:
            # a whole strategy/belief note, or a strategy-flavored bullet in any note.
            if not (strategy_note or is_belief or _is_strategy_bullet(bullet)):
                continue
            key = bullet.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(bullet)
            if len(out) >= limit:
                return out
    return out


def playbook_block(channel_id: str = "default", *, limit: int = 8, char_budget: int = 700) -> str:
    """A bounded prompt block of playbook guidance, or "" when none.

    Mirrors `core/channel_persona.human_context_block`: a small, clearly-labeled,
    bounded insert the script prompt can include without it overriding grounding.
    """
    bullets = load_playbook(channel_id, limit=limit)
    if not bullets:
        return ""
    lines: list[str] = []
    used = 0
    for b in bullets:
        if used + len(b) > char_budget:
            break
        lines.append(f"- {b}")
        used += len(b)
    if not lines:
        return ""
    body = "\n".join(lines)
    return (
        "CHANNEL PLAYBOOK (style/strategy guidance from the operator's vault — "
        "shape tone and angle with these; they are NOT facts and never override "
        f"the verified source facts below):\n{body}"
    )
