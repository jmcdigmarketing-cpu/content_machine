"""Measure A/V sync in a rendered mp4 so the intro offset stops getting relearned.

Candidate 44. The failure this exists to prevent, in full:

A finished render *looks* out of sync with its own SRT. `output/video/temp_subtitles.srt`
says the third cue starts at 3.220s; the burned frame at 4.2s is still showing cue 2.
The natural conclusion — "the caption pipeline is drifting" — is wrong. `prepend_channel_intro`
runs **after** ffmpeg and pushes both audio and burned subtitles later by the intro's
length (TapIn's sting is 2.15s, ~2.167s once re-encoded to 30fps). Subtract it and the
sync is exact.

Two traps cost real time on the way to that answer, so they are handled here:

  * **`ffmpeg -ss` before `-i` is input-seek** and reported the wrong frame for this
    check. Output-seek (`-i` then `-ss`) agreed with reality. This script uses
    output-seek.
  * **`silencedetect` on a file whose audio starts silent** reports `silence_start: 0`;
    that leading run *is* the intro, not a defect.

    py -m scripts.probe_sync                          # newest mp4 under output/
    py -m scripts.probe_sync --video path/to.mp4
    py -m scripts.probe_sync --video x.mp4 --srt output/video/temp_subtitles.srt

A dev script, deliberately outside the test suite: it shells out to ffprobe/ffmpeg and
reads real renders (tests/CLAUDE.md — no network, no ffmpeg, in tests). The pure helpers
(`parse_srt_first_cue`, `intro_offset_seconds`, `verdict`) are importable and unit-tested.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess

_TIMECODE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)
_SILENCE_END = re.compile(r"silence_end:\s*([\d.]+)")
_SILENCE_START = re.compile(r"silence_start:\s*([\d.]+)")

# Anything under this is codec padding, not an intro.
_MIN_INTRO_SECONDS = 0.25


def _run(cmd: list[str], timeout: int = 60) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (out.stdout or "") + (out.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return f"__ERROR__ {exc}"


def newest_render(root: str = "output") -> str | None:
    """Newest mp4 under output/, skipping the intro asset itself."""
    files = [
        p
        for p in glob.glob(os.path.join(root, "**", "*.mp4"), recursive=True)
        if "intro" not in os.path.basename(p).lower()
    ]
    return max(files, key=os.path.getmtime) if files else None


def parse_srt_first_cue(srt_text: str) -> float | None:
    """Start time (seconds) of the first cue, or None when the file has no timecode."""
    m = _TIMECODE.search(srt_text or "")
    if not m:
        return None
    h, mi, s, ms = (int(g) for g in m.groups()[:4])
    return h * 3600 + mi * 60 + s + ms / 1000.0


def leading_silence(video_path: str) -> float | None:
    """Seconds of silence at the head of the file, or None if it does not start silent.

    A render with a channel intro starts with the sting's (usually silent) audio, so this
    is the intro length rather than a fault.
    """
    text = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            video_path,
            "-t",
            "30",
            "-af",
            "silencedetect=n=-40dB:d=0.2",
            "-f",
            "null",
            "-",
        ]
    )
    if text.startswith("__ERROR__"):
        return None
    starts = _SILENCE_START.findall(text)
    if not starts or float(starts[0]) > 0.05:
        return None  # does not begin silent -> no leading pad
    ends = _SILENCE_END.findall(text)
    return float(ends[0]) if ends else None


def intro_offset_seconds(channel_id: str | None = None) -> float:
    """Configured intro length, or 0.0 when no intro is configured for the channel."""
    try:
        from video.channel_intro import _probe_duration, resolve_intro_path

        path = resolve_intro_path(channel_id)
        if not path:
            return 0.0
        return float(_probe_duration(path) or 0.0)
    except Exception:
        return 0.0


def verdict(first_cue: float | None, silence: float | None, intro: float) -> str:
    """Explain the gap between the SRT and the burned video in one sentence."""
    if first_cue is None:
        return "No timecode in the SRT - nothing to compare."
    pad = silence or 0.0
    if pad < _MIN_INTRO_SECONDS:
        return (
            f"No leading pad ({pad:.2f}s). Captions should appear at their SRT times; "
            f"first cue {first_cue:.2f}s."
        )
    if intro and abs(pad - intro) <= 0.35:
        return (
            f"Leading pad {pad:.2f}s matches the {intro:.2f}s channel intro. "
            f"IN SYNC: subtract the intro - cue 1 lands at {first_cue + pad:.2f}s in the "
            f"file, not {first_cue:.2f}s. prepend_channel_intro runs after ffmpeg."
        )
    return (
        f"Leading pad {pad:.2f}s does NOT match the configured intro ({intro:.2f}s). "
        "Investigate: this is the case where captions are genuinely adrift."
    )


def grab_frame(video_path: str, at_seconds: float, out_path: str) -> bool:
    """Extract one frame using OUTPUT seek (`-i` then `-ss`).

    Input-seek (`-ss` before `-i`) reported the wrong frame while diagnosing this exact
    problem; output-seek agreed with the burned pixels. Slower, correct.
    """
    text = _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-ss",
            f"{at_seconds:.3f}",
            "-frames:v",
            "1",
            out_path,
        ],
        timeout=120,
    )
    return not text.startswith("__ERROR__") and os.path.isfile(out_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A/V + caption sync probe for a rendered mp4")
    ap.add_argument("--video", default=None, help="mp4 to probe (default: newest under output/)")
    ap.add_argument("--srt", default=os.path.join("output", "video", "temp_subtitles.srt"))
    ap.add_argument("--channel", default=None, help="channel id for the intro lookup")
    ap.add_argument("--frame", default="", help="also write the first-cue frame here (png)")
    args = ap.parse_args(argv)

    video = args.video or newest_render()
    if not video or not os.path.isfile(video):
        print("No mp4 found. Render one, or pass --video.")
        return 1

    srt_text = ""
    if os.path.isfile(args.srt):
        with open(args.srt, encoding="utf-8", errors="replace") as fh:
            srt_text = fh.read()
    first_cue = parse_srt_first_cue(srt_text)
    silence = leading_silence(video)
    intro = intro_offset_seconds(args.channel)

    print(f"\n  video      : {video}")
    print(f"  srt        : {args.srt}{'' if srt_text else '  (missing)'}")
    print(f"  first cue  : {'n/a' if first_cue is None else f'{first_cue:.3f}s'}")
    print(f"  leading pad: {'none' if silence is None else f'{silence:.3f}s'}")
    print(f"  intro      : {intro:.3f}s" if intro else "  intro      : none configured")
    print(f"\n  {verdict(first_cue, silence, intro)}\n")

    if args.frame and first_cue is not None:
        at = first_cue + (silence or 0.0)
        ok = grab_frame(video, at, args.frame)
        print(f"  frame @{at:.2f}s -> {args.frame}" if ok else "  frame grab failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
