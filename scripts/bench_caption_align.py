"""Measure local whisper caption timing against ElevenLabs ground truth.

`core/caption_align.py` only matters if its word timings are close enough to trust for
burned captions. ElevenLabs already writes a `<audio>.words.json` sidecar next to the
mp3s it synthesized, which gives us real per-word timings for real channel audio — so
accuracy can be measured rather than asserted.

    py -m scripts.bench_caption_align                        # auto-pick an audio file
    py -m scripts.bench_caption_align --models tiny,base,small
    py -m scripts.bench_caption_align --audio path/to.mp3

What matters is **line-start error**, not per-word error: captions are grouped into
~5-word lines (`CAPTION_WORDS_PER_LINE`) and a line's start time is when it appears on
screen. A per-word wobble inside a line is invisible; a late line start is not.

A dev script, deliberately outside the test suite — it downloads models and reads real
audio (tests/CLAUDE.md: no network in tests).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from typing import Any


def find_ground_truth_audio() -> str | None:
    """An mp3 that has an ElevenLabs word sidecar beside it (newest first)."""
    sidecars = sorted(
        glob.glob(os.path.join("output", "**", "*.words.json"), recursive=True),
        key=os.path.getmtime,
        reverse=True,
    )
    for sidecar in sidecars:
        audio = sidecar[: -len(".words.json")]
        if os.path.exists(audio):
            return audio
    return None


def load_truth(audio_path: str) -> list[dict[str, Any]]:
    with open(audio_path + ".words.json", encoding="utf-8") as fh:
        words = json.load(fh)
    return [w for w in words if isinstance(w, dict) and w.get("word")]


def _norm(word: str) -> str:
    return "".join(ch for ch in str(word).lower() if ch.isalnum())


def align_sequences(truth: list[dict], got: list[dict]) -> list[tuple[dict, dict]]:
    """Pair up words by order using a simple LCS-style walk on normalised text.

    Whisper drops/merges the odd token, so a positional zip would report huge errors
    that are really just an offset. Matching on text keeps the comparison honest.
    """
    pairs: list[tuple[dict, dict]] = []
    i = j = 0
    while i < len(truth) and j < len(got):
        a, b = _norm(truth[i].get("word", "")), _norm(got[j].get("word", ""))
        if a == b:
            pairs.append((truth[i], got[j]))
            i += 1
            j += 1
            continue
        # Look a short way ahead on each side for a re-sync point.
        resync = None
        for lookahead in range(1, 5):
            if j + lookahead < len(got) and a == _norm(got[j + lookahead].get("word", "")):
                resync = ("got", lookahead)
                break
            if i + lookahead < len(truth) and b == _norm(truth[i + lookahead].get("word", "")):
                resync = ("truth", lookahead)
                break
        if resync is None:
            i += 1
            j += 1
        elif resync[0] == "got":
            j += resync[1]
        else:
            i += resync[1]
    return pairs


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def line_start_errors(pairs: list[tuple[dict, dict]], max_words: int) -> list[float]:
    """Absolute error of each caption LINE's start time — what the viewer actually sees.

    Grouped from the **matched pairs**, not from each side independently. Whisper
    punctuates differently from ElevenLabs, and `group_into_lines` breaks on sentence
    ends, so grouping the two transcripts separately compares line N of one against
    entirely different words in the other — that measures transcript divergence, not
    timing error (it reported ~4s when per-word error was ~40ms). Pairing first means
    both sides always describe the same words.
    """
    from video.caption_timing import group_into_lines

    truth_words = [t for t, _ in pairs]
    lines = group_into_lines(truth_words, max_words)
    by_index = {id(t): g for t, g in pairs}
    errors: list[float] = []
    for line in lines:
        for word in line:  # first word in the line that has both timings
            counterpart = by_index.get(id(word))
            if counterpart is None:
                continue
            t_start, g_start = word.get("start"), counterpart.get("start")
            if t_start is not None and g_start is not None:
                errors.append(abs(float(t_start) - float(g_start)))
                break
    return errors


def bench_model(audio_path: str, truth: list[dict], model: str, max_words: int) -> dict[str, Any]:
    from core import caption_align

    os.environ["CAPTION_ALIGN_MODEL"] = model
    started = time.perf_counter()
    result = caption_align.transcribe_and_align(audio_path)
    elapsed = time.perf_counter() - started

    if not result.ok or not isinstance(result.data, list):
        return {"model": model, "ok": False, "detail": result.detail, "seconds": elapsed}

    got = result.data
    pairs = align_sequences(truth, got)
    word_errors = [
        abs(float(t["start"]) - float(g["start"]))
        for t, g in pairs
        if t.get("start") is not None and g.get("start") is not None
    ]
    line_errors = line_start_errors(pairs, max_words)
    return {
        "model": model,
        "ok": True,
        "seconds": elapsed,
        "truth_words": len(truth),
        "got_words": len(got),
        "matched": len(pairs),
        "word_p50": _percentile(word_errors, 50),
        "word_p90": _percentile(word_errors, 90),
        "line_p50": _percentile(line_errors, 50),
        "line_p90": _percentile(line_errors, 90),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Whisper caption timing vs ElevenLabs truth")
    parser.add_argument("--audio", default=None, help="mp3 with a .words.json sidecar")
    parser.add_argument("--models", default="tiny,base,small")
    parser.add_argument("--backend", default="faster_whisper")
    parser.add_argument("--max-words", type=int, default=5, help="caption words per line")
    args = parser.parse_args(argv)

    audio_path = args.audio or find_ground_truth_audio()
    if not audio_path or not os.path.exists(audio_path):
        print("No audio with an ElevenLabs .words.json sidecar found under output/.")
        return 1

    truth = load_truth(audio_path)
    if not truth:
        print(f"Sidecar for {audio_path} has no usable words.")
        return 1

    os.environ["CAPTION_ALIGN_BACKEND"] = args.backend
    from core.caption_align import align_compute_type, align_device

    device = align_device()
    duration = float(truth[-1].get("end") or 0.0)
    print(f"\n  audio   : {os.path.basename(audio_path)}")
    print(f"  duration: {duration:.1f}s   truth words: {len(truth)}")
    print(f"  backend : {args.backend} on {device} ({align_compute_type(device)})")
    print(f"  captions: {args.max_words} words/line\n")

    header = (
        f"  {'model':8} {'load+run':>9} {'x-real':>7} {'words':>7} "
        f"{'word p50':>9} {'word p90':>9} {'LINE p50':>9} {'LINE p90':>9}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    rows = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        row = bench_model(audio_path, truth, model, args.max_words)
        rows.append(row)
        if not row["ok"]:
            print(f"  {model:8} FAILED — {str(row.get('detail'))[:60]}")
            continue
        speed = (duration / row["seconds"]) if row["seconds"] else 0.0
        print(
            f"  {row['model']:8} {row['seconds']:8.1f}s {speed:6.1f}x "
            f"{row['got_words']:4}/{row['truth_words']:<3} "
            f"{row['word_p50'] * 1000:8.0f}ms {row['word_p90'] * 1000:8.0f}ms "
            f"{row['line_p50'] * 1000:8.0f}ms {row['line_p90'] * 1000:8.0f}ms"
        )

    good = [r for r in rows if r.get("ok") and r["line_p90"] <= 0.150]
    print()
    if good:
        best = min(good, key=lambda r: r["seconds"])
        print(
            f"  Recommended: CAPTION_ALIGN_MODEL={best['model']} "
            f"(line p90 {best['line_p90'] * 1000:.0f}ms, {best['seconds']:.1f}s for {duration:.0f}s audio)"
        )
    else:
        print("  No model met the 150ms line-start target — captions would visibly drift.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
