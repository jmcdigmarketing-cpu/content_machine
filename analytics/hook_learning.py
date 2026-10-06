"""The hook learns from the stayed share (#985).

The hook scorer (`core/hook_score`) rates a script's opening line on fixed traits: a number, a
name, brevity, a contradiction, stakes, no question. Nothing checked those traits against what
viewers did. The sync keeps, per Short, the share of starts not swiped away (`stayed`, #951). This
joins each uploaded video's stayed share to its run's opening line and reports:

- the correlation of the hook score with stayed, and the n that would settle it (#824);
- per trait, the median stayed share of openers with it against without it (`_MIN_SIDE` each);
- the three openers that held viewers best.

Below `HOOK_LEARN_MIN` measured videos it is "collecting". Once ready, `regen_guidance` feeds
the opt-in hook rewrite (`content_engine._maybe_improve_hook`): the openers that held best as
examples, the trait that held more viewers, and the one that held fewer.
"""

from __future__ import annotations

import json
import os
import statistics
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.hook_learning")

_MIN_SIDE = 3
_GAP = 0.05

# hook_score reason labels -> the trait as the operator reads it.
_TRAITS = {
    "has a number": "a number",
    "names a specific entity": "a name",
    "opens as a question": "a question",
    "curiosity / contradiction": "a contradiction",
    "high stakes": "stakes",
    "weak opener": "a weak opener",
}


def learn_min() -> int:
    try:
        return max(3, int(os.getenv("HOOK_LEARN_MIN", "10")))
    except ValueError:
        return 10


def _publish_repo() -> Any:
    from storage.repositories.publish_log import get_publish_log_repository

    return get_publish_log_repository()


def _run_repo() -> Any:
    from storage.repositories.content_runs import get_content_run_repository

    return get_content_run_repository()


def traits_of(hook: str) -> set[str]:
    """The scorer's own traits for one opening line (concise = 12 words or fewer)."""
    from core.hook_score import score_hook

    out: set[str] = set()
    for label, _delta in score_hook(hook).reasons:
        if label.startswith("concise"):
            out.add("12 words or fewer")
        elif label in _TRAITS:
            out.add(_TRAITS[label])
    return out


def _rows(channel_id: str) -> list[dict[str, Any]]:
    from analytics.packaging import packaging_figures
    from core.hook_score import extract_hook, score_hook
    from storage.repositories.publish_log import is_seeded

    runs = _run_repo()
    out: list[dict[str, Any]] = []
    for row in _publish_repo().list_uploaded_for_channel(channel_id) or []:
        if not getattr(row, "youtube_video_id", "") or is_seeded(row):
            continue
        try:
            metrics = json.loads(getattr(row, "metrics_json", None) or "{}")
        except (TypeError, ValueError):
            continue
        stayed = packaging_figures(metrics if isinstance(metrics, dict) else {}).get("stayed")
        run_id = getattr(row, "content_run_id", None)
        if stayed is None or not run_id:
            continue
        run = runs.get(int(run_id))
        hook = extract_hook(str(getattr(run, "script", "") or "")) if run else ""
        if not hook:
            continue
        out.append({
            "hook": hook,
            "score": float(score_hook(hook).score),
            "traits": traits_of(hook),
            "stayed": float(stayed),
        })  # fmt: skip
    return out


def learn(channel_id: str) -> dict[str, Any]:
    """{n, ready, r, needs, traits: [{trait, with, without, gap, n_with, n_without}], best_hooks}."""
    from core.grade_calibration import _pearson, n_for_significance

    rows = _rows(channel_id)
    n = len(rows)
    out: dict[str, Any] = {"n": n, "min": learn_min(), "ready": n >= learn_min()}
    r = _pearson([x["score"] for x in rows], [x["stayed"] for x in rows])
    out["r"] = round(r, 3) if r is not None else None
    out["needs"] = n_for_significance(r)
    traits: list[dict[str, Any]] = []
    for trait in sorted({t for x in rows for t in x["traits"]}):
        with_t = [x["stayed"] for x in rows if trait in x["traits"]]
        without = [x["stayed"] for x in rows if trait not in x["traits"]]
        if len(with_t) < _MIN_SIDE or len(without) < _MIN_SIDE:
            continue
        a, b = statistics.median(with_t), statistics.median(without)
        traits.append({"trait": trait, "with": round(a, 3), "without": round(b, 3),
                       "gap": round(a - b, 3), "n_with": len(with_t),
                       "n_without": len(without)})  # fmt: skip
    out["traits"] = sorted(traits, key=lambda t: -t["gap"])
    best = sorted(rows, key=lambda x: -x["stayed"])[:3]
    out["best_hooks"] = [(x["hook"], x["stayed"]) for x in best]
    return out


def _held(t: dict[str, Any]) -> str:
    return f"openers with {t['trait']} held {t['with']:.0%} vs {t['without']:.0%}"


def render_line(channel_id: str) -> str:
    """One line for `ops growth` and the app's analytics page."""
    got = learn(channel_id)
    if not got["ready"]:
        return (
            f"Hook vs stayed: collecting - {got['n']} of {got['min']} videos with an opening "
            "line and a stayed share"
        )
    parts = [f"Hook vs stayed over {got['n']} videos:"]
    if got["r"] is not None:
        if got["needs"] and got["n"] >= got["needs"]:
            needs = " (clears p<0.05 at this n)"
        else:
            needs = f", settles at n={got['needs']}" if got["needs"] else ""
        parts.append(f"score r={got['r']:+.2f}{needs}")
    up = [t for t in got["traits"] if t["gap"] >= _GAP][:1]
    down = [t for t in reversed(got["traits"]) if t["gap"] <= -_GAP][:1]
    parts.extend(_held(t) for t in up + down)
    if not up and not down:
        parts.append("no trait separates them yet")
    return " ".join(parts[:1]) + " " + " · ".join(parts[1:])


def regen_guidance(channel_id: str) -> dict[str, Any]:
    """What the hook rewrite may use: {} until `learn_min` videos are measured."""
    if not channel_id:
        return {}
    try:
        got = learn(channel_id)
    except Exception as exc:
        logger.debug("hook learning unavailable: %s", exc)
        return {}
    if not got["ready"]:
        return {}
    return {
        "examples": [hook for hook, _stayed in got["best_hooks"]],
        "prefer": [t for t in got["traits"] if t["gap"] >= _GAP][:2],
        "avoid": [t for t in reversed(got["traits"]) if t["gap"] <= -_GAP][:2],
    }


def rank_openers(hooks: list[str], guidance: dict[str, Any]) -> list[tuple[str, float]]:
    """#987: openers best first - the scorer's score plus the learned trait gaps (x100).

    Before learning is ready (`guidance` empty) it is the scorer alone. A stable sort, so a tie
    keeps the order the openers came in.
    """
    from core.hook_score import score_hook

    learned = [*(guidance.get("prefer") or []), *(guidance.get("avoid") or [])]
    scored: list[tuple[str, float]] = []
    for hook in hooks:
        text = (hook or "").strip()
        if not text:
            continue
        traits = traits_of(text)
        bonus = sum(float(t["gap"]) * 100 for t in learned if t["trait"] in traits)
        scored.append((text, round(score_hook(text).score + bonus, 1)))
    return sorted(scored, key=lambda pair: -pair[1])
