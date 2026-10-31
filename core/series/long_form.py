"""The GTA 6 window's long videos (#1850, decision 84): 10-12 minutes, 16:9, after review.

A long draft is written with the Extended preset and chapters from its angles
(`batch_generation.generate_draft`); its title carries what people search (`search_title`,
#1856); it renders only once the operator accepts it, with the landscape profile, and the run then
points at the `_16x9` file with its own thumbnail (`finish_long_render`, #1731 + #1869: a frame of
our own render, three title words, the subject's palette - no outside image).
"""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
from collections.abc import Iterator
from typing import Any

from core.logging import get_logger
from core.series.countdown import series_rows

logger = get_logger("core.series.long_form")

_TITLE_LIMIT = 100
WIDE_SUFFIX = "_16x9"  # video/render_profiles' landscape suffix


def search_title(
    subject: str,
    suggestions: list[str] | None,
    title: str,
    *,
    terms: list[str] | None = None,
    limit: int = _TITLE_LIMIT,
) -> str:
    """#1856: "GTA 6 Release Date: <the title>" - the subject first and a YouTube suggestion's own
    words in it; the title unchanged with no suggestion. With `terms` (the row's
    `search_terms`), only a suggestion carrying one counts - live, the subject's own top
    suggestions were "trailer", "gameplay" and "leak", which no long video here is."""
    title = " ".join(str(title or "").split())
    subject = " ".join(str(subject or "").split())
    if not subject or not suggestions:
        return title
    lead = subject.lower().split()
    phrase = ""
    for suggestion in suggestions:
        words = str(suggestion or "").lower().split()
        rest = (
            words[len(lead) :]
            if words[: len(lead)] == lead
            else [w for w in words if w not in lead]
        )
        wanted = [str(t).lower().split() for t in terms or [] if str(t).strip()]
        if rest and (not wanted or any(all(w in rest for w in t) for t in wanted)):
            phrase = " ".join(rest)
            break
    if not phrase:
        return title
    if title.lower().startswith(subject.lower()) and phrase in title.lower():
        return title
    # only "GTA 6: ..." or "GTA 6 - ..." loses its subject; "GTA 6's map" keeps it (live, 10-28)
    body = re.sub(rf"^{re.escape(subject)}\s*[:,-]\s*", "", title, flags=re.IGNORECASE).strip()
    head = f"{subject} {phrase.title()}"
    if not body or phrase in body.lower():
        joined = f"{subject}: {body}" if body else head
    else:
        joined = f"{head}: {body}"
    return joined if len(joined) <= limit else head


def long_title(channel_id: str, topic: str, title: str) -> tuple[str, list[str] | None]:
    """The long draft's title from search, and the suggestions it read (None when unread)."""
    row = next((r for r in series_rows(channel_id)
                if r.get("kind") == "long" and r.get("topic") == topic), None)  # fmt: skip
    subject = str((row or {}).get("subject") or "").strip()
    if not subject:
        return title, None
    terms = [str(t) for t in (row or {}).get("search_terms") or [] if str(t).strip()]
    try:
        from apis.autocomplete_api import youtube_suggestions

        # The subject's own list is generic; "GTA 6 map" gives "gta 6 map size", "... leak".
        suggestions: list[str] | None = None
        for query in [f"{subject} {t}" for t in terms[:3]] or [subject]:
            got = youtube_suggestions(query)
            if got is not None:
                suggestions = [
                    *(suggestions or []),
                    *(g for g in got if g not in (suggestions or [])),
                ]
    except Exception as exc:
        logger.debug("long-form suggestions unread: %s", exc)
        suggestions = None
    return search_title(subject, suggestions, title, terms=terms or None), suggestions


def three_words(title: str) -> str:
    """At most three of the title's first phrase's words (#1731)."""
    from assets.thumbnail_compose import headline_words

    return " ".join((headline_words(title) or [])[:3])


def style_palette(channel_id: str, title: str) -> list[str]:
    """The `style` row's colours for a title naming its subject (GTA 6's cover art), else []."""
    from apis.topic_tokens import names_any

    for row in series_rows(channel_id):
        names = [str(n) for n in row.get("names") or [] if str(n).strip()]
        if row.get("kind") == "style" and names_any(title or "", names):
            return [str(c) for c in row.get("palette") or []]
    return []


def _hex(color: str) -> tuple[int, int, int] | None:
    raw = str(color or "").lstrip("#")
    if len(raw) != 6:
        return None
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return None


