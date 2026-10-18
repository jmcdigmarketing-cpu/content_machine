"""#450: facts from a voice note - a memo recorded on a phone, transcribed, one fact a sentence.

`py -m scripts.ops voice-facts --path memo.m4a --run-id 165` prints what it heard; `--apply` saves
the lines to the vault as the operator's own for that run's subject (the booth's facts box, wave
107, takes the same path), or for `--topic "..."`. Transcription is the caption aligner's
(`core.caption_align.transcribe_and_align`, faster-whisper), so nothing new is installed.
"""

from __future__ import annotations

import re

from core.logging import get_logger

logger = get_logger("core.facts.voice_notes")


def transcript_lines(path: str) -> tuple[list[str], str]:
    """(one line a sentence, "") - or ([], why) when the memo cannot be transcribed."""
    from core.caption_align import transcribe_and_align
    from core.operator_facts import sentences

    result = transcribe_and_align(path)
    if not result.ok:
        return [], str(result.detail or "the memo could not be transcribed")
    words = [str(item.get("word") or "").strip() for item in result.data or []]
    # The aligner strips each word, so "p" + ".m." came back as "8 p .m." on a test memo.
    text = re.sub(r"\s+(?=[.,!?;:%])", "", " ".join(word for word in words if word))
    lines = [line.strip() for line in sentences(text) if line.strip()]
    return (lines, "") if lines else ([], "no words were heard")


def known_names(text: str) -> list[str]:
    """The single words of the names `text` carries - a run's title and subject (#1296)."""
    from apis.topic_tokens import name_phrases

    words: list[str] = []
    for phrase in name_phrases(text or "", max_words=5, connectors=True):
        for word in phrase.split():
            if len(word) >= 4 and word not in words:
                words.append(word)
    return words


def correct_names(lines: list[str], names: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """#1296: a test memo was heard "Malott" as "Molot". A heard name close to one of the run's
    own (same first letter, a close spelling) is written as the run's; other words stay."""
    import difflib

    from apis.topic_tokens import name_phrases

    known = {name.lower(): name for name in names}
    out: list[str] = []
    fixes: list[tuple[str, str]] = []
    for line in lines:
        for phrase in name_phrases(line, max_words=5, connectors=True):
            for word in phrase.split():
                low = word.lower()
                if len(word) < 4 or low in known:
                    continue
                pool = [k for k in known if k[0] == low[0]]
                match = difflib.get_close_matches(low, pool, n=1, cutoff=0.7)
                if match:
                    line = re.sub(rf"\b{re.escape(word)}\b", known[match[0]], line)
                    if (word, known[match[0]]) not in fixes:
                        fixes.append((word, known[match[0]]))
        out.append(line)
    return out, fixes


def run_names(run_id: int) -> str:
    """The text a run's names come from: its title and subject, or "" (#1296)."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(int(run_id))
    except Exception as exc:
        logger.debug("voice notes: run %s unread: %s", run_id, exc)
        return ""
    if run is None:
        return ""
    parts = (getattr(run, name, "") for name in ("title", "input_topic", "selected_topic"))
    return " . ".join(str(p) for p in parts if p)


def save_topic_facts(channel_id: str, topic: str, lines: list[str]) -> int:
    """The lines as the operator's facts for ``topic``; how many were kept."""
    from core.operator_facts import capture_facts_to_vault, clean_typed_lines

    facts, _dropped = clean_typed_lines([(line, False) for line in lines])
    if not facts or not topic.strip():
        return 0
    path = capture_facts_to_vault(channel_id, topic, facts, tier="operator", origin="voice")
    return len(facts) if path else 0
