"""Re-derive WORDS_PER_SECOND from real rendered audio.

`core/script_length.WORDS_PER_SECOND` turns a word count into the duration estimate the
operator sees before deciding to render. It sat at 2.4 for months while real delivery was
~3.3, so run 66 was shown "243 words (~101s spoken)" and produced 70.2s — a 38% error
nobody caught, because nothing ever compared it to actual audio.

    py -m scripts.bench_script_duration

Measures every ElevenLabs `.words.json` sidecar under output/ (word count vs the last
word's end time) and prints the distribution plus the current constant's error. Re-run
after changing voice, model or stability settings — those change delivery speed.

A dev script, not part of the suite: it needs real rendered audio.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any


def _samples() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sidecar in sorted(glob.glob(os.path.join("output", "**", "*.words.json"), recursive=True)):
        try:
            with open(sidecar, encoding="utf-8") as fh:
                words = json.load(fh)
        except Exception:
            continue
        words = [w for w in words if isinstance(w, dict) and w.get("word")]
        if len(words) < 30:  # too short to be representative
            continue
        try:
            duration = float(words[-1].get("end") or 0.0)
        except (TypeError, ValueError):
            continue
        if duration <= 0:
            continue
        rows.append(
            {
                "words": len(words),
                "seconds": duration,
                "rate": len(words) / duration,
                "name": os.path.basename(sidecar)[:46],
            }
        )
    return rows


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure spoken words/sec from real renders")
    parser.add_argument("--verbose", action="store_true", help="list every sample")
    args = parser.parse_args(argv)

    rows = _samples()
    if not rows:
        print("No ElevenLabs .words.json sidecars found under output/ — render something first.")
        return 1

    from core.script_length import PRESETS, WORDS_PER_SECOND

    if args.verbose:
        print(f"\n  {'words':>6} {'secs':>7} {'w/sec':>7}  file")
        for row in rows:
            print(f"  {row['words']:6} {row['seconds']:7.1f} {row['rate']:7.2f}  {row['name']}")

    rates = [r["rate"] for r in rows]
    measured = _median(rates)
    print(f"\n  samples : {len(rates)} rendered script(s)")
    print(f"  measured: median {measured:.2f} w/s   (min {min(rates):.2f}, max {max(rates):.2f})")
    print(f"  current : WORDS_PER_SECOND = {WORDS_PER_SECOND}")

    drift = (measured / WORDS_PER_SECOND - 1) * 100 if WORDS_PER_SECOND else 0.0
    if abs(drift) < 5:
        print(f"  status  : OK — within {abs(drift):.0f}% of measured delivery.\n")
    else:
        direction = "understates" if drift > 0 else "overstates"
        print(f"  status  : DRIFTED — the constant {direction} speed by {abs(drift):.0f}%.")
        print(f"            Set WORDS_PER_SECOND = {measured:.1f} in core/script_length.py.\n")

    print("  Preset durations at the current constant (derived from the word ranges):")
    for preset in PRESETS.values():
        print(
            f"    {preset.label:9} {preset.min_words:5}-{preset.max_words:<5} words "
            f"-> {preset.duration_hint()}"
        )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
