"""#1700 (B05.4, wave 158): a strong story in two Shorts, a day apart.

Part 1 is the night's lead headline when it is on `PART_OUTLETS`+ outlets and names a marquee
name, and no pair is open: its last line is the one question part 2 answers ("Part 2: why the
Ravens let him go"), left open (`batch_generation.follow_brief`). Its draft opens the pair in
`data/parts_<channel>.json` - its run, its subject, that question and its facts. The next night,
once part 1 has rendered (12-72 hours on), "<subject>, part 2: <question>" is drafted from part
1's facts and that question, opening on the answer. A pair whose part 1 never rendered, or that
passed 72 hours, closes without a part 2. One pair at a time; `PART_SHORTS=false` stops it.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.series.parts")

PART_OUTLETS = 5
PART2_HOURS = (12.0, 72.0)
_PART2 = re.compile(r"\bpart\s*(?:2|two)\b\s*[:,-]?\s*", re.IGNORECASE)
_TOPIC = re.compile(r",\s*part 2:\s*(.+)$", re.IGNORECASE)


def enabled() -> bool:
    return os.getenv("PART_SHORTS", "true").strip().lower() not in ("0", "false", "no", "off")


def store_path(channel_id: str) -> str:
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, f"parts_{channel_id}.json")


def load_store(channel_id: str) -> dict[str, Any]:
    try:
        with open(store_path(channel_id), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_store(channel_id: str, data: dict[str, Any]) -> None:
    path = store_path(channel_id)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1)
        os.replace(tmp, path)
    except OSError as exc:
        logger.debug("parts store not written: %s", exc)


def part_one(ideas: list[Any], names: list[str], channel_id: str) -> str:
    """The topic of tonight's part 1 - the first fresh headline on `PART_OUTLETS`+ outlets naming a
    marquee name - or "" (off, a pair open, none qualifies)."""
    if not enabled() or load_store(channel_id).get("open"):
        return ""
    from apis.topic_tokens import names_any

    for bet in ideas:
        topic = str(getattr(bet, "topic", "") or "")
        if getattr(bet, "source", "") != "trending":
            continue
        if int(getattr(bet, "outlets", 0) or 0) >= PART_OUTLETS and names_any(topic, names):
            return topic
    return ""


def question_of(script: str) -> str:
    """The question part 1 leaves for part 2: its "Part 2: ..." line, else its last sentence."""
    from apis.topic_tokens import split_sentences

    sentences = [s.strip() for s in split_sentences(script or "") if s.strip()]
    if not sentences:
        return ""
    line = next((s for s in reversed(sentences) if _PART2.search(s)), sentences[-1])
    found = _PART2.search(line)
    text = line[found.end() :] if found else line
    return text.strip().strip("\"'").rstrip(".") or ""


def subject_of(topic: str, names: list[str]) -> str:
    from apis.topic_tokens import names_any

    return next((n for n in names if names_any(topic, [n])), "")


def record_part_one(
    channel_id: str,
    topic: str,
    run_id: int,
    script: str,
    facts: list[str] | None,
    *,
    names: list[str] | None = None,
    now: datetime | None = None,
) -> None:
    """Open the pair once part 1 is drafted. Bookkeeping: never raises."""
    try:
        if names is None:
            from core.best_bet import marquee_names

            names = marquee_names(channel_id)
        question = question_of(script)
        if not question:
            return
        moment = now or datetime.now(timezone.utc)
        save_store(channel_id, {**load_store(channel_id), "open": {
            "topic": topic, "run_id": int(run_id), "question": question,
            "subject": subject_of(topic, names) or topic.split(":")[0][:40],
            "facts": list(facts or [])[:8], "drafted": moment.isoformat(timespec="seconds")}})  # fmt: skip
    except Exception as exc:
        logger.debug("part 1 not recorded: %s", exc)


def part_two_topic(subject: str, question: str) -> str:
    return f"{subject}, part 2: {question}"


def question_in(topic: str) -> str:
    found = _TOPIC.search(topic or "")
    return found.group(1).strip() if found else ""


def _rendered(run_id: int) -> bool:
    try:
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(int(run_id))
        return bool(str(getattr(run, "mp4_path", "") or "").strip())
    except Exception as exc:
        logger.debug("part 1 run unread: %s", exc)
        return False


def part_two_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    rendered: Any = None,
    drafted: Any = None,
) -> list[Any]:
    """Tonight's part 2, or []. Closes a pair that is done, never rendered or past 72 hours."""
    if not enabled():
        return []
    try:
        from core.batch_generation import series_drafted
        from core.best_bet import BestBetResult

        store = load_store(channel_id)
        pair = store.get("open")
        if not isinstance(pair, dict):
            return []
        moment = now or datetime.now(timezone.utc)
        made = datetime.fromisoformat(str(pair.get("drafted") or ""))
        made = made if made.tzinfo else made.replace(tzinfo=timezone.utc)
        age = (moment - made).total_seconds() / 3600
        topic = part_two_topic(str(pair.get("subject") or ""), str(pair.get("question") or ""))
        low, high = PART2_HOURS
        if age < low:
            return []
        done = (drafted or series_drafted)(channel_id, topic)
        if done or age > high or not (rendered or _rendered)(int(pair.get("run_id") or 0)):
            store["open"] = None
            store.setdefault("closed", []).append({**pair, "part2": bool(done)})
            store["closed"] = store["closed"][-20:]
            save_store(channel_id, store)
            return []
        facts = [*list(pair.get("facts") or []),
                 f"Part 1 ({pair.get('topic')}) ended on the question: {pair.get('question')}"]  # fmt: skip
        from apis.topic_scorer import infer_topic_domain

        return [BestBetResult(
            topic=topic, domain=infer_topic_domain(str(pair.get("topic") or "")),
            avg_engaged_rate=0.0, source="part2", supporting_runs=0,
            facts=facts, rationale=f"part 2 · answers what run {pair.get('run_id')} asked")]  # fmt: skip
    except Exception as exc:
        logger.debug("part 2 skipped: %s", exc)
        return []


def part_brief(part: int, topic: str = "") -> str:
    """The script's direction for a part 1 or a part 2, or ""."""
    if part == 1:
        return (" End on the one question part 2 answers, as the last line, written \"Part 2: "
                "<the question>\" - leave it unanswered: no answer, no call to comment.")  # fmt: skip
    if part == 2:
        question = question_in(topic)
        return (f" This is part 2: open by answering what part 1 asked - \"{question}\" - with one "
                "short recap line at most, then the rest of the answer.")  # fmt: skip
    return ""
