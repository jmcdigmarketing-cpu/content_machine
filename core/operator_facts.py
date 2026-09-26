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

_MAX_KEY_FACT_CHARS = 400  # split width for a prompt line - NOT a truncation point
# A "sentence" longer than this multiple of the split width is not prose, it is a
# scraped blob with no punctuation. Only those get a word-boundary split.
_HARD_SPLIT_FACTOR = 3
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
    """Soft line cap (default 150, clamped 1-400). Char budget is the real limiter.

    `link_facts` chops a fetched page into ~400-char lines, so one news article is
    already a dozen-plus lines and a long read is dozens. The old cap of 24 could
    not hold a single article alongside vault facts. Since run 74 an over-long line
    is *split* rather than sliced, which inflates the count again - hence 150. The
    char budget is still what actually decides.
    """
    raw = os.getenv("MAX_OPERATOR_KEY_FACTS", "150").strip()
    try:
        return max(1, min(400, int(raw)))
    except ValueError:
        return 150


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


_ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "vs",
        "etc",
        "inc",
        "ltd",
        "co",
        "corp",
        "no",
        "approx",
        "fig",
        "al",
        "ave",
        "gen",
        "gov",
        "sen",
        "rep",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sept",
        "sep",
        "oct",
        "nov",
        "dec",
        "u.s",
        "e.g",
        "i.e",
        "a.m",
        "p.m",
    }
)
# A sentence end is terminal punctuation (plus any closing quote/bracket) followed
# by whitespace. Abbreviations are filtered out afterwards, not by the pattern.
_SENTENCE_BOUNDARY = re.compile(r"([.!?][\"')\]]*)(\s+)")


def key_fact_split_width() -> int:
    """Width a fact line is split at. Env `MAX_KEY_FACT_CHARS`."""
    raw = os.getenv("MAX_KEY_FACT_CHARS", str(_MAX_KEY_FACT_CHARS)).strip()
    try:
        return max(80, min(4000, int(raw)))
    except ValueError:
        return _MAX_KEY_FACT_CHARS


def _ends_on_an_abbreviation(chunk: str) -> bool:
    if not chunk.endswith("."):
        return False
    last = chunk.rsplit(" ", 1)[-1].rstrip(".").lower()
    # "Nov." / "Inc." / a middle initial ("Rob J. Nelson").
    return last in _ABBREVIATIONS or (len(last) == 1 and last.isalpha())


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        candidate = text[start : match.end(1)].strip()
        if not candidate or _ends_on_an_abbreviation(candidate):
            continue
        out.append(candidate)
        start = match.end(2)
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _word_chunks(text: str, limit: int) -> list[str]:
    """Last resort for punctuation-free blobs: word boundaries, marked as elided."""
    words = text.split()
    out: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and length + extra > limit - 1:  # room for the ellipsis
            out.append(" ".join(current) + "…")
            current, length = [word], len(word)
            continue
        current.append(word)
        length += extra
    if current:
        out.append(" ".join(current))
    return out


def split_at_sentences(text: str, limit: int) -> list[str]:
    """Whole-sentence chunks of at most `limit` chars. Never cuts mid-sentence.

    This replaces `line[:400]`, which is what fed the model
    "...the campaign will progress through a chapter-based" in run 74. A severed
    clause does not read as a truncation to a language model - it reads as a
    finished, vague statement, and the model resolves the vagueness by inventing.

    A single sentence longer than `limit` is emitted whole: a real sentence is
    information, a fragment of one is a trap. Only a blob with no sentence
    punctuation at all (a scraped `<p>` holding a whole transcript) is cut, at word
    boundaries, with a trailing ellipsis so it still reads as elided rather than
    finished. Nothing here drops text - only the total prompt budget does that, and
    it reports what it dropped.
    """
    flat = _normalize_line(text)
    if not flat:
        return []
    limit = max(40, int(limit))
    if len(flat) <= limit:
        return [flat]

    out: list[str] = []
    current = ""
    for sentence in _sentences(flat):
        if len(sentence) > limit * _HARD_SPLIT_FACTOR:
            if current:
                out.append(current)
                current = ""
            out.extend(_word_chunks(sentence, limit))
            continue
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limit:
            current = f"{current} {sentence}"
        else:
            out.append(current)
            current = sentence
    if current:
        out.append(current)
    return out


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


def is_paste_command(text: str) -> bool:
    """True when the operator meant the paste-mode verb, not a fact line.

    Run 76: the prompt shows `` `paste` `` and the operator typed that, which was
    stored as fact 1 because mode entry required an exact `paste`. A glued
    article title after the verb is not the command itself — see
    ``paste_command_rest``.
    """
    raw = (text or "").strip().strip("`\"'").strip()
    core = raw.rstrip(".:!").strip()
    return core.lower() == "paste"


def paste_command_rest(text: str) -> str:
    """Remainder after a `paste` verb, if the operator glued the article on one line."""
    raw = (text or "").strip().strip("`\"'").strip()
    low = raw.lower()
    if is_paste_command(raw):
        return ""
    if low.startswith("paste ") or low.startswith("paste\t"):
        parts = raw.split(None, 1)
        return parts[1].strip() if len(parts) > 1 else ""
    return ""


