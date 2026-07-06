"""Causal attribution for the experimentation harness — Bayesian, low-n-safe.

Per arm we have a sample of engaged-rates (one per published video). We binarize
each against the experiment's pooled mean (success = "beat the average"), put a
Beta(1,1) prior on each arm's success probability, and Monte-Carlo the posteriors
to get P(arm is best). A winner is declared only when every arm has enough samples
AND the leader's P(best) clears a threshold — otherwise "collecting" / "no clear
winner", never a false positive from 3 videos.

Bayesian + a weak prior is the standard bandit approach and behaves sanely at the
low sample counts a single channel produces. Dependency-free: `random.betavariate`.
"""

from __future__ import annotations

import random

_DEFAULT_DRAWS = 20000
_DEFAULT_WIN_PROB = 0.95


def _baseline(arm_outcomes: dict[str, list[float]]) -> float:
    pooled = [r for rates in arm_outcomes.values() for r in rates]
    return (sum(pooled) / len(pooled)) if pooled else 0.0


def evaluate(
    arm_outcomes: dict[str, list[float]],
    *,
    min_per_arm: int = 6,
    baseline: float | None = None,
    draws: int = _DEFAULT_DRAWS,
    win_prob: float = _DEFAULT_WIN_PROB,
    rng: random.Random | None = None,
) -> dict:
    """Per-arm posteriors + a confidence-gated winner.

    Returns {arms: {arm: {n, successes, rate, post_mean, p_best}}, winner, status,
    baseline}. `status`: collecting | no_clear_winner | winner | insufficient.
    """
    base = _baseline(arm_outcomes) if baseline is None else baseline
    arms: dict[str, dict] = {}
    for arm, rates in arm_outcomes.items():
        n = len(rates)
        successes = sum(1 for r in rates if r >= base)
        arms[arm] = {
            "n": n,
            "successes": successes,
            "rate": (sum(rates) / n) if n else 0.0,
            "post_mean": (1 + successes) / (2 + n),
            "p_best": 0.0,
        }

    names = [a for a in arms if arms[a]["n"] > 0]
    if len(names) < 2:
        return {"arms": arms, "winner": None, "status": "insufficient", "baseline": base}

    r = rng or random.Random(12345)  # seeded → deterministic, testable
    wins = dict.fromkeys(names, 0)
    for _ in range(draws):
        best, best_val = None, -1.0
        for a in names:
            d = arms[a]
            sample = r.betavariate(1 + d["successes"], 1 + d["n"] - d["successes"])
            if sample > best_val:
                best, best_val = a, sample
        wins[best] += 1
    for a in names:
        arms[a]["p_best"] = wins[a] / draws

    enough = all(arms[a]["n"] >= min_per_arm for a in names)
    leader = max(names, key=lambda a: arms[a]["p_best"])
    if not enough:
        status, winner = "collecting", None
    elif arms[leader]["p_best"] >= win_prob:
        status, winner = "winner", leader
    else:
        status, winner = "no_clear_winner", None
    return {"arms": arms, "winner": winner, "status": status, "baseline": base}