def _duration(path: str) -> float | None:
    from video.channel_intro import _probe_duration

    return _probe_duration(path)


def _frame(video: str, at: float, dest: str) -> str:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-ss", f"{at:.1f}", "-i", video, "-frames:v", "1",
         "-vf", "scale=1280:720", dest],
        capture_output=True, stdin=subprocess.DEVNULL, timeout=120, check=False,
    )  # fmt: skip
    return dest if os.path.isfile(dest) else ""


def long_thumbnail(
    video: str, title: str, dest: str, *, channel_id: str, palette: list[str] | None = None
) -> str:
    """#1731 + #1869: a 1280x720 card - a frame 30% into our own 16:9 render, three title words
    in the palette's first colour (`compose_thumbnail`'s contrast rule backs or refuses it).
    "" when no card was made."""
    length = _duration(video) or 0.0
    frame = _frame(video, max(1.0, 0.3 * length), os.path.splitext(dest)[0] + "_frame.png")
    if not frame:
        return ""
    try:
        from PIL import Image

        from assets.thumbnail_compose import compose_thumbnail

        if not title:  # L9's "none" arm: the frame alone, no words
            Image.open(frame).convert("RGB").resize((1280, 720)).save(dest)
            return dest if os.path.isfile(dest) else ""
        ink = next((c for c in (_hex(p) for p in palette or []) if c), None)
        plate = compose_thumbnail(
            Image.open(frame).convert("RGB"), three_words(title) or title, dest,
            channel_id=channel_id, ink=ink,
        )  # fmt: skip
    except Exception as exc:
        logger.warning("long-form thumbnail skipped: %s", exc)
        return ""
    return plate.path if plate.path and os.path.isfile(plate.path) else ""


def cover_arm(channel_id: str, run_id: int) -> str:
    """L9 (wave 135): "words" or "none" for this long video's cover - the `long_cover`
    experiment's next arm, started when the first long video renders; recorded on the run."""
    try:
        from core.experiments import (
            active_experiment,
            next_arm,
            record_assignment,
            start_experiment,
        )

        if active_experiment(channel_id, "long_cover") is None:
            start_experiment(channel_id, "long_cover", days=60)  # long videos come a few a month
        picked = next_arm(channel_id, kind="long_cover")
        if picked is None:
            return "words"
        record_assignment(channel_id, run_id, picked[0], picked[1])
        return picked[1]
    except Exception as exc:
        logger.debug("long cover arm unread: %s", exc)
        return "words"


@contextlib.contextmanager
def landscape_render() -> Iterator[None]:
    """RENDER_FORMATS=landscape for one render, restored after (video/render_profiles)."""
    before = os.environ.get("RENDER_FORMATS")
    os.environ["RENDER_FORMATS"] = "landscape"
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("RENDER_FORMATS", None)
        else:
            os.environ["RENDER_FORMATS"] = before


def finish_long_render(run_id: int, channel_id: str, title: str) -> str:
    """Point the run at its `_16x9` render and give it the long card. The path, or "" when the
    wide file was not written (the run keeps its primary render and says so in the log)."""
    from storage.repositories.content_runs import get_content_run_repository

    run: Any = get_content_run_repository().get(int(run_id))
    primary = str(getattr(run, "mp4_path", "") or "")
    stem, ext = os.path.splitext(primary)
    wide = f"{stem}{WIDE_SUFFIX}{ext or '.mp4'}"
    if not primary or not os.path.isfile(wide):
        logger.warning("long render: no %s file for run %s", WIDE_SUFFIX, run_id)
        return ""
    from core.run_recorder import update_content_run_media

    update_content_run_media(
        int(run_id), mp3_path=str(getattr(run, "mp3_path", "") or ""), mp4_path=wide
    )
    arm = cover_arm(channel_id, int(run_id))  # L9: three words against none
    thumb = long_thumbnail(wide, title if arm == "words" else "", f"{stem}{WIDE_SUFFIX}_thumb.png",
                           channel_id=channel_id, palette=style_palette(channel_id, title))  # fmt: skip
    from core.run_features import merge_features

    # the hours ledger (#1728) counts the runs marked long_form
    merge_features(int(run_id), {"long_form": True})
    if thumb:
        merge_features(int(run_id), {"thumbnail_pick": {"path": thumb, "arm": "long"}})
    return wide
