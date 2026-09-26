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


def content_tokens(text: str, *, min_len: int = 1) -> list[str]:
    """Lower-cased tokens of `text` minus function words, in order, de-duplicated.

    `min_len` drops shorter tokens (the relevance matchers use 3). Every module that
    asks "is this about the topic?" reads this - thirteen private copies meant run 98's
    question-word fix reached 1 of 7 of them (wave 36).
    """
    out: list[str] = []
    seen: set[str] = set()
    for tok in _TOKEN.findall((text or "").lower().replace("'", "")):
        if len(tok) < min_len or tok in FUNCTION_WORDS or tok in seen:
            continue
        seen.add(tok)
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


_NUMBER_AFTER = r"\s+((?:\d+|[IVX]+)\b)"


def search_query(
    topic: str,
    *,
    drop: tuple[str, ...] = (),
    max_len: int = 64,
    mode: str = "auto",
) -> str:
    """The name to send a name-search API: "Silksong", not the typed sentence (#852).

    `drop` removes the API's own noise words first ("review", "season"). A question or a
    sentence-length topic becomes its first Title-Case name, plus a number that follows
    it ("UFC 320"); a lower-case one keeps its content words. A short statement keeps
    its words, since it usually already is the name. `mode="entity"` takes the name
    whatever the length (a company, team or player search); `mode="keywords"` keeps up to
    five content words in order (a data-series or stock-footage search, #874). Eleven builders each did their own version and
    the #852 fix reached one of them (wave 36).
    """
    text = topic or ""
    if drop:
        text = re.sub(r"\b(" + "|".join(drop) + r")\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.;:-")
    sentence = starts_with_question(text) or len(text.split()) > 5
    if mode == "keywords":
        words = [w for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in FUNCTION_WORDS]
        return " ".join(words[:5])[:max_len] or text[:max_len] or (topic or "")[:max_len]
    if mode == "entity" or sentence:
        for phrase in title_phrases(text):
            name = re.sub(r"['’]s$", "", phrase)
            follow = re.match(re.escape(phrase) + _NUMBER_AFTER, text[text.find(phrase) :])
            if follow:
                name = f"{name} {follow.group(1)}"
            return name[:max_len]
        words = [w for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in FUNCTION_WORDS]
        if words:
            return " ".join(words[:3])[:max_len]
    return text[:max_len] or (topic or "")[:max_len]
