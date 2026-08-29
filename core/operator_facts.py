"""Operator key facts — parse, store, and pack facts for the LLM prompt.

All facts the operator collects are persisted to the Obsidian vault (when
configured). The prompt uses a **character budget** (not a tiny line cap) so
trade-heavy topics can ship a full digest without dropping pasted moves.
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

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
    "not facts",
    "reports suggest",
    "facts are thin",
    "always verify",
    "competitor video",
    "corporate-jargon",
    "spoken-word cadence",
    "short-form punchy",
    "retention pivot",
    "longer analysis for rankings",
)


def max_operator_key_facts() -> int:
    """Soft line cap (default 60). Char budget is the real limiter.

    `link_facts` chops a fetched page into ~400-char lines, so one news article is
    already a dozen-plus lines and a long read is dozens. The old cap of 24 could
    not hold a single article alongside vault facts.
    """
    raw = os.getenv("MAX_OPERATOR_KEY_FACTS", "60").strip()
    try:
        return max(1, min(120, int(raw)))
    except ValueError:
        return 60


def operator_key_fact_char_budget() -> int:
    """Total chars of operator facts injected into the script prompt.

    12000 holds a full news article (~8k chars once `link_facts` has chopped it)
    plus the vault facts beside it. The old 4500 did not, which is what the
    operator hit when a pasted article came back shortened. The ceiling is
    deliberate - facts are ~1 token per 4 chars, so this block is already ~3k
    tokens of every script prompt.
    """
    raw = os.getenv("OPERATOR_KEY_FACT_CHAR_BUDGET", "12000").strip()
    try:
        return max(500, min(20000, int(raw)))
    except ValueError:
        return 12000


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


def read_multiline_paste(input_fn) -> str:
    """Read a paste until a lone `.` / `END`, two consecutive blank lines, or EOF.

    A single blank line is a paragraph break, not an end — otherwise a pasted
    article dies at the first empty line (the interactive `paste` prompt).
    """
    lines: list[str] = []
    blank_run = 0
    while True:
        try:
            raw = input_fn("    ")
        except EOFError:
            break
        stripped = (raw or "").replace("\r", "").strip()
        if stripped.lower() in (".", "end"):
            break
        if not stripped:
            blank_run += 1
            if blank_run >= 2:
                break
            lines.append("")
            continue
        blank_run = 0
        lines.append(stripped)
    return "\n".join(lines)


def load_key_facts(facts_file: str = "", fact_lines: list[str] | None = None) -> list[str]:
    """Headless key facts: a paste-block file and/or repeated ``--fact`` lines.

    Same parser as the interactive paste prompt (trade blocks work). A missing
    file is a warning, not a crash. Returns [] when neither input is supplied.
    """
    collected: list[str] = list(fact_lines or [])
    path = (facts_file or "").strip()
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                collected.extend(parse_pasted_block(f.read()))
        except OSError as exc:
            logger.warning("Key-facts file skipped (%s)", exc)
    return dedupe_facts(collected)


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


_last_budget_report: dict[str, Any] = {"kept": 0, "dropped": 0, "reason": "", "chars": 0}


def last_fact_budget_report() -> dict[str, Any]:
    """What the most recent `facts_for_prompt` kept and dropped, and why."""
    return dict(_last_budget_report)


def facts_for_prompt(facts: list[str] | None) -> list[str]:
    """Facts sent to the LLM — char budget + line cap, manual order preserved.

    Operator key facts are the highest-priority ground truth in the system
    (decisions §4), so a truncation here is never silent: the drop is logged and
    recorded in `last_fact_budget_report()` for callers that render it.
    """
    global _last_budget_report
    _last_budget_report = {"kept": 0, "dropped": 0, "reason": "", "chars": 0}
    if not facts:
        return []
    budget = operator_key_fact_char_budget()
    line_cap = max_operator_key_facts()
    used = 0
    reason = ""
    out: list[str] = []
    for raw in facts:
        if not isinstance(raw, str):
            continue
        line = _normalize_line(raw)[:_MAX_KEY_FACT_CHARS]
        if not line or is_writing_tip(line):
            continue
        cost = len(line) + 2
        if len(out) >= line_cap:
            reason = f"line cap {line_cap} reached (raise MAX_OPERATOR_KEY_FACTS)"
            break
        if used + cost > budget:
            reason = f"char budget {budget} reached (raise OPERATOR_KEY_FACT_CHAR_BUDGET)"
            break
        out.append(line)
        used += cost

    dropped = max(0, len(facts) - len(out))
    _last_budget_report = {
        "kept": len(out),
        "dropped": dropped,
        "reason": reason if dropped else "",
        "chars": used,
    }
    if dropped and reason:
        logger.warning("%d operator fact(s) omitted from the prompt: %s", dropped, reason)
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
            "tier: operator\n"
            f"verified_at: {day}\n"
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