_CHROME_EXACT = frozenset(
    {
        "share",
        "follow us",
        "follow author",
        "related tags",
        "learn more",
        "show less",
        "summary",
        "detail info",
        "about the authors",
        "credit: rockstar games",
        "this voice experience is generated by ai",
        "ffaaa",
    }
)
# Word-bounded disclosure phrasing, not bare words: a bare "affiliate" dropped real
# finance facts ("Amazon's affiliate program cut commission rates") and "about the
# author" matched "about the authorities".
_CHROME_MARKERS = re.compile(
    r"this voice experience is generated by ai|got a news tip|email news@"
    r"|\baffiliate links?\b|\baffiliate commissions?\b"
    r"|\bearn (?:a|an) (?:affiliate )?commission\b|\babout the authors?\b",
    re.I,
)
_LIKE_RE = re.compile(r"^like \(\d+\)$", re.I)
_TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}(?:\s*/\s*\d{1,2}:\d{2})?$")


def is_article_chrome(text: str) -> bool:
    """Page furniture that must not be pinned as operator ground truth (run 76)."""
    body = (text or "").strip().strip("`\"'").strip()
    if not body:
        return True
    if is_paste_command(body) and not paste_command_rest(body):
        return True
    low = body.lower()
    if low in _CHROME_EXACT:
        return True
    if _CHROME_MARKERS.search(low):
        return True
    return bool(_LIKE_RE.match(low) or _TIMESTAMP_RE.match(body))


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
        facts.extend(split_at_sentences(line, _MAX_KEY_FACT_CHARS * 2))
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
        elif is_writing_tip(line) or is_article_chrome(line):
            continue
        else:
            _flush_trade()
            if len(line) > 20:
                facts.extend(split_at_sentences(line, _MAX_KEY_FACT_CHARS * 2))

    _flush_trade()

    if not facts and text.strip():
        for ln in lines:
            ln = _BULLET_PREFIX.sub("", ln).strip()
            if len(ln) > 20 and not is_writing_tip(ln) and not is_article_chrome(ln):
                facts.extend(split_at_sentences(ln, _MAX_KEY_FACT_CHARS * 2))
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


def dedupe_key(line: str) -> str:
    """Identity of a fact for de-duplication. Shared so callers can key on it too."""
    return re.sub(r"[^a-z0-9]+", "", (line or "").lower())[:120]


def dedupe_facts(facts: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in facts:
        line = _normalize_line(raw)
        if not line or is_writing_tip(line):
            continue
        key = dedupe_key(line)
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

    Run 74: a line that overflows the split width is now *split* into whole
    sentences, not sliced at character 400. One pasted paragraph can therefore
    become several prompt lines. `dropped` still counts **source facts**, not
    lines, so the number the operator sees still means "facts you gave me that did
    not make it".
    """
    global _last_budget_report
    _last_budget_report = {"kept": 0, "dropped": 0, "reason": "", "chars": 0}
    if not facts:
        return []
    budget = operator_key_fact_char_budget()
    line_cap = max_operator_key_facts()
    width = key_fact_split_width()
    used = 0
    reason = ""
    out: list[str] = []
    consumed = 0  # source facts fully represented in `out`
    for raw in facts:
        if not isinstance(raw, str):
            consumed += 1
            continue
        line = _normalize_line(raw)
        if not line or is_writing_tip(line):
            consumed += 1
            continue
        pending: list[str] = []
        running = used
        complete = True
        for chunk in split_at_sentences(line, width):
            if len(out) + len(pending) >= line_cap:
                reason = f"line cap {line_cap} reached (raise MAX_OPERATOR_KEY_FACTS)"
                complete = False
                break
            cost = len(chunk) + 2
            if running + cost > budget:
                reason = f"char budget {budget} reached (raise OPERATOR_KEY_FACT_CHAR_BUDGET)"
                complete = False
                break
            pending.append(chunk)
            running += cost
        out.extend(pending)
        used = running
        if not complete:
            break
        consumed += 1

    dropped = max(0, len(facts) - consumed)
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
    tier: str = "operator",
) -> str | None:
    """Persist a fact set to Obsidian (all lines, no cap).

    `tier="link"` is for lines scraped from pasted URLs: they go to `_link_facts/`
    as `tier: link`. Until run 98 they were saved as operator facts, so page
    boilerplate and off-topic paragraphs came back in later runs pinned like lines
    the operator typed.
    """
    from config.channels import resolve_channel_id
    from core.obsidian_facts import _vault_path

    vault = _vault_path()
    if not vault or not facts:
        return None
    channel_id = resolve_channel_id(channel_id)
    day = (today or date.today()).isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", (topic or "run").lower()).strip("-")[:60] or "run"
    link = tier == "link"
    folder = "_link_facts" if link else "_operator_facts"
    path = vault / channel_id / folder / f"{day}_{slug}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(f"- {f}" for f in facts if f.strip())
        header = (
            "---\n"
            f"channel: {channel_id}\n"
            f"tags: [facts, {'link' if link else 'operator'}, research]\n"
            f"topic: {topic[:120]}\n"
            f"date: {day}\n"
            f"tier: {'link' if link else 'operator'}\n"
            f"verified_at: {day}\n"
            f"source: content-machine ({'pasted-link facts' if link else 'operator key facts'})\n"
            "---\n\n"
            f"# {'Link' if link else 'Operator'} facts — {topic[:80]}\n\n"
        )
        path.write_text(header + body + "\n", encoding="utf-8", newline="\n")
        logger.info("Saved %d operator facts to %s", len(facts), path)
        return str(path)
    except OSError as exc:
        logger.warning("operator facts vault write failed: %s", exc)
        return None
