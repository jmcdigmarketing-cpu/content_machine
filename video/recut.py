"""#1057 (wave 114, the operator: the best-held window, a draft that waits): re-cuts of past winners.

24 published videos carry YouTube's retention curve (100 points), and the best-held third kept
twice the viewers of the rest - but every moment that held was published once and never again.
A re-cut takes the 20-40 s of an older video that held most viewers *above the curve's own
trend* (so it does not just pick the opening, which every curve starts high on), snapped to whole
sentences, starting after the run's own intro, with the first sentence on screen for 2.5 s.

$0: no script, voice or render of new footage - one ffmpeg cut of the finished video. `--apply`
makes it and records it as a rendered run (`features.recut_of`); it is not uploaded - it waits in
the queue manager like any finished video, for the operator (decision 60).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

from core.logging import get_logger

logger = get_logger("video.recut")

MIN_SECONDS = 20.0
MAX_SECONDS = 40.0
CARD_SECONDS = 2.5
_END_MARGIN = 4.0  # the end card / last line
# Live 2026-10-19: against a straight-line trend the opening won on 2 of 3 videos (every curve
# falls steeply first), so the re-cut was the original's own first 20 s. A re-cut is a later
# moment: it starts after the first fifth, and is scored against the channel's average curve.
OPENING_SHARE = 0.2
_SIZE = (1080, 1920)


def residuals(
    curve: list[list[float]], baseline: list[tuple[float, float]] | None = None
) -> list[tuple[float, float]]:
    """(fraction, retention minus the expected) for each point - the expected is the channel's
    average curve at that point when given (what a video usually holds there), else the
    curve's own least-squares line."""
    points = [(float(p[0]), float(p[1])) for p in curve or [] if len(p) >= 2]
    if len(points) < 3:
        return []
    if baseline:
        return [(x, y - min(baseline, key=lambda b: abs(b[0] - x))[1]) for x, y in points]
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    var = sum((x - mx) ** 2 for x, _ in points)
    slope = sum((x - mx) * (y - my) for x, y in points) / var if var else 0.0
    return [(x, y - (my + slope * (x - mx))) for x, y in points]


def best_window(
    curve: list[list[float]],
    duration: float,
    *,
    start_after: float = 0.0,
    min_s: float = MIN_SECONDS,
    max_s: float = MAX_SECONDS,
    baseline: list[tuple[float, float]] | None = None,
) -> tuple[float, float] | None:
    """(start, end) in seconds of the span of `min_s`-`max_s` with the most retention above the
    curve's trend, starting after `start_after` and ending before the last few seconds."""
    res = residuals(curve, baseline)
    if not res or duration <= 0:
        return None
    end_limit = duration - _END_MARGIN
    timed = [(x * duration, r) for x, r in res]
    best: tuple[float, float, float] | None = None
    for i, (t0, _r0) in enumerate(timed):
        if t0 < start_after:
            continue
        total = 0.0
        for t1, r1 in timed[i:]:
            if t1 > end_limit or t1 - t0 > max_s:
                break
            total += r1
            if t1 - t0 >= min_s and (best is None or total > best[0]):
                best = (total, t0, t1)
    if best is None:
        return None
    return round(best[1], 2), round(best[2], 2)


def _sentences(words: list[dict], offset: float) -> list[tuple[float, float, str]]:
    """(start, end, text) of each sentence, in video seconds (the audio starts after `offset`)."""
    out: list[tuple[float, float, str]] = []
    current: list[dict] = []
    for word in words or []:
        current.append(word)
        if str(word.get("word") or "").strip().endswith((".", "!", "?")):
            out.append(_sentence(current, offset))
            current = []
    if current:
        out.append(_sentence(current, offset))
    return out


def _sentence(words: list[dict], offset: float) -> tuple[float, float, str]:
    text = " ".join(str(w.get("word") or "").strip() for w in words).strip()
    return (round(float(words[0].get("start") or 0) + offset, 2),
            round(float(words[-1].get("end") or 0) + offset, 2), re.sub(r"\s+", " ", text))  # fmt: skip


def snap(
    window: tuple[float, float], words: list[dict], offset: float, *, max_s: float = MAX_SECONDS
) -> tuple[float, float, str] | None:
    """The window moved to whole sentences: it starts on the sentence it starts in (or the next
    one) and ends on the sentence end nearest its own end, within `MIN_SECONDS`-`max_s`.
    Returns (start, end, first sentence) or None when no such span exists."""
    sentences = _sentences(words, offset)
    if not sentences:
        return None
    start_at, end_at = window
    first = next((i for i, s in enumerate(sentences) if s[1] > start_at), None)
    if first is None:
        return None
    start = sentences[first][0]
    ends = [s[1] for s in sentences[first:] if MIN_SECONDS <= s[1] - start <= max_s]
    if not ends:
        return None
    end = min(ends, key=lambda e: abs(e - end_at))
    return round(start, 2), round(end + 0.3, 2), sentences[first][2]


