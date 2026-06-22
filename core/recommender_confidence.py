"""
Shared confidence labelling for analytics-driven recommenders.

best-bet, post-timing, and length all switch from a sensible default to an
analytics-derived pick once "enough" measured samples exist. With only a handful
of samples a single video can flip the pick, so the recommenders should surface
HOW solid the basis is rather than printing a thin average as if it were
authoritative (e.g. "28.9% across 4 videos" reads as fact but is barely a trend).

One place defines the sample-count bands so every recommender speaks the same
language.
"""

from __future__ import annotations

# Sample-count bands (number of measured videos backing the figure shown).
#   >= SOLID    : trust it, no caveat printed
#   >= MODERATE : usable, but flag it
#   <  MODERATE : barely more than anecdote
SOLID_SAMPLES = 8
MODERATE_SAMPLES = 4


def confidence_level(n: int) -> str:
    """Map a supporting-sample count to 'high' | 'moderate' | 'low'."""
    if n >= SOLID_SAMPLES:
        return "high"
    if n >= MODERATE_SAMPLES:
        return "moderate"
    return "low"


def confidence_note(n: int) -> str:
    """
    Short parenthetical to append to a recommendation's reason line.

    Empty when the basis is solid (>= SOLID_SAMPLES) so high-confidence picks
    stay uncluttered; otherwise names the level and the sample count.
    """
    if confidence_level(n) == "high":
        return ""
    plural = "s" if n != 1 else ""
    return f" ⚠ {confidence_level(n)} confidence ({n} sample{plural})"
