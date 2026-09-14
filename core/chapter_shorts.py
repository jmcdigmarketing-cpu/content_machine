"""Cut an all-angles long video's chapters into Shorts (run 78).

Every chapter of an all-angles video opens on its own hook, so a chapter cut straight out
of the rendered long video is a Short with no extra voice cost. Renders are already
vertical 1080x1920 with burned captions; a chapter only needs to fit YouTube's 3-minute
Shorts limit. Each cut is recorded as its own rendered content run, so it queues and
uploads like any other video.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any

from core.angle_chapters import AngleChapter, chapters_from_features, token_start_times
from core.logging import get_logger
from core.run_recorder import record_content_run
from storage.repositories.content_runs import get_content_run_repository
from video.subtitles import load_word_timings

logger = get_logger("core.chapter_shorts")

SHORTS_MAX_SECONDS = 180.0
_LEAD_PAD = 0.12
_TAIL_TRIM = 0.05
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ChapterSpan:
    index: int
    title: str
    angle: str
    start: float
    end: float
    text: str

    @property
    def seconds(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def fits_shorts(self) -> bool:
        return 0.0 < self.seconds <= SHORTS_MAX_SECONDS


@dataclass
class ChapterShort:
    index: int
    title: str
    run_id: int | None
    mp4_path: str
    skipped: str = ""


def _intro_offset(channel_id: str | None) -> float:
    from scripts.probe_sync import intro_offset_seconds

    return intro_offset_seconds(channel_id)


def _probe_duration(path: str) -> float | None:
    from video.channel_intro import _probe_duration as probe

    return probe(path)


def chapter_spans(
    script: str,
    chapters: list[AngleChapter],
    *,
    word_timings: list[dict[str, Any]] | None,
    intro_offset: float,
    audio_duration: float,
) -> list[ChapterSpan]:
    """Where each chapter sits in the final video (after the channel intro)."""
    text = script or ""
    positions = [m.start() for m in _WORD_RE.finditer(text)]
    total = len(positions)
    times = token_start_times(word_timings)

    def _time_at(word: int) -> float:
        if word < len(times):
            return times[word]
        return float(audio_duration) * word / max(1, total)

    def _char_at(word: int) -> int:
        return positions[word] if word < total else len(text)

    spans: list[ChapterSpan] = []
    for k, chapter in enumerate(chapters):
        nxt = chapters[k + 1].word_start if k + 1 < len(chapters) else None
        start = (
            0.0 if chapter.word_start <= 0 else max(0.0, _time_at(chapter.word_start) - _LEAD_PAD)
        )
        end = float(audio_duration) if nxt is None else max(start, _time_at(nxt) - _TAIL_TRIM)
        body = text[_char_at(chapter.word_start) : _char_at(nxt) if nxt is not None else len(text)]
        spans.append(
            ChapterSpan(
                index=chapter.index,
                title=chapter.title,
                angle=chapter.angle,
                start=round(intro_offset + start, 3),
                end=round(intro_offset + end, 3),
                text=body.strip(),
            )
        )
    return spans


def parse_chapter_selection(text: str, count: int) -> list[int]:
    """ "" / "all" -> every chapter; "1,3,5" -> [0, 2, 4]; out-of-range entries dropped."""
    raw = (text or "").strip().lower()
    if raw in ("", "all", "a"):
        return list(range(count))
    out: list[int] = []
    for part in re.split(r"[,\s]+", raw):
        if part.isdigit() and 1 <= int(part) <= count and int(part) - 1 not in out:
            out.append(int(part) - 1)
    return out


def _short_description(span: ChapterSpan, channel_id: str, parent_title: str) -> str:
    lead = " ".join(" ".join(_SENTENCE_RE.split(span.text)[:2]).split()[:45]).strip()
    body = f"{lead}\n\nFrom the full video: {parent_title}".strip()
    try:
        from core.description_extras import apply_description_extras

        return apply_description_extras(
            body, channel_id, title=span.title, topic=span.title, length_choice="2"
        )
    except Exception as exc:
        logger.debug("short description extras skipped: %s", exc)
        return body


def cut_chapter_shorts(
    run_id: int,
    *,
    indices: list[int] | None = None,
    script: str | None = None,
) -> list[ChapterShort]:
    """Cut the chosen chapters of a rendered all-angles run into Shorts. Never raises."""
    record = get_content_run_repository().get(int(run_id))
    if record is None:
        return []
    try:
        features = json.loads(record.features_json or "{}")
    except (TypeError, ValueError):
        features = {}
    chapters = chapters_from_features(features.get("angle_chapters"))
    source = str(record.mp4_path or "")
    words = load_word_timings(record.mp3_path) or []
    # script_preview is capped at 2,000 chars, so a re-cut by run id would lose every
    # later chapter's text. The TTS word sidecar is the full spoken script.
    spoken = " ".join(str(w.get("word") or "") for w in words if isinstance(w, dict)).strip()
    text = script if script is not None else (spoken or str(record.script_preview or ""))
    if not chapters or not source or not os.path.isfile(source) or not text.strip():
        return []

    last_word_end = max(
        (
            float(w["end"])
            for w in words
            if isinstance(w, dict) and isinstance(w.get("end"), int | float)
        ),
        default=0.0,
    )
    audio_duration = _probe_duration(record.mp3_path) or last_word_end
    spans = chapter_spans(
        text,
        chapters,
        word_timings=words,
        intro_offset=_intro_offset(record.channel_id),
        audio_duration=float(audio_duration or 0.0),
    )
    try:
        tags = json.loads(record.tags_json or "[]")
    except (TypeError, ValueError):
        tags = []
    stem = os.path.splitext(os.path.basename(source))[0][:60]
    wanted = indices if indices is not None else list(range(len(spans)))

    made: list[ChapterShort] = []
    for i in wanted:
        if not 0 <= i < len(spans):
            continue
        span = spans[i]
        if not span.fits_shorts:
            made.append(
                ChapterShort(
                    i,
                    span.title,
                    None,
                    "",
                    f"{span.seconds:.0f}s is over the 3-minute Shorts limit",
                )
            )
            continue
        dest = os.path.join(os.path.dirname(source), f"{stem}_short{i + 1}.mp4")
        argv = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{span.start:.3f}", "-i", source, "-t", f"{span.seconds:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            dest,
        ]  # fmt: skip
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=900)
            failed = proc.returncode != 0 or not os.path.isfile(dest)
            reason = (proc.stderr or "").strip()[-200:] if failed else ""
        except Exception as exc:
            failed, reason = True, str(exc)
        if failed:
            made.append(ChapterShort(i, span.title, None, "", f"ffmpeg failed: {reason}"))
            continue
        short_run = record_content_run(
            channel_id=record.channel_id,
            input_topic=record.input_topic,
            selected_topic=span.angle,
            status="rendered",
            composite_score=float(record.composite_score or 0.0),
            signals={},
            variants=[],
            title=span.title[:100],
            description=_short_description(span, record.channel_id, record.title or ""),
            tags_json=json.dumps(tags),
            script=span.text,
            mp4_path=dest,
            features={
                "parent_run_id": int(record.id),
                "chapter_index": i,
                "short_source": "chapter_cut",
                "length_preset": "2",
                "clip_start": span.start,
                "clip_seconds": round(span.seconds, 3),
            },
        )
        made.append(ChapterShort(i, span.title, short_run, dest))
    return made