def draw_card(text: str, dest: str) -> str:
    """A transparent 1080x1920 frame with the sentence in a dark box in the top safe area."""
    from PIL import Image, ImageDraw

    from assets.thumbnail_compose import _font

    img = Image.new("RGBA", _SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = 64
    font = _font(size)
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) > _SIZE[0] - 160 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    lines = lines[:4]
    top = 300
    height = 40 + 82 * len(lines)
    draw.rounded_rectangle(
        [(50, top), (_SIZE[0] - 50, top + height)], radius=28, fill=(10, 12, 18, 215)
    )
    y = top + 24
    for text_line in lines:
        width = draw.textlength(text_line, font=font)
        draw.text(((_SIZE[0] - width) / 2, y), text_line, font=font, fill=(255, 255, 255, 255))
        y += 82
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    img.save(dest)
    return dest


def recut_argv(src: str, dst: str, *, start: float, end: float, card: str) -> list[str]:
    """The span re-encoded from `start` (seek before the input, frame-accurate) with the card
    over its first CARD_SECONDS."""
    graph = f"[0:v][1:v]overlay=0:0:enable='between(t,0,{CARD_SECONDS})'[v]"
    return [
        "ffmpeg", "-nostdin", "-y", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", src,
        "-i", card, "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst,
    ]  # fmt: skip


def _already_recut(channel_id: str) -> set[int]:
    from storage.repositories.content_runs import get_content_run_repository

    done: set[int] = set()
    for run in get_content_run_repository().list_for_channel(channel_id):
        try:
            features = json.loads(getattr(run, "features_json", "") or "{}")
        except (TypeError, ValueError):
            continue
        source = (features.get("recut_of") or {}) if isinstance(features, dict) else {}
        if source.get("run_id"):
            done.add(int(source["run_id"]))
    return done


def _duration(path: str) -> float:
    from video.week_compile import _duration as probe

    return float(probe(path) or 0.0)


