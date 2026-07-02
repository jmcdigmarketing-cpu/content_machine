"""Operator key facts — parse, store, and pack facts for the LLM prompt.

All facts the operator collects are persisted to the Obsidian vault (when
configured). The prompt uses a **character budget** (not a tiny line cap) so
trade-heavy topics can ship a full digest without dropping pasted moves.
"""

from __future__ import annotations

import os
import re
from datetime import date

from core.logging import get_logger

logger = get_logger("core.operator_facts")

_MAX_KEY_FACT_CHARS = 400  # per line in the prompt
_TRADE_HEADER_RE = re.compile(
    r"^(.{0,80}?\b(?:trade[sd]?|send[s]?|acquired|signed|waived)\b.{0,120})$",
    re.I,
)
_BULLET_PREFIX = re.compile(r"^[\s•\-\*]+")
_DATE_SUFFIX_RE = re.compile(
    r"\((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\)", re.I
)

# Writing tips / playbook lines that must never become operator ground truth.
_WRITING_TIP_MARKERS = (
    "open with a specific",
    "never invent a fight",
    "never invent a ",
    "avoid filler",
    "build to a strong closing",
    "drive comments",
    "drop your thoughts",
    "what do you think",
    "strong:",
    "weak:",
    "hook rule",
    "content strategy",
    "underdog/upset",
    "implication hooks",
    "invite debate",
    "framing beats",
    "outperform recaps",
    "narratives outperform",
    "rankings framing",
    "travel further",
    "age better",
    "clickbait",
    "heuristic",
)


def max_operator_key_facts() -> int:
    """Soft line cap (default 24). Char budget is the real limiter."""
    raw = os.getenv("MAX_OPERATOR_KEY_FACTS", "24").strip()
    try:
        return max(1, min(40, int(raw)))
    except ValueError:
        return 24


def operator_key_fact_char_budget() -> int:
    """Total chars of operator facts injected into the script prompt."""
    raw = os.getenv("OPERATOR_KEY_FACT_CHAR_BUDGET", "4500").strip()
    try:
        return max(500, min(12000, int(raw)))
    except ValueError:
        return 4500


def is_writing_tip(text: str) -> bool:
    """True for playbook / hook-coaching lines, not verifiable event facts."""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if stripped.lower().startswith("machine belief:"):
        return False
    low = stripped.lower()
    if re.search(
        r"\b(?:traded|trade for|signed|acquired|waived|drafted|"
        r"final|score|\$[\d,]+|\d{1,3}-\d{1,3}|20\d{2})\b",
        stripped,
        re.I,
    ):
        return False
    return any(m in low for m in _WRITING_TIP_MARKERS)


def _normalize_line(raw: str) -> str:
    flat = re.sub(r"\s+", " ", (raw or "").strip())
    return "".join(ch for ch in flat if ch.isprintable())


def parse_pasted_block(text: str) -> list[str]:
    """Turn a multi-line paste (trade tracker, article excerpt) into fact lines."""
    if not text or not text.strip():
        return []
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    facts: list[str] = []
    current_trade: list[str] = []

    def _flush_trade() -> None:
        if not current_trade:
            return
        header = current_trade[0]
        body = " | ".join(current_trade[1:]) if len(current_trade) > 1 else ""
        line = f"{header} — {body}" if body else header
        facts.append(_normalize_line(line)[: _MAX_KEY_FACT_CHARS * 2])
        current_trade.clear()

    for raw in lines:
        line = _BULLET_PREFIX.sub("", raw).strip()
        if not line:
            _flush_trade()
            continue
        if line.lower() in ("get:", "gets:"):
            continue
        low = line.lower()
        if low.endswith(" get:") or low.endswith(" gets:"):
            line = line.split(":")[0].strip()

        is_header = bool(_TRADE_HEADER_RE.match(line)) or (
            re.search(r"\btrade(?:d|s)?\s+(?:for|to)\b", line, re.I)
            and not line.lower().startswith(("line ", "the ", "a "))
        )
        is_bullet_asset = line.startswith("•") or (
            len(line) < 120 and not line.endswith(".") and " pick" in low
        )

        if is_header:
            _flush_trade()
            current_trade = [line]
        elif current_trade and (is_bullet_asset or line.startswith("•") or len(line) < 100):
            current_trade.append(line.lstrip("•").strip())
        elif is_writing_tip(line):
            continue
        else:
            _flush_trade()
            if len(line) > 20:
                facts.append(_normalize_line(line)[: _MAX_KEY_FACT_CHARS * 2])

    _flush_trade()

    if not facts and text.strip():
        for ln in lines:
            ln = _BULLET_PREFIX.sub("", ln).strip()
            if len(ln) > 20 and not is_writing_tip(ln):
                facts.append(_normalize_line(ln)[: _MAX_KEY_FACT_CHARS * 2])
    return facts


def dedupe_facts(facts: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in facts:
        line = _normalize_line(raw)
        if not line or is_writing_tip(line):
            continue
        key = re.sub(r"[^a-z0-9]+", "", line.lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def facts_for_prompt(facts: list[str] | None) -> list[str]:
    """Facts sent to the LLM — char budget + line cap, manual order preserved."""
    if not facts:
        return []
    budget = operator_key_fact_char_budget()
    line_cap = max_operator_key_facts()
    used = 0
    out: list[str] = []
    for raw in facts:
        if not isinstance(raw, str):
            continue
        line = _normalize_line(raw)[:_MAX_KEY_FACT_CHARS]
        if not line or is_writing_tip(line):
            continue
        cost = len(line) + 2
        if used + cost > budget or len(out) >= line_cap:
            break
        out.append(line)
        used += cost
    return out


def capture_facts_to_vault(
    channel_id: str,
    topic: str,
    facts: list[str],
    *,
    today: date | None = None,
) -> str | None:
    """Persist the full operator fact set to Obsidian (all lines, no cap)."""
    from config.channels import resolve_channel_id
    from core.obsidian_facts import _vault_path

    vault = _vault_path()
    if not vault or not facts:
        return None
    channel_id = resolve_channel_id(channel_id)
    day = (today or date.today()).isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", (topic or "run").lower()).strip("-")[:60] or "run"
    path = vault / channel_id / "_operator_facts" / f"{day}_{slug}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"- {f}" for f in facts if f.strip())
        header = (
            "---\n"
            f"channel: {channel_id}\n"
            "tags: [facts, operator, research]\n"
            f"topic: {topic[:120]}\n"
            f"date: {day}\n"
            "source: content-machine (operator key facts)\n"
            "---\n\n"
            f"# Operator facts — {topic[:80]}\n\n"
        )
        path.write_text(header + body + "\n", encoding="utf-8", newline="\n")
        logger.info("Saved %d operator facts to %s", len(facts), path)
        return str(path)
    except OSError as exc:
        logger.warning("operator facts vault write failed: %s", exc)
        return None
