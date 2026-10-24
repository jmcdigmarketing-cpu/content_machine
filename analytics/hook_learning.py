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
from datetime import datetime, timedelta, timezone
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


def examples_count() -> int:
    """#1504: how many best-held openers the rewrite quotes (`HOOK_EXAMPLES`, default 10)."""
    try:
        return max(1, int(os.getenv("HOOK_EXAMPLES", "10")))
    except ValueError:
        return 10


def learn_days() -> int:
    """Decision 67: the last 90 days teach. All 41 videos made the three best openers June 4's
    first batch ("Grand Theft Auto VI is on the horizon..."); `HOOK_LEARN_DAYS=0` is all."""
    try:
        return max(0, int(os.getenv("HOOK_LEARN_DAYS", "90")))
    except ValueError:
        return 90


# Decision 67: what the rewrite's fixed rules want (the prompt asks for "a specific fact, number,
# or contradiction, under 12 words"; the scorer rewards a name and stakes) and what they ban
# ("never ... a question"; a weak opener). A learned note against them waits until n settles.
_RULE_WANTS = frozenset({"a number", "a name", "12 words or fewer", "a contradiction", "stakes"})
_RULE_BANS = frozenset({"a question", "a weak opener"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _rows(channel_id: str, *, detail: bool = False) -> list[dict[str, Any]]:
    """Each measured video's opening line and stayed share; `detail` (the hook table) adds its
    length, its 3-second share and TikTok's watch time - a render's length is an ffprobe each."""
    from analytics.packaging import packaging_figures
    from core.hook_score import extract_hook, score_hook
    from core.runs.script_report import script_of
    from storage.repositories.publish_log import is_seeded

    platform: dict[str, Any] = {}
    if detail:
        try:
            from publishing.platform_metrics import load

            platform = load(channel_id).get("rows") or {}
        except Exception as exc:
            logger.debug("platform metrics unread for the hook table: %s", exc)
    runs = _run_repo()
    days = learn_days()
    since = _now() - timedelta(days=days) if days else None
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
        if run is None or (since is not None and not _made_since(run, since)):
            continue
        # #1287: `run.script` - a field no content run has - joined 0 of 41 videos.
        hook = extract_hook(script_of(run))
        if not hook:
            continue
        row_out: dict[str, Any] = {
            "run_id": int(run_id),
            "hook": hook,
            "score": float(score_hook(hook).score),
            "traits": traits_of(hook),
            "stayed": float(stayed),
        }
        if detail:
            from core.retention import _render_seconds

            row_out.update(
                detail_of(hook, metrics, platform.get(str(run_id)) or {}, _render_seconds(run))
            )
        out.append(row_out)
    return out


def detail_of(
    hook: str, metrics: dict[str, Any], platforms: dict[str, Any], seconds: float | None
) -> dict[str, Any]:
    """One video's hook-table fields: words, `first3` (YouTube's share 3 s in - None over 100%,
    which is a replayed opening, #1538) and `tiktok_s` (TikTok's average watch, #1418)."""
    from core.retention import _parse_curve, share_at

    first3 = share_at(_parse_curve(metrics.get("retention_curve")), seconds)
    tiktok = platforms.get("tiktok") if isinstance(platforms, dict) else None
    watch = (
        tiktok.get("avg_watch_s") if isinstance(tiktok, dict) and tiktok.get("measured") else None
    )
    return {
        "words": len(hook.split()),
        "first3": first3 if first3 is not None and first3 <= 1.0 else None,
        "first3_replayed": first3 is not None and first3 > 1.0,
        "tiktok_s": float(watch) if isinstance(watch, (int, float)) else None,
    }


# #1505: the rewrite's rule is "under 12 words"; the bins put 12 on its side.
_LENGTH_BINS = (
    (8, "8 words or fewer"),
    (12, "9-12 words"),
    (16, "13-16 words"),
    (10**6, "17+ words"),
)
_MEASURES = (("stayed", "stayed"), ("first3", "3 s"), ("tiktok", "TikTok s"))


def _side(rows: list[dict[str, Any]], key: str, trait: str) -> dict[str, Any]:
    with_t = [float(x[key]) for x in rows if trait in x["traits"] and x.get(key) is not None]
    without = [float(x[key]) for x in rows if trait not in x["traits"] and x.get(key) is not None]

    def median(values: list[float]) -> float | None:
        return round(statistics.median(values), 3) if len(values) >= _MIN_SIDE else None

    return {"with": median(with_t), "without": median(without),
            "n_with": len(with_t), "n_without": len(without)}  # fmt: skip


def hook_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """#1500 #1501 #1506: every opener trait - the scorer's and "a call" (the first-line rule,
    #1311) - with and without, against the share who stayed, the 3-second share and TikTok's
    watch time; #1505: the opener's length in bins and its r with stayed. A side under
    `_MIN_SIDE` videos has no median. Report-only: the rewrite's guidance is `learn`'s."""
    from core.authenticity import first_line_take
    from core.grade_calibration import _pearson

    marked = [
        {**x, "traits": set(x["traits"]) | ({"a call"} if first_line_take(x["hook"]) else set()),
         "tiktok": x.get("tiktok_s")}
        for x in rows
    ]  # fmt: skip
    traits = []
    for trait in sorted({t for x in marked for t in x["traits"]} | {"a call"}):
        traits.append({"trait": trait, **{key: _side(marked, key, trait) for key, _l in _MEASURES}})
    length = []
    low = 0
    for top, label in _LENGTH_BINS:
        stayed = [x["stayed"] for x in marked if low < int(x.get("words") or 0) <= top]
        length.append({"bin": label, "n": len(stayed),
                       "stayed": round(statistics.median(stayed), 3) if stayed else None})  # fmt: skip
        low = top
    worded = [x for x in marked if x.get("words")]
    r = _pearson([float(x["words"]) for x in worded], [x["stayed"] for x in worded])
    return {"n": len(marked), "traits": traits, "length": length,
            "length_r": round(r, 3) if r is not None else None,
            "first3_readable": sum(1 for x in marked if x.get("first3") is not None),
            "first3_replayed": sum(1 for x in marked if x.get("first3_replayed")),
            "tiktok_measured": sum(1 for x in marked if x.get("tiktok") is not None)}  # fmt: skip


def _pair(side: dict[str, Any]) -> str:
    if side["with"] is None or side["without"] is None:
        return f"n {side['n_with']}/{side['n_without']}, too few"
    fmt = "{:.0%}" if max(side["with"], side["without"]) <= 1.0 else "{:.1f}"
    return (f"{fmt.format(side['with'])} vs {fmt.format(side['without'])} "
            f"(n {side['n_with']}/{side['n_without']})")  # fmt: skip


def length_text(table: dict[str, Any]) -> str:
    bins = "; ".join(
        f"{b['bin']} {b['stayed']:.0%} (n {b['n']})" for b in table["length"] if b["n"]
    )
    r = table.get("length_r")
    return f"Hook length vs stayed: {bins}" + (
        f"; r={r:+.2f} over {table['n']}" if r is not None else ""
    )


def length_line(channel_id: str) -> str:
    """#1505: one line for `ops growth`."""
    return length_text(hook_table(_rows(channel_id)))


def hook_table_lines(channel_id: str) -> list[str]:
    """`ops hooks`: the table, one line a trait, then length."""
    table = hook_table(_rows(channel_id, detail=True))
    out = [
        f"Hooks - {channel_id}: {table['n']} videos with an opening line and a stayed share "
        f"(the last {learn_days() or 'all'} days). With the trait vs without; a side under "
        f"{_MIN_SIDE} videos is too few.",
        f"  {'trait':20} {'stayed':24} {'3 s (YouTube)':24} TikTok s (avg watch)",
    ]
    for t in table["traits"]:
        out.append(
            f"  {t['trait']:20} {_pair(t['stayed']):24} {_pair(t['first3']):24} {_pair(t['tiktok'])}"
        )
    out.append(f"  {length_text(table)}")
    out.append(
        f"  3 s readable on {table['first3_readable']} of {table['n']} "
        f"({table['first3_replayed']} read over 100% - a replayed opening, #1538); TikTok's "
        f"watch time on {table['tiktok_measured']}"
    )
    out.append(
        "  The hook score is out of the grade and overnight's order (decision 70); "
        "`ops growth` prints its r."
    )
    return out


def _made_since(run: Any, since: datetime) -> bool:
    made = getattr(run, "created_at", None)
    if isinstance(made, str):
        try:
            made = datetime.fromisoformat(made.replace("Z", "+00:00"))
        except ValueError:
            return True
    if not isinstance(made, datetime):
        return True  # an unknown age is not a reason to drop the video
    if made.tzinfo is None:
        made = made.replace(tzinfo=timezone.utc)
    return made >= since


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
    best = sorted(rows, key=lambda x: -x["stayed"])[: examples_count()]  # #1504: was 3
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
            # #1507 (wave 114): that n is the correlation's; the score itself is retuned on
            # logic until n of about 85 (master_plan M4.5, wave 112).
            needs += "; the score's retune waits for about 85 (master_plan M4.5)"
        parts.append(f"score r={got['r']:+.2f}{needs}")
    up = [t for t in got["traits"] if t["gap"] >= _GAP][:1]
    down = [t for t in reversed(got["traits"]) if t["gap"] <= -_GAP][:1]
    parts.extend(_held(t) for t in up + down)
    if not up and not down:
        parts.append("no trait separates them yet")
    waiting = _against_rules(got)
    if waiting:
        until = f"n={got['needs']}" if got.get("needs") else "the number settles"
        parts.append(f"the rewrite keeps its rule on {' and '.join(waiting)} until {until}")
    return " ".join(parts[:1]) + " " + " · ".join(parts[1:])


def _settled(got: dict[str, Any]) -> bool:
    needs = got.get("needs")
    return bool(needs) and int(got.get("n") or 0) >= int(needs)


def _against_rules(got: dict[str, Any]) -> list[str]:
    """Learned notes the rewrite's fixed rules contradict, while n has not settled them."""
    if _settled(got):
        return []
    traits = got.get("traits") or []
    return [
        t["trait"]
        for t in traits
        if (t["gap"] >= _GAP and t["trait"] in _RULE_BANS)
        or (t["gap"] <= -_GAP and t["trait"] in _RULE_WANTS)
    ]


def guidance_from(got: dict[str, Any]) -> dict[str, Any]:
    """What the hook rewrite may use from `learn`'s result: {} until `learn_min` videos.

    Decision 67: a learned note that contradicts the rewrite's fixed rules - questions held
    more, numbers fewer, over 18 videos on 2026-10-18 - is left out until n reaches the n that
    settles it (`needs`); the rest goes in as measured."""
    if not got.get("ready"):
        return {}
    held_back = set(_against_rules(got))
    traits = [t for t in got.get("traits") or [] if t["trait"] not in held_back]
    return {
        # #1504: each with the share who stayed, so the model reads how well it held
        "examples": [
            f"{hook} ({stayed:.0%} stayed)" for hook, stayed in got.get("best_hooks") or []
        ],
        "prefer": [t for t in traits if t["gap"] >= _GAP][:2],
        "avoid": [t for t in reversed(traits) if t["gap"] <= -_GAP][:2],
        "settled": _settled(got),  # decision 67: a settled note outranks the fixed rule
    }


def regen_guidance(channel_id: str) -> dict[str, Any]:
    """What the hook rewrite may use: {} until `learn_min` videos are measured."""
    if not channel_id:
        return {}
    try:
        got = learn(channel_id)
    except Exception as exc:
        logger.debug("hook learning unavailable: %s", exc)
        return {}
    return guidance_from(got)


def rank_by_traits(hooks: list[str], guidance: dict[str, Any]) -> list[tuple[str, float]]:
    """#1556 (the operator, 2026-10-23: measured traits - decision 73): openers best first by the
    channel's learned trait gaps (x100) alone - not `score_hook`, which ran against who stayed
    (r = -0.48 over 22). With no learning yet every opener ranks 0. A stable sort."""
    learned = [*(guidance.get("prefer") or []), *(guidance.get("avoid") or [])]
    ranked: list[tuple[str, float]] = []
    for hook in hooks:
        text = (hook or "").strip()
        if not text:
            continue
        traits = traits_of(text)
        ranked.append(
            (text, round(sum(float(t["gap"]) * 100 for t in learned if t["trait"] in traits), 1))
        )
    return sorted(ranked, key=lambda pair: -pair[1])


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