def candidates(channel_id: str) -> list[dict[str, Any]]:
    """The best-held third of the measured videos that can be re-cut: a retention curve, the
    render and its word timings on disk, not re-cut before. Best-held first."""
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded
    from video.hook_copy import hook_offset, run_opening
    from video.subtitles import load_word_timings

    rows = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id):
        if is_seeded(row) or str(getattr(row, "privacy_status", "") or "") != "public":
            continue
        try:
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}")
        except (TypeError, ValueError):
            continue
        if metrics.get("stayed_share") is None:
            continue
        rows.append((float(metrics["stayed_share"]), row, metrics))
    rows.sort(key=lambda item: -item[0])
    top = rows[: max(1, len(rows) // 3)]
    done = _already_recut(channel_id)
    repo = get_content_run_repository()
    from core.retention import average_curve

    baseline = average_curve(channel_id)
    out: list[dict[str, Any]] = []
    for stayed, row, metrics in top:
        run_id = int(row.content_run_id or 0)
        curve = metrics.get("retention_curve")
        if not run_id or run_id in done or not curve:
            continue
        run = repo.get(run_id)
        mp4 = str(getattr(run, "mp4_path", "") or "") if run else ""
        mp3 = str(getattr(run, "mp3_path", "") or "") if run else ""
        if not mp4 or not os.path.isfile(mp4) or not mp3 or not os.path.isfile(mp3):
            continue
        words = load_word_timings(mp3)
        if not words:
            continue
        out.append({"run": run, "stayed": stayed, "curve": curve, "words": words,
                    "offset": hook_offset(run_opening(run), channel_id), "baseline": baseline,
                    "video_id": str(row.youtube_video_id)})  # fmt: skip
    return out


def plan_recut(
    candidate: dict[str, Any], *, duration: float | None = None
) -> dict[str, Any] | None:
    """Where to cut one candidate and what it is called, or None when nothing fits."""
    run = candidate["run"]
    length = duration if duration is not None else _duration(str(run.mp4_path))
    after = max(candidate["offset"] + 0.5, OPENING_SHARE * length)
    window = best_window(candidate["curve"], length, start_after=after,
                         baseline=candidate.get("baseline"))  # fmt: skip
    if window is None:
        return None
    snapped = snap((max(window[0], after), window[1]), candidate["words"], candidate["offset"])
    if snapped is None:
        return None
    start, end, sentence = snapped
    return {"run_id": int(run.id), "start": start, "end": end, "sentence": sentence,
            "title": recut_title(sentence, str(getattr(run, "title", "") or "")),
            "stayed": candidate["stayed"], "video_id": candidate["video_id"]}  # fmt: skip


def recut_title(sentence: str, original: str) -> str:
    """The first sentence as the title when it reads as one - else the original's, marked."""
    from core.authenticity import ad_limit_reason
    from core.title_generator import broken_place_name, title_cut_off

    text = sentence.strip().rstrip(".")
    if 20 <= len(text) <= 90 and not ad_limit_reason(text, "") and not broken_place_name(text) \
            and not title_cut_off(text):  # fmt: skip
        return text
    suffix = " - the moment that held"
    base = original.strip()
    if len(base) > 100 - len(suffix):  # YouTube's 100; cut at a whole word ("Manife" was cut)
        base = base[: 100 - len(suffix)].rsplit(" ", 1)[0]
    base = base.rstrip(" -:,")
    return f"{base}{suffix}" if base else text[:90]


def make_recut(
    channel_id: str, plan: dict[str, Any], *, run: Any = subprocess.run
) -> tuple[int, str]:
    """Cut it and record it as a rendered run. (run id, the file) - (0, why) when it failed."""
    from core.run_recorder import record_content_run
    from storage.repositories.content_runs import get_content_run_repository

    source = get_content_run_repository().get(int(plan["run_id"]))
    src = str(getattr(source, "mp4_path", "") or "")
    stem, ext = os.path.splitext(src)
    dst = f"{stem}.recut{ext or '.mp4'}"
    card = draw_card(plan["sentence"], f"{stem}.recut_card.png")
    done = run(recut_argv(src, dst, start=plan["start"], end=plan["end"], card=card),
               capture_output=True, stdin=subprocess.DEVNULL, timeout=600, check=False)  # fmt: skip
    if getattr(done, "returncode", 1) != 0 or not os.path.isfile(dst):
        return 0, f"ffmpeg exit {getattr(done, 'returncode', '?')}"
    original = str(getattr(source, "title", "") or "")
    description = (f"From \"{original}\" - the part viewers stayed for.\n\n"
                   + str(getattr(source, "description", "") or ""))  # fmt: skip
    run_id = record_content_run(
        channel_id=channel_id,
        input_topic=str(getattr(source, "input_topic", "") or plan["title"]),
        selected_topic=plan["title"],
        status="rendered",
        composite_score=0.0,
        signals={},
        variants=[],
        title=plan["title"],
        description=description,
        tags_json=str(getattr(source, "tags_json", "") or "[]"),
        mp4_path=dst,
        features={
            "recut_of": {
                "run_id": plan["run_id"],
                "video_id": plan["video_id"],
                "start": plan["start"],
                "end": plan["end"],
                "stayed": plan["stayed"],
            }
        },
    )
    return int(run_id or 0), dst


def recut_lines(channel_id: str, *, apply: bool = False, run_id: int = 0) -> list[str]:
    """What `ops recut` prints: the candidates and their windows; with `apply`, one is made."""
    found = candidates(channel_id)
    if run_id:
        found = [c for c in found if int(c["run"].id) == int(run_id)]
    if not found:
        return ["  Re-cuts: no video qualifies (the best-held third, with its curve, render and "
                "word timings on disk, not re-cut before)."]  # fmt: skip
    lines = [f"  Re-cuts - {channel_id}: the best-held third, best first"]
    planned: list[dict[str, Any]] = []
    for candidate in found:
        plan = plan_recut(candidate)
        run = candidate["run"]
        if plan is None:
            lines.append(
                f"    run {run.id} ({candidate['stayed']:.0%} stayed): no 20-40 s span fits"
            )
            continue
        planned.append(plan)
        lines.append(f"    run {run.id} ({plan['stayed']:.0%} stayed): {plan['start']:.1f}-{plan['end']:.1f} s"
                     f" - \"{plan['title']}\"")  # fmt: skip
    if not apply:
        lines.append("  Dry run. py -m scripts.ops recut --channel tapin --apply makes the first "
                     "(--run-id N for another); it waits in the queue manager, not uploaded.")  # fmt: skip
        return lines
    if not planned:
        return lines
    made, where = make_recut(channel_id, planned[0])
    if made:
        lines.append(f"  Made: run {made} from run {planned[0]['run_id']} - {where}. It waits for you: "
                     "py main.py -> 2 (queue manager).")  # fmt: skip
    else:
        lines.append(f"  ! Not made: {where}")
    return lines
