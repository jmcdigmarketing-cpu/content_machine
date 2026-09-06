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

import statistics
from collections.abc import Sequence

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
    return f" ! {confidence_level(n)} confidence ({n} sample{plural})"


# 95% normal approximation. Deliberately not the Beta machinery in
# `core/experiment_stats.py`: that models a conversion count out of N trials,
# and these are means of an already-continuous engaged_rate.
_Z_95 = 1.96


def confidence_interval(values: Sequence[float]) -> float | None:
    """Half-width of the 95% interval around the mean, in the same units.

    `None` when it cannot be computed — fewer than two samples. That is the case
    that matters most (the loop's priors are built on n=1) and precisely the one
    where a number would be a lie: returning 0.0 would read as certainty.
    """
    clean = [float(v) for v in values or [] if v is not None]
    if len(clean) < 2:
        return None
    sem = statistics.stdev(clean) / (len(clean) ** 0.5)
    return round(_Z_95 * sem, 4)


def interval_note(values: Sequence[float]) -> str:
    """`" +/- 22pp"`-style suffix for a rationale line, or `""` when unavailable.

    Points, not percent-of-percent: the recommenders print rates as percentages,
    and "30.6% +/- 22%" invites reading the 22 as relative.
    """
    half = confidence_interval(values)
    if half is None:
        return ""
    return f" +/- {half * 100:.0f}pp"
