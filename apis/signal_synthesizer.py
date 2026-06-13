import re
from collections import Counter

COMPARISON_WORDS = [
    "vs",
    "better than",
    "greater than",
    "compared to",
    "or",
    "over",
    "next",
    "future of",
    "goat",
]

DEBATE_WORDS = [
    "debate",
    "controversial",
    "exposed",
    "fraud",
    "overrated",
    "underrated",
    "truth",
    "real",
    "problem",
]

HYPE_WORDS = [
    "insane",
    "dominant",
    "unstoppable",
    "future star",
    "generational",
    "elite",
    "next level",
]


def extract_titles(signal):
    if not signal or not signal.get("active"):
        return []
    data = signal.get("data", {})
    return data.get("titles", [])


def extract_blog_headlines(signal):
    if not signal or not signal.get("active"):
        return []
    headlines = (signal.get("data") or {}).get("headlines") or []
    return [h.get("title", "") for h in headlines if h.get("title")]


def normalize_text(text):
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())


def detect_phrase_patterns(titles):
    tokens = []

    for title in titles:
        clean = normalize_text(title)
        tokens.extend(clean.split())

    counter = Counter(tokens)

    common_terms = [word for word, count in counter.items() if count >= 2 and len(word) > 3]

    return common_terms


def detect_comparison_density(titles):
    count = 0
    for title in titles:
        lower = title.lower()
        for word in COMPARISON_WORDS:
            if word in lower:
                count += 1
                break
    return count


def detect_debate_density(titles):
    count = 0
    for title in titles:
        lower = title.lower()
        for word in DEBATE_WORDS:
            if word in lower:
                count += 1
                break
    return count


def detect_hype_density(titles):
    count = 0
    for title in titles:
        lower = title.lower()
        for word in HYPE_WORDS:
            if word in lower:
                count += 1
                break
    return count


def synthesize_signals(base_signals):
    youtube_titles = extract_titles(base_signals.get("youtube"))
    blog_titles = extract_blog_headlines(base_signals.get("blog_rss"))

    combined_titles = youtube_titles + blog_titles

    if not combined_titles:
        return {
            "dominant_terms": [],
            "comparison_density": 0,
            "debate_density": 0,
            "hype_density": 0,
            "signal_strength": 0,
        }

    dominant_terms = detect_phrase_patterns(combined_titles)

    comparison_density = detect_comparison_density(combined_titles)
    debate_density = detect_debate_density(combined_titles)
    hype_density = detect_hype_density(combined_titles)

    signal_strength = comparison_density + debate_density + hype_density + len(dominant_terms)

    return {
        "dominant_terms": dominant_terms,
        "comparison_density": comparison_density,
        "debate_density": debate_density,
        "hype_density": hype_density,
        "signal_strength": signal_strength,
    }
