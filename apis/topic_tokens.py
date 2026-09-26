"""Content tokens of a typed topic: the words that can identify a subject.

Run 98 typed "Manchester City ofund guilty, what does this mean for the prem". Every
signal received the whole string, and three of them matched on the question words:
RAWG kept "What's This?", topic fan-out queried "what does this mean for the prem"
alone. One shared list of words that name nothing, so each signal stops carrying its
own partial copy.
"""

from __future__ import annotations

import re

# Question words, auxiliaries, pronouns and connectives. Deliberately NOT generic
# nouns ("update", "news", "game"): those are each signal's own call.
INTERROGATIVES = frozenset({"what", "whats", "how", "why", "who", "when", "where", "which"})

FUNCTION_WORDS = INTERROGATIVES | frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "i",
        "in",
        "is",
        "it",
        "its",
        "me",
        "mean",
        "means",
        "my",
        "of",
        "on",
        "or",
        "our",
        "s",
        "should",
        "that",
        "the",
        "their",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)

_TOKEN = re.compile(r"[a-z0-9]+")


def content_tokens(text: str) -> list[str]:
    """Lower-cased tokens of `text` minus function words, in order, de-duplicated."""
    out: list[str] = []
    for tok in _TOKEN.findall((text or "").lower().replace("'", "")):
        if tok in FUNCTION_WORDS or tok in out:
            continue
        out.append(tok)
    return out


def starts_with_question(text: str) -> bool:
    """True when `text`'s first word is a question word ("what does this mean ...")."""
    first = _TOKEN.findall((text or "").lower().replace("'", ""))
    return bool(first) and first[0] in INTERROGATIVES


_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.&-]*")


def title_phrases(text: str, *, max_words: int = 3) -> list[str]:
    """Title-Case names in the raw text, in order: "Manchester City", "Liverpool".

    A run of capitalised words, broken by punctuation, a lower-case word or a function
    word ("What does Arsenal ..." -> "Arsenal"), at most `max_words` long. Case is read
    from the original text, so a lower-case topic has none - callers fall back to
    `content_tokens`. Run 98's signals searched the whole typed sentence instead.
    """
    phrases: list[str] = []
    run: list[str] = []
    last_end = 0
    raw = text or ""

    def flush() -> None:
        if run:
            phrase = " ".join(run[:max_words])
            if phrase not in phrases:
                phrases.append(phrase)
            run.clear()

    for match in _WORD.finditer(raw):
        word = match.group(0).strip(".-")
        gap = raw[last_end : match.start()]
        last_end = match.end()
        if run and gap.strip():  # punctuation between words ends a name
            flush()
        lower = word.lower().replace("'", "").replace("’", "")
        if word[:1].isupper() and lower not in FUNCTION_WORDS:
            run.append(word)
        else:
            flush()
    flush()
    return phrases
