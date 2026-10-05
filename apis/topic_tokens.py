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
        # #972: indefinite pronouns - "Somebody has to be the East favorite" (run 113) is
        # not a name, and nothing a topic is about.
        "anybody",
        "anyone",
        "anything",
        "everybody",
        "everyone",
        "everything",
        "nobody",
        "nothing",
        "somebody",
        "someone",
        "something",
    }
)

# #925: the words a news headline is made of whatever it is about. Not function words -
# a topic may still be *about* a trailer - but a headline that shares only these with the
# topic is not about it: run 109's "New Uncharted Game ..." matched "Over 85 Percent Of
# Japanese Game Developers Are Using AI" on "game". Opt-in: a matcher that wants a
# distinctive hit asks `distinctive_tokens`.
NEWS_REGISTER_WORDS = frozenset(
    {
        "new",
        "news",
        "game",
        "games",
        "gaming",
        "video",
        "videos",
        "report",
        "reports",
        "reported",
        "reportedly",
        "featuring",
        "feature",
        "features",
        "work",
        "works",
        "working",
        "update",
        "updates",
        "official",
        "officially",
        "latest",
        "first",
        "big",
        "huge",
        "top",
        "best",
        "fan",
        "fans",
        "says",
        "said",
        "announced",
        "announces",
        "reveal",
        "reveals",
        "revealed",
        "trailer",
        "release",
        "released",
        "coming",
        "soon",
        "today",
        "week",
        "year",
    }
)

_TOKEN = re.compile(r"[a-z0-9]+")


def fold_accents(text: str) -> str:
    """ "Pokémon" -> "Pokemon", "Yōtei" -> "Yotei": accents fold to the base letter (#963),
    so an accented name and a headline that drops the accent share their tokens."""
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def content_tokens(text: str, *, min_len: int = 1) -> list[str]:
    """Lower-cased tokens of `text` minus function words, in order, de-duplicated.

    `min_len` drops shorter tokens (the relevance matchers use 3). Every module that
    asks "is this about the topic?" reads this - thirteen private copies meant run 98's
    question-word fix reached 1 of 7 of them (wave 36).
    """
    out: list[str] = []
    seen: set[str] = set()
    for tok in _TOKEN.findall(fold_accents(text or "").lower().replace("'", "")):
        if len(tok) < min_len or tok in FUNCTION_WORDS or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def distinctive_tokens(tokens: list[str]) -> list[str]:
    """`tokens` minus news-register words and bare years (#925) - what can name a subject."""
    return [
        t
        for t in tokens
        if t not in NEWS_REGISTER_WORDS
        and not (len(t) == 4 and t.isdigit() and t[:2] in ("19", "20"))
    ]


def contains_phrase(text: str, phrase: str) -> bool:
    """True when `phrase`'s words appear in `text` consecutively, as whole words.

    "Manchester City" is in "Manchester City fined again"; "Premier" is not in "The
    Premiership". Case and punctuation are ignored. An empty phrase is never found.
    """
    words = _TOKEN.findall((text or "").lower().replace("'", ""))
    want = _TOKEN.findall((phrase or "").lower().replace("'", ""))
    if not want:
        return False
    n = len(want)
    return any(words[i : i + n] == want for i in range(len(words) - n + 1))


def starts_with_question(text: str) -> bool:
    """True when `text`'s first word is a question word ("what does this mean ...")."""
    first = _TOKEN.findall((text or "").lower().replace("'", ""))
    return bool(first) and first[0] in INTERROGATIVES


# #969: letters are Unicode letters - "Yōtei" and "Pokémon" are one word, not "Y" + "tei".
_WORD = re.compile(r"[^\W_](?:[^\W_]|['’.&-])*")


# #963: lower-case words that sit inside a name - "Ghost of Yotei", "Call of Duty",
# "Lord of the Rings" - when `title_phrases(..., connectors=True)`.
NAME_CONNECTORS = frozenset({"of", "the", "de", "la", "del", "da", "von", "van"})


def title_phrases(text: str, *, max_words: int = 3, connectors: bool = False) -> list[str]:
    """Title-Case names in the raw text, in order: "Manchester City", "Liverpool".

    A run of capitalised words, broken by punctuation, a lower-case word or a function
    word ("What does Arsenal ..." -> "Arsenal"), at most `max_words` long. Case is read
    from the original text, so a lower-case topic has none - callers fall back to
    `content_tokens`. Run 98's signals searched the whole typed sentence instead.
    `connectors=True` keeps a lower-case `NAME_CONNECTORS` word between two capitalised
    ones inside the name ("Ghost of Yotei", not "Ghost" and "Yotei") - for name lookups.
    #969: "the" only follows another connector ("Lord of the Rings", never "Reasons the
    Lakers"), connectors do not count toward `max_words`, and a cut name never ends on one.
    """
    phrases: list[str] = []
    run: list[str] = []
    held: list[str] = []  # connector words waiting for a capitalised word
    last_end = 0
    raw = text or ""

    def flush() -> None:
        held.clear()
        if run:
            kept: list[str] = []
            names = 0
            cut = False
            for word in run:
                is_connector = word in NAME_CONNECTORS
                if not is_connector and names >= max_words:
                    cut = True
                    break
                kept.append(word)
                names += 0 if is_connector else 1
            if cut and any(w in NAME_CONNECTORS for w in kept):
                # the name after the last connector was cut: "Southern District of New"
                while kept and kept[-1] not in NAME_CONNECTORS:
                    kept.pop()
            while kept and kept[-1] in NAME_CONNECTORS:
                kept.pop()
            phrase = " ".join(kept)
            if phrase and phrase not in phrases:
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
            run.extend(held)
            held.clear()
            run.append(word)
        elif (
            connectors
            and run
            and word == lower
            and lower in NAME_CONNECTORS
            and (held or lower != "the")
        ):
            held.append(word)
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
        for phrase in title_phrases(text, connectors=True):  # #969: "Ghost of Yotei"
            name = re.sub(r"['’]s$", "", phrase)
            follow = re.match(re.escape(phrase) + _NUMBER_AFTER, text[text.find(phrase) :])
            if follow:
                name = f"{name} {follow.group(1)}"
            return name[:max_len]
        words = [w for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in FUNCTION_WORDS]
        if words:
            return " ".join(words[:3])[:max_len]
    return text[:max_len] or (topic or "")[:max_len]
