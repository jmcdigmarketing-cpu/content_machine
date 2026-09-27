"""Fact-fit: how much of the fact pool supports each angle (#849).

Signals are fetched once per topic and reused for every angle, so the composite is the
same number for all of them - run 98 tied five ways at 94.61 - and the editorial angle
score decided. The operator's calibration put that score at r=-0.26 (n=22, not
significant). Fact-fit reads something the angle text alone cannot: of the fact lines
the pipeline already holds when it chooses, how many say something this angle is about.

An angle's terms are its own words minus the seed topic's. Every fact about "GTA 6"
names GTA 6, so those words would give every angle the same score and separate nothing.

Measured and stored only; `best_variant_index` does not read it until calibration shows
it predicts something (the #819 lesson: nothing decides on zero rows).
"""

from __future__ import annotations

from apis.topic_tokens import content_tokens


def fact_lines(block: str) -> list[str]:
    """The bullet lines of a `format_signal_facts` block, without their "- "."""
    lines = []
    for raw in (block or "").splitlines():
        line = raw.strip()
        if line.startswith("- ") and line[2:].strip():
            lines.append(line[2:].strip())
    return lines


def fact_fit(angles: list[str], facts: list[str], *, seed_topic: str = "") -> dict[str, float]:
    """{angle: share of fact lines naming one of the angle's own terms}, 0.0-1.0."""
    seed = set(content_tokens(seed_topic or "", min_len=3))
    fact_terms = [set(content_tokens(fact, min_len=3)) for fact in facts or []]
    scores: dict[str, float] = {}
    for angle in angles:
        terms = set(content_tokens(angle or "", min_len=3)) - seed
        if not terms or not fact_terms:
            scores[angle] = 0.0
            continue
        hits = sum(1 for words in fact_terms if terms & words)
        scores[angle] = round(hits / len(fact_terms), 4)
    return scores
