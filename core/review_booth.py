"""Last-run review booth + thumbnail lightbox + thin-facts abort screen.

Localhost HTML over the last render (play / grade / authenticity / cost /
Approve). Not FastAPI, not the full review room. Stdlib only.
"""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote

from core.html_report import (
    escape,
    html_dir,
    open_html_enabled,
    open_local,
    themed_page,
    write_html,
)
from core.logging import get_logger

logger = get_logger("core.review_booth")


def last_trace(channel_id: str | None = None) -> dict[str, Any] | None:
    try:
        from core.run_trace import list_traces

        traces = list_traces(limit=20, channel_id=channel_id)
    except Exception as exc:
        logger.debug("list_traces skipped: %s", exc)
        return None
    for t in traces:
        if (t.get("status") or "") in ("rendered", "drafted"):
            return t
    return traces[0] if traces else None


def _run_label(run_id: Any) -> str:
    if run_id is None or run_id == "":
        return "(last render)"
    try:
        return f"#{int(run_id)}"
    except (TypeError, ValueError):
        return f"#{run_id}"


def _file_uri(path: str) -> str:
    abs_path = os.path.abspath(path).replace("\\", "/")
    if not abs_path.startswith("/"):
        abs_path = "/" + abs_path
    return "file://" + quote(abs_path, safe="/:")


def lightbox_html(thumb_path: str | None) -> str:
    if not thumb_path or not os.path.isfile(thumb_path):
        body = (
            "<p>No thumbnail on disk. Pillow-first thumbs live in output/{channel}/thumbnails/.</p>"
        )
        return themed_page("Thumbnail lightbox", body, subtitle="last Pillow thumb")
    uri = _file_uri(thumb_path)
    body = (
        f"<p>{escape(thumb_path)}</p>"
        f"<img class='thumb' src='{escape(uri)}' alt='last thumbnail' "
        "onclick=\"document.getElementById('lb').showModal()\">"
        f"<dialog id='lb' onclick='this.close()'><img src='{escape(uri)}' alt='full'></dialog>"
    )
    return themed_page("Thumbnail lightbox", body, subtitle="click to zoom")


def thin_facts_html(reason: str, *, fact_count: int | None = None) -> str:
    extra = f"<p>Verified fact lines: {int(fact_count)}</p>" if fact_count is not None else ""
    body = (
        "<div class='card'>"
        "<p class='fail'><strong>Thin-facts abort</strong> - TTS skipped so the "
        "$0.31 voice line is not burned.</p>"
        f"<p>{escape(reason)}</p>{extra}"
        "<p>The draft is saved. Add operator facts and re-run, or override in the CLI.</p>"
        "</div>"
    )
    return themed_page("Thin-facts abort", body, subtitle="gate already saved the TTS spend")


def tts_share_line(tts: Any, total: Any) -> str:
    """`tts $0.31 · 91% of this render` — the number that should stay on-screen."""
    try:
        tts_f = float(tts or 0)
        total_f = float(total or 0)
    except (TypeError, ValueError):
        return ""
    if total_f > 0:
        pct = 100.0 * tts_f / total_f
        return f"tts ${tts_f:.2f} · {pct:.0f}% of this render"
    if tts_f:
        return f"tts ${tts_f:.2f}"
    return ""


def title_meter_html(title: str) -> str:
    if not (title or "").strip():
        return ""
    count = len(title)
    over = max(0, count - 100)
    cls = "fail" if over else "ok"
    note = f" - over by {over}" if over else ""
    return (
        f"<p><strong>YouTube title</strong> {escape(title)}</p>"
        f"<p class='{cls}' role='meter' aria-valuenow='{count}' "
        f"aria-valuemin='0' aria-valuemax='100'>{count} / 100{note}</p>"
    )


def description_preview_html(description: str) -> str:
    first = next((line.strip() for line in (description or "").splitlines() if line.strip()), "")
    if not first:
        return ""
    return f"<p><strong>Description first line</strong> {escape(first)}</p>"


def duration_readout(actual_seconds: Any, word_count: Any) -> str:
    try:
        from core.script_length import WORDS_PER_SECOND

        estimated = float(word_count or 0) / WORDS_PER_SECOND
    except (TypeError, ValueError):
        estimated = 0.0
    try:
        actual = float(actual_seconds) if actual_seconds is not None else None
    except (TypeError, ValueError):
        actual = None
    spoken = f"{actual:.1f}s" if actual is not None else "not available"
    return f"Spoken {spoken} · estimated {estimated:.1f}s"


def _srt_to_vtt(srt_path: str, vtt_path: str) -> str:
    with open(srt_path, encoding="utf-8-sig") as source:
        lines = source.read().splitlines()
    converted: list[str] = []
    in_cue_text = False
    for line in lines:
        if "-->" in line:
            converted.append(line.replace(",", "."))
            in_cue_text = True
        elif not line.strip():
            converted.append("")
            in_cue_text = False
        elif in_cue_text:
            converted.append(escape(line))
        else:
            converted.append(line)
    with open(vtt_path, "w", encoding="utf-8") as dest:
        dest.write("WEBVTT\n\n" + "\n".join(converted).strip() + "\n")
    return vtt_path


def booth_markdown(
    *,
    grade: str = "",
    authenticity: str = "",
    cost: str = "",
    blocking: str = "",
    cost_share: str = "",
    run_id: int | None = None,
) -> str:
    """Copy-as-markdown payload for the report card (vault / chat)."""
    rid = _run_label(run_id)
    lines = [
        f"# Report card {grade or 'n/a'} ({rid})",
        "",
        f"- Authenticity: {authenticity or 'n/a'}",
        f"- Cost: {cost or 'n/a'}",
        f"- TTS share: {cost_share or 'n/a'}",
        f"- Blocking publish: {blocking or 'n/a'}",
    ]
    return "\n".join(lines)


def apify_pills_html() -> str:
    """Remaining paid Apify actors as pills. Never implies reddit/twitter still bill."""
    try:
        from apis.apify_catalog import remaining_enabled_actors

        names = remaining_enabled_actors()
    except Exception as exc:
        logger.debug("apify pills skipped: %s", exc)
        names = ["tiktok_trends", "youtube_competitors"]
    parts = [f"<span class='pill'>{escape(n)}</span>" for n in names]
    return "<p>Apify (still billing): " + "".join(parts) + "</p>" if parts else ""


def thin_facts_banner_html(blocking: str = "") -> str:
    if "thin" in (blocking or "").lower():
        return (
            "<p class='banner'>Thin-facts: TTS was skipped or the draft is under "
            "the fact bar. Add operator facts before burning the $0.31 voice line.</p>"
        )
    return ""


def escaped_llm_pill_html(trace: dict[str, Any] | None) -> str:
    calls = (trace or {}).get("llm_calls") or []
    hit = False
    for call in calls:
        if isinstance(call, dict) and call.get("escaped_free_first"):
            hit = True
            break
    if not hit:
        return ""
    return "<p class='redpill'>Escaped free-first LLM - this run landed on a paid slug.</p>"


def numeric_chips_html(spans: list[str] | None) -> str:
    if not spans:
        return ""
    chips = "".join(f"<span class='chip'>{escape(s)}</span>" for s in spans[:12])
    return "<p>Ungrounded numeric: " + chips + "</p>"


def semantic_bar_html(overlap: Any) -> str:
    try:
        val = float(overlap or 0)
    except (TypeError, ValueError):
        return ""
    pct = max(0, min(100, int(round(val * 100))))
    warn = pct >= 45
    cls = "fail" if warn else "ok"
    return (
        f"<p>Authenticity semantic overlap <span class='{cls}'>{pct}%</span> "
        "(warn at 45%)</p>"
        f"<div class='bar' role='meter' aria-valuenow='{pct}' aria-valuemin='0' "
        f"aria-valuemax='100'><span style='width:{pct}%'></span></div>"
    )


def grade_breakdown_html(components: list[Any] | None) -> str:
    if not components:
        return ""
    items: list[str] = []
    for c in components:
        name = escape(getattr(c, "name", "") or "")
        try:
            score = float(getattr(c, "score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        if not name:
            continue
        items.append(f"<li>{name} {score:.0f}</li>")
    if not items:
        return ""
    return (
        "<p><strong>Grade breakdown</strong></p><ul class='breakdown'>" + "".join(items) + "</ul>"
    )


def script_diff_html(quality: dict[str, Any] | None) -> str:
    """Both script texts when a rewrite pass ran (#405)."""
    quality = quality or {}
    pre = str(quality.get("script_pre_rewrite") or "").strip()
    post = str(quality.get("script_post_rewrite") or "").strip()
    if not pre or not post:
        return ""
    return (
        "<p><strong>Script diff</strong> LLM draft vs post-gate rewrite</p>"
        f"<pre class='md'>{escape(pre[:800])}\n---\n{escape(post[:800])}</pre>"
    )


def tts_cache_pill_html(cached: Any) -> str:
    if not cached:
        return ""
    return "<p class='pill'>TTS cache hit - $0 re-render</p>"


def thumb_badge_html(provider: str = "", thumbnail_cost: Any = None) -> str:
    label = (provider or "").strip().lower()
    if not label:
        try:
            label = "flux" if float(thumbnail_cost or 0) > 0 else "pillow"
        except (TypeError, ValueError):
            label = "pillow"
    shown = "Pillow" if label in ("pillow", "none", "") else label[:1].upper() + label[1:]
    return f"<span class='badge'>Thumb: {escape(shown)}</span>"


def thumbnail_picker_html(
    run_id: int | None,
    candidates: list[dict[str, Any]] | None,
    *,
    image_hrefs: list[str] | None = None,
) -> str:
    if not run_id or not candidates or len(candidates) < 2:
        return ""
    cards: list[str] = []
    for index, candidate in enumerate(candidates):
        path = str(candidate.get("path") or "")
        arm = str(candidate.get("arm") or "")
        if not path or not arm:
            continue
        src = (
            image_hrefs[index]
            if image_hrefs is not None and index < len(image_hrefs) and image_hrefs[index]
            else _file_uri(path)
        )
        cards.append(
            "<div class='card'>"
            f"<p><strong>{escape(arm)}</strong> · "
            f"{escape(str(candidate.get('provider') or 'unknown'))}</p>"
            f"<img class='thumb' src='{escape(src)}' alt='{escape(arm)} thumbnail'>"
            "<form method='post' action='/pick-thumbnail'>"
            f"<input type='hidden' name='run_id' value='{int(run_id)}'>"
            f"<input type='hidden' name='arm' value='{escape(arm)}'>"
            f"<button type='submit'>Pick {escape(arm)}</button></form></div>"
        )
    if len(cards) < 2:
        return ""
    return (
        "<section><h2>Choose thumbnail</h2>"
        "<p>Publishing is blocked until one arm is picked.</p>"
        "<div class='thumb-grid'>" + "".join(cards) + "</div></section>"
    )


def thumbnail_candidate_routes(
    candidates: list[dict[str, Any]] | None,
) -> tuple[dict[str, str], list[str]]:
    """Map validated candidate files to fixed booth-local HTTP paths."""
    routes: dict[str, str] = {}
    hrefs: list[str] = []
    for index, candidate in enumerate(candidates or []):
        path = os.path.abspath(str(candidate.get("path") or ""))
        ext = os.path.splitext(path)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"} or not os.path.isfile(path):
            hrefs.append("")
            continue
        href = f"/thumbnail-candidate-{index}{ext}"
        routes[href] = path
        hrefs.append(href)
    return routes, hrefs


def parse_thumbnail_pick_post(body: bytes, *, expected_run_id: int) -> tuple[int, str]:
    """Parse a bounded booth pick and bind it to the run currently being reviewed."""
    from urllib.parse import parse_qs

    if len(body) > 1024:
        raise ValueError("Thumbnail pick form is too large")
    try:
        fields = parse_qs(
            body.decode("utf-8", errors="strict"),
            keep_blank_values=True,
            strict_parsing=True,
        )
        run_values = fields.get("run_id") or []
        arm_values = fields.get("arm") or []
        if len(run_values) != 1 or len(arm_values) != 1:
            raise ValueError("Thumbnail pick requires exactly one run_id and arm")
        run_id = int(run_values[0])
        arm = str(arm_values[0])
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid thumbnail pick form: {exc}") from exc
    if run_id != int(expected_run_id):
        raise ValueError(f"Thumbnail pick must target displayed run {expected_run_id}")
    if arm not in {"text_on", "face_forward"}:
        raise ValueError("Thumbnail arm must be text_on or face_forward")
    return run_id, arm


def signal_dots_html(signals: dict[str, Any] | None) -> str:
    if not signals:
        return ""
    parts: list[str] = []
    for name, sig in list(signals.items())[:12]:
        status = str(sig.get("status") or "") if isinstance(sig, dict) else str(sig or "")
        low = status.lower()
        if low in ("ok", "active"):
            cls = "ok"
        elif low in ("inactive", "skipped"):
            cls = "skip"
        elif "stale" in low or "timeout" in low or low in ("unavailable",):
            cls = "warn"
        else:
            cls = "fail"
        parts.append(
            f"<span class='dot {cls}' title='{escape(name)}: {escape(status or 'n/a')}'></span>"
            f"<span>{escape(name)}</span> "
        )
    return "<p>Signals: " + "".join(parts) + "</p>"


def feed_stale_banner_html(text: str = "") -> str:
    if not (text or "").strip():
        return ""
    return f"<p class='banner'>Feed health: {escape(text)}</p>"


def gate_banner_html(text: str = "", *, css: str = "banner") -> str:
    if not (text or "").strip():
        return ""
    return f"<p class='{css}'>{escape(text)}</p>"


def copy_field_html(label: str, value: str, *, field_id: str) -> str:
    if not (value or "").strip():
        return ""
    return (
        f"<p><label for='{escape(field_id)}'>{escape(label)}</label></p>"
        f"<textarea id='{escape(field_id)}' class='md' readonly>{escape(value)}</textarea>"
        "<p><button type='button' "
        f"onclick=\"navigator.clipboard.writeText(document.getElementById('{escape(field_id)}').value)\">"
        f"Copy {escape(label)}</button></p>"
    )


def _command_line(argv: Any) -> str:
    if isinstance(argv, list):
        quoted = ["'" + str(part).replace("'", "''") + "'" for part in argv]
        return "& " + " ".join(quoted)
    return str(argv or "")


def _details_html(summary: str, body: str) -> str:
    if not (body or "").strip():
        return ""
    return "<details class='card'>" f"<summary>{escape(summary)}</summary>" f"{body}" "</details>"


def last_watch_url(channel_id: str | None = None) -> str:
    """Newest uploaded YouTube URL, preferring unlisted review holds."""
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        rows = get_publish_log_repository().list_uploaded_for_channel(channel_id or "tapin")
    except Exception as exc:
        logger.debug("last watch url skipped: %s", exc)
        return ""
    rows = [r for r in (rows or []) if getattr(r, "youtube_video_id", "")]
    if not rows:
        return ""
    unlisted = [r for r in rows if str(getattr(r, "privacy_status", "")).lower() == "unlisted"]
    pool = unlisted or rows
    best = max(pool, key=lambda r: int(getattr(r, "id", 0) or 0))
    vid = str(best.youtube_video_id).strip()
    return f"https://youtu.be/{vid}" if vid else ""


def booth_html(
    *,
    mp4_path: str | None = None,
    thumb_path: str | None = None,
    grade: str = "",
    authenticity: str = "",
    cost: str = "",
    blocking: str = "",
    run_id: int | None = None,
    approve_cmd: str = "",
    cost_share: str = "",
    uploads_left: str = "",
    elevenlabs_chars: str = "",
    apify_pills: str = "",
    escaped_pill: str = "",
    standard_billed: str = "",
    allocated_line: str = "",
    thin_banner: str = "",
    markdown: str = "",
    mp4_href: str = "",
    thumb_href: str = "",
    numeric_chips: str = "",
    semantic_bar: str = "",
    grade_breakdown: str = "",
    tts_cache_pill: str = "",
    thumb_badge: str = "",
    signal_dots: str = "",
    feed_stale: str = "",
    render_gate: str = "",
    rpm_deferred: str = "",
    yesterday_unsynced: str = "",
    unlisted_url: str = "",
    dossier_uri: str = "",
    postmortem_md: str = "",
    trace_json: str = "",
    ffmpeg_command: str = "",
    ffmpeg_intro_command: str = "",
    ffmpeg_outro_command: str = "",
    title: str = "",
    description: str = "",
    duration_readout: str = "",
    captions_href: str = "",
    thumbnail_safe_area: str = "",
    thumbnail_picker: str = "",
    expert_panel_html: str = "",
    channel_id: str = "",
) -> str:
    share = f"<p class='cost-sub'>{escape(cost_share)}</p>" if cost_share else ""
    poster_attr = ""
    poster_chrome = ""
    if thumb_path and os.path.isfile(thumb_path):
        tsrc = thumb_href or _file_uri(thumb_path)
        poster_attr = f" poster='{escape(tsrc)}'"
        poster_chrome = (
            f"<div class='poster-chrome' style='background-image:url({escape(tsrc)})'></div>"
        )
    rate_controls = (
        "<p>"
        "<button type='button' class='rate' onclick='setBoothRate(1)'>1×</button>"
        "<button type='button' class='rate' onclick='setBoothRate(1.25)'>1.25×</button>"
        "<button type='button' class='rate' onclick='toggleSafeArea()'>Safe area</button>"
        "</p>"
        "<script>"
        "(function(){var player=document.getElementById('player');"
        "if(player && player.playbackRate !== undefined){player.playbackRate = 1;}"
        "window.setBoothRate=function(r){var p=document.getElementById('player');"
        "if(p && p.playbackRate !== undefined){p.playbackRate=r;}};"
        "window.toggleSafeArea=function(){var s=document.getElementById('stage');"
        "if(s){s.classList.toggle('safe-on');}};"
        "})();"
        "</script>"
    )
    safe_boxes = (
        "<div class='safe-area' aria-hidden='true'>"
        "<span class='yt-top'></span><span class='yt-bottom'></span></div>"
    )
    if mp4_path and os.path.isfile(mp4_path):
        src = mp4_href or _file_uri(mp4_path)
        track = (
            f"<track kind='captions' src='{escape(captions_href)}' srclang='en' "
            "label='English' default>"
            if captions_href
            else ""
        )
        vid = (
            f"<div class='stage' id='stage'>{poster_chrome}"
            f"<video id='player' class='player' controls src='{escape(src)}'"
            f"{poster_attr}>{track}</video>{safe_boxes}</div>"
            f"{rate_controls}{share}<p>{escape(mp4_path)}</p>"
        )
    else:
        vid = (
            f"<div class='stage' id='stage'>{poster_chrome}"
            "<p id='player'>No last mp4 on disk. Render first, then reopen the booth.</p>"
            f"{safe_boxes}</div>"
            f"{rate_controls}{share}"
        )
    thumb = ""
    if thumb_path and os.path.isfile(thumb_path):
        tsrc = thumb_href or _file_uri(thumb_path)
        thumb = f"<img class='thumb' src='{escape(tsrc)}' alt='thumb'>"
        if thumb_badge:
            thumb += thumb_badge
    elif thumb_badge:
        thumb = thumb_badge
    rid = _run_label(run_id)
    run_id_int = None
    try:
        if run_id is not None and run_id != "":
            run_id_int = int(run_id)
    except (TypeError, ValueError):
        run_id_int = None
    cmd = approve_cmd or (
        f"py -m scripts.ops requeue-upload --run-id {run_id_int}"
        if run_id_int is not None
        else "py -m scripts.ops list-uploads"
    )
    md = markdown or booth_markdown(
        grade=grade,
        authenticity=authenticity,
        cost=cost,
        blocking=blocking,
        cost_share=cost_share,
        run_id=run_id,
    )
    extra_cost = ""
    if standard_billed:
        extra_cost += f"<p>{escape(standard_billed)}</p>"
    if allocated_line:
        extra_cost += f"<p>{escape(allocated_line)}</p>"
    banners = (
        f"{thin_banner}{escaped_pill}{feed_stale}"
        f"{gate_banner_html(render_gate)}{gate_banner_html(rpm_deferred)}"
        f"{gate_banner_html(yesterday_unsynced)}"
    )
    extras = f"{numeric_chips}{semantic_bar}{grade_breakdown}{tts_cache_pill}{signal_dots}"
    public_metadata = (
        title_meter_html(title)
        + description_preview_html(description)
        + (
            f"<p><strong>Duration</strong> {escape(duration_readout)}</p>"
            if duration_readout
            else ""
        )
        + (
            f"<p><strong>Thumbnail safe area</strong> {escape(thumbnail_safe_area)}</p>"
            if thumbnail_safe_area
            else ""
        )
    )
    copy_bits = (
        copy_field_html("last unlisted URL", unlisted_url, field_id="unlisted")
        + copy_field_html("Obsidian dossier URI", dossier_uri, field_id="dossier")
        + copy_field_html("postmortem markdown", postmortem_md, field_id="pmm")
    )
    trace_details = _details_html(
        "Raw trace JSON",
        f"<pre>{escape(trace_json)}</pre>" if trace_json else "",
    )
    command_body = ""
    if ffmpeg_command:
        command_body += f"<p><strong>Primary render</strong></p><pre>{escape(ffmpeg_command)}</pre>"
        command_body += copy_field_html(
            "ffmpeg command",
            ffmpeg_command,
            field_id="ffmpeg-command",
        )
    if ffmpeg_intro_command:
        command_body += (
            f"<p><strong>Intro concat</strong></p><pre>{escape(ffmpeg_intro_command)}</pre>"
        )
    if ffmpeg_outro_command:
        command_body += (
            f"<p><strong>End-card concat</strong></p><pre>{escape(ffmpeg_outro_command)}</pre>"
        )
    command_details = _details_html("FFmpeg commands", command_body)
    body = (
        f"{banners}"
        f"<div class='card'>{vid}{thumb}</div>{thumbnail_picker}"
        "<div class='card'>"
        f"<p><strong>Run</strong> {escape(rid)}</p>"
        f"<p><strong>Grade</strong> {escape(grade or 'n/a')}</p>"
        f"{expert_panel_html}"
        f"<p><strong>Authenticity</strong> {escape(authenticity or 'n/a')}</p>"
        f"<p><strong>Cost</strong> {escape(cost or 'n/a')}</p>"
        f"{extra_cost}"
        f"<p><strong>Blocking publish</strong> {escape(blocking or 'n/a')}</p>"
        f"{public_metadata}"
        f"{apify_pills}{extras}"
        "</div>"
        "<div class='card'>"
        "<p><strong>Approve</strong> (unlisted review, cadence-safe):</p>"
        f"<pre>{escape(cmd)}</pre>"
        "<p><strong>Reject</strong>: leave the mp4 in output/; do not queue an upload.</p>"
        "<p><label for='md'>Copy as markdown</label></p>"
        f"<textarea id='md' class='md' readonly>{escape(md)}</textarea>"
        "<p><button type='button' "
        "onclick=\"navigator.clipboard.writeText(document.getElementById('md').value)\">"
        "Copy as markdown</button></p>"
        f"{copy_bits}"
        "</div>"
        f"{trace_details}{command_details}"
    )
    quota_bits = [b for b in (uploads_left, elevenlabs_chars) if b]
    header_html = ""
    if quota_bits:
        header_html += f"<div class='quota' id='quotabar'>{escape(' · '.join(quota_bits))}</div>"
    if cost_share:
        header_html += f"<div class='sticky-cost' id='costbar'>{escape(cost_share)}</div>"
    return themed_page(
        "Last-run review booth",
        body,
        subtitle="play + grade + authenticity + cost",
        skip_href="#player",
        header_html=header_html,
        channel_id=channel_id,
    )


def write_lightbox(thumb_path: str | None, *, open_browser: bool = True) -> str:
    path = write_html(lightbox_html(thumb_path), filename="lightbox.html")
    if open_browser:
        open_local(path)
    return path


def write_thin_facts_screen(
    reason: str, *, fact_count: int | None = None, open_browser: bool = True
) -> str:
    path = write_html(thin_facts_html(reason, fact_count=fact_count), filename="thin_facts.html")
    if open_browser:
        open_local(path)
    return path


def gather_booth_context(channel_id: str | None = None) -> dict[str, Any]:
    from core.win_shell import last_media_file

    mp4 = last_media_file("mp4", channel_id=channel_id)
    thumb = last_media_file("thumb", channel_id=channel_id)
    trace = last_trace(channel_id)
    quality = (trace or {}).get("quality") or {}
    cost_d = (trace or {}).get("cost") or {}
    run_id = (trace or {}).get("run_id")
    record = None
    if run_id:
        try:
            from storage.repositories.content_runs import get_content_run_repository

            record = get_content_run_repository().get(int(run_id))
        except Exception as exc:
            logger.debug("booth content metadata skipped: %s", exc)
    title = str(getattr(record, "title", "") or "")
    description = str(getattr(record, "description", "") or "")
    timings = (trace or {}).get("timings") or {}
    if record is not None:
        try:
            stored_timings = json.loads(getattr(record, "timings_json", "") or "{}")
            if isinstance(stored_timings, dict):
                timings = {**stored_timings, **timings}
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.debug("booth stored timings unreadable for run %s: %s", run_id, exc)
    actual_duration = None
    spoken_audio = str(getattr(record, "mp3_path", "") or "")
    if spoken_audio and os.path.isfile(spoken_audio):
        try:
            from video.render_video import _probe_video_duration

            actual_duration = _probe_video_duration(spoken_audio)
        except Exception as exc:
            logger.debug("booth spoken-audio duration skipped: %s", exc)
    duration_line = duration_readout(actual_duration, timings.get("word_count"))
    captions_path = ""
    if mp4:
        candidate = os.path.splitext(str(mp4))[0] + ".srt"
        if os.path.isfile(candidate):
            captions_path = candidate
    thumbnail_safe_area = ""
    if thumb and os.path.isfile(thumb):
        try:
            from core.thumbnail_safe_area import inspect_thumbnail, render_check

            thumbnail_safe_area = render_check(inspect_thumbnail(thumb))
        except Exception as exc:
            logger.warning("Booth thumbnail safe-area check failed for %s: %s", thumb, exc)
    grade = ""
    grade_obj = None
    try:
        from core.video_grade import grade_from_parts

        if quality:
            grade_obj = grade_from_parts(quality=quality)
            grade = f"{grade_obj.letter} ({grade_obj.score:.0f})"
    except Exception as exc:
        logger.debug("booth grade skipped: %s", exc)
    expert_panel_html = ""
    try:
        from core.providers import flag_enabled

        if flag_enabled("EXPERT_PANEL_ENABLED"):
            stored = quality.get("expert_panel") if isinstance(quality, dict) else None
            if stored:
                bits = []
                for entry in stored:
                    persona = str(entry.get("persona") or "").strip()
                    review = str(entry.get("review") or "").strip()
                    if persona and review:
                        bits.append(f"<strong>{escape(persona)}</strong>: {escape(review)}")
                if bits:
                    expert_panel_html = "<p>" + "<br>".join(bits) + "</p>"
    except Exception as exc:
        logger.debug("booth expert panel skipped: %s", exc)
    blocking = ""
    try:
        from core.publish_blockers import blocking_publish_sentence

        blocking = blocking_publish_sentence(
            channel_id=channel_id,
            quality=quality,
            features=(trace or {}).get("features") or quality,
            mp4_path=mp4,
        )
    except Exception as exc:
        logger.debug("booth blocking skipped: %s", exc)
    tts = cost_d.get("tts")
    total = cost_d.get("total")
    cost_s = ""
    if total is not None:
        cost_s = f"tts ${float(tts or 0):.2f} · total ${float(total):.2f}"
    uploads_left = ""
    elevenlabs_chars = ""
    try:
        from core.win_notify import quota_chip_lines

        for line in quota_chip_lines(channel_id=channel_id):
            if line.startswith("YouTube:"):
                uploads_left = line
            elif line.startswith("ElevenLabs:"):
                elevenlabs_chars = line
    except Exception as exc:
        logger.debug("booth quota header skipped: %s", exc)
    standard_billed = ""
    try:
        from core.cost_meter import format_standard_billed_line, local_tts_selected

        script = str((trace or {}).get("script_preview") or "")
        standard_billed = format_standard_billed_line(script)
        if not standard_billed and local_tts_selected():
            standard_billed = "Standard would have billed ElevenLabs TTS (~$0.31/video, 91%)"
    except Exception as exc:
        logger.debug("booth standard-billed skipped: %s", exc)
    allocated_line = ""
    try:
        from core.unit_economics import allocated_vs_marginal_oneliner

        allocated_line = allocated_vs_marginal_oneliner(
            n_videos=None,
            marginal=float(total) if total is not None else None,
        )
    except Exception as exc:
        logger.debug("booth allocated line skipped: %s", exc)

    numeric_chips = ""
    try:
        spans = quality.get("ungrounded_numeric") or []
        if not spans:
            from core.fact_grounding import numeric_claims_among

            spans = numeric_claims_among(quality.get("ungrounded_entities") or [])
        numeric_chips = numeric_chips_html(list(spans) if spans else None)
    except Exception as exc:
        logger.debug("booth numeric chips skipped: %s", exc)

    semantic_bar = ""
    try:
        semantic_bar = semantic_bar_html(quality.get("authenticity_semantic"))
    except Exception as exc:
        logger.debug("booth semantic bar skipped: %s", exc)

    grade_breakdown = ""
    try:
        if grade_obj is not None:
            grade_breakdown = grade_breakdown_html(grade_obj.components)
    except Exception as exc:
        logger.debug("booth grade breakdown skipped: %s", exc)

    features = (trace or {}).get("features") or {}
    thumbnail_picker = ""
    thumbnail_candidates: list[dict[str, Any]] = []
    try:
        if run_id:
            from core.run_features import load_features

            stored_features = load_features(int(run_id))
            if isinstance(stored_features, dict):
                features = {**features, **stored_features}
            thumbnail_candidates = [
                dict(item)
                for item in (features.get("thumbnail_candidates") or [])
                if isinstance(item, dict)
            ]
            thumbnail_picker = thumbnail_picker_html(int(run_id), thumbnail_candidates)
    except Exception as exc:
        logger.debug("booth thumbnail picker skipped: %s", exc)
    tts_cache_pill = ""
    try:
        cached = (trace or {}).get("tts_cached")
        if cached is None and isinstance(features, dict):
            cached = features.get("tts_cached")
        tts_cache_pill = tts_cache_pill_html(cached)
    except Exception as exc:
        logger.debug("booth tts cache pill skipped: %s", exc)

    thumb_badge = ""
    try:
        provider = str(
            (trace or {}).get("thumbnail_provider")
            or (features.get("thumbnail_provider") if isinstance(features, dict) else "")
            or quality.get("thumbnail_source")
            or ""
        )
        thumb_badge = thumb_badge_html(provider, cost_d.get("thumbnail"))
    except Exception as exc:
        logger.debug("booth thumb badge skipped: %s", exc)

    signal_dots = ""
    try:
        signal_dots = signal_dots_html((trace or {}).get("signals") or {})
    except Exception as exc:
        logger.debug("booth signal dots skipped: %s", exc)

    feed_stale = ""
    try:
        from core.feed_health import stale_strip_text

        feed_stale = feed_stale_banner_html(stale_strip_text())
    except Exception as exc:
        logger.debug("booth feed-stale skipped: %s", exc)

    render_gate = ""
    try:
        from core.render_gate import overnight_plain_reason

        render_gate = overnight_plain_reason(quality)
    except Exception as exc:
        logger.debug("booth render-gate skipped: %s", exc)

    rpm_deferred = ""
    try:
        from core.rpm_cost_gate import deferred_plain_reason

        rpm_deferred = deferred_plain_reason(channel_id or "tapin")
    except Exception as exc:
        logger.debug("booth rpm-deferred skipped: %s", exc)

    yesterday_unsynced = ""
    try:
        from core.metrics_gate import yesterday_unsynced_copy

        yesterday_unsynced = yesterday_unsynced_copy(channel_id or "tapin")
    except Exception as exc:
        logger.debug("booth yesterday-unsynced skipped: %s", exc)

    unlisted_url = ""
    try:
        unlisted_url = last_watch_url(channel_id)
    except Exception as exc:
        logger.debug("booth unlisted url skipped: %s", exc)

    dossier_uri = ""
    try:
        from core.vault_dossiers import dossier_obsidian_uri

        dossier_uri = dossier_obsidian_uri(run_id, channel_id)
    except Exception as exc:
        logger.debug("booth dossier uri skipped: %s", exc)

    postmortem_md = ""
    try:
        if run_id:
            from core.postmortem import as_markdown, assemble

            postmortem_md = as_markdown(
                assemble(run_id=int(run_id), trace=trace or {}, quality=quality, cost=cost_d)
            )
    except Exception as exc:
        logger.debug("booth postmortem md skipped: %s", exc)

    trace_json = ""
    ffmpeg_command = ""
    ffmpeg_intro_command = ""
    ffmpeg_outro_command = ""
    try:
        from core.run_trace import redact_trace_value

        if trace:
            trace_json = json.dumps(redact_trace_value(trace), indent=2, default=str)
            ffmpeg_command = _command_line(trace.get("ffmpeg_command"))
            ffmpeg_intro_command = _command_line(trace.get("ffmpeg_intro_command"))
            ffmpeg_outro_command = _command_line(trace.get("ffmpeg_outro_command"))
    except Exception as exc:
        logger.debug("booth trace details skipped: %s", exc)

    return {
        "mp4_path": mp4,
        "thumb_path": thumb,
        "channel_id": channel_id or "",
        "grade": grade,
        "authenticity": str(quality.get("authenticity_verdict") or ""),
        "cost": cost_s,
        "cost_share": tts_share_line(tts, total),
        "blocking": blocking,
        "run_id": run_id,
        "uploads_left": uploads_left,
        "elevenlabs_chars": elevenlabs_chars,
        "apify_pills": apify_pills_html(),
        "escaped_pill": escaped_llm_pill_html(trace),
        "standard_billed": standard_billed,
        "allocated_line": allocated_line,
        "thin_banner": thin_facts_banner_html(blocking),
        "markdown": booth_markdown(
            grade=grade,
            authenticity=str(quality.get("authenticity_verdict") or ""),
            cost=cost_s,
            blocking=blocking,
            cost_share=tts_share_line(tts, total),
            run_id=run_id,
        ),
        "numeric_chips": numeric_chips,
        "semantic_bar": semantic_bar,
        "grade_breakdown": grade_breakdown + script_diff_html(quality),
        "tts_cache_pill": tts_cache_pill,
        "thumb_badge": thumb_badge,
        "signal_dots": signal_dots,
        "feed_stale": feed_stale,
        "render_gate": render_gate,
        "rpm_deferred": rpm_deferred,
        "yesterday_unsynced": yesterday_unsynced,
        "unlisted_url": unlisted_url,
        "dossier_uri": dossier_uri,
        "postmortem_md": postmortem_md,
        "trace_json": trace_json,
        "ffmpeg_command": ffmpeg_command,
        "ffmpeg_intro_command": ffmpeg_intro_command,
        "ffmpeg_outro_command": ffmpeg_outro_command,
        "title": title,
        "description": description,
        "duration_readout": duration_line,
        "captions_path": captions_path,
        "thumbnail_safe_area": thumbnail_safe_area,
        "thumbnail_picker": thumbnail_picker,
        "thumbnail_candidates": thumbnail_candidates,
        "expert_panel_html": expert_panel_html,
    }


def write_booth(channel_id: str | None = None, *, open_browser: bool = True) -> str:
    ctx = gather_booth_context(channel_id)
    ctx.pop("thumbnail_candidates", None)
    captions_path = str(ctx.pop("captions_path", "") or "")
    if captions_path:
        try:
            vtt_path = os.path.join(html_dir(), "booth.vtt")
            _srt_to_vtt(captions_path, vtt_path)
            ctx["captions_href"] = _file_uri(vtt_path)
        except Exception as exc:
            logger.warning("Booth captions unavailable: %s", exc)
    path = write_html(booth_html(**ctx), filename="booth.html")
    if open_browser:
        open_local(path)
    return path


def serve_booth(channel_id: str | None = None, *, port: int = 0) -> str:
    """Tiny stdlib HTTP host for the booth (not FastAPI, not #141). Returns the URL."""
    ctx = gather_booth_context(channel_id)
    candidates = ctx.pop("thumbnail_candidates", [])
    candidate_routes, candidate_hrefs = thumbnail_candidate_routes(candidates)
    if ctx.get("run_id"):
        ctx["thumbnail_picker"] = thumbnail_picker_html(
            int(ctx["run_id"]),
            candidates,
            image_hrefs=candidate_hrefs,
        )
    mp4 = ctx.get("mp4_path")
    thumb = ctx.get("thumb_path")
    captions_path = str(ctx.pop("captions_path", "") or "")
    if mp4 and os.path.isfile(str(mp4)):
        ctx["mp4_href"] = "booth.mp4"
    thumb_name = ""
    if thumb and os.path.isfile(str(thumb)):
        ext = os.path.splitext(str(thumb))[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        thumb_name = f"booth{ext}"
        ctx["thumb_href"] = thumb_name
    if captions_path and os.path.isfile(captions_path):
        try:
            _srt_to_vtt(captions_path, os.path.join(html_dir(), "booth.vtt"))
            ctx["captions_href"] = "booth.vtt"
        except Exception as exc:
            logger.warning("Booth captions unavailable: %s", exc)
    html_path = write_html(booth_html(**ctx), filename="booth.html")
    directory = os.path.dirname(html_path)
    displayed_run_id = int(ctx.get("run_id") or 0)

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def translate_path(self, path: str) -> str:
            from urllib.parse import unquote, urlparse

            parsed_path = unquote(urlparse(path).path)
            if parsed_path in candidate_routes:
                return candidate_routes[parsed_path]
            if parsed_path in ("/favicon.ico", "/favicon.svg", "favicon.ico", "favicon.svg"):
                from config.paths import ROOT_DIR

                mark = os.path.join(ROOT_DIR, "core", "data", "booth_favicon.svg")
                if os.path.isfile(mark):
                    return mark
            name = parsed_path.rsplit("/", 1)[-1]
            if name in ("favicon.ico", "favicon.svg"):
                from config.paths import ROOT_DIR

                mark = os.path.join(ROOT_DIR, "core", "data", "booth_favicon.svg")
                if os.path.isfile(mark):
                    return mark
            if name == "booth.mp4" and mp4 and os.path.isfile(str(mp4)):
                return str(mp4)
            if thumb_name and name == thumb_name and thumb and os.path.isfile(str(thumb)):
                return str(thumb)
            return super().translate_path(path)

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("booth http: " + fmt, *args)

        def do_POST(self) -> None:
            from urllib.parse import urlparse

            if urlparse(self.path).path != "/pick-thumbnail":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 1024:
                    raise ValueError("Thumbnail pick form length must be 1-1024 bytes")
                picked_run, arm = parse_thumbnail_pick_post(
                    self.rfile.read(length),
                    expected_run_id=displayed_run_id,
                )
                from core.thumbnail_pick import pick_thumbnail

                pick_thumbnail(picked_run, arm=arm, channel_id=channel_id)
            except Exception as exc:
                logger.warning("Booth thumbnail pick failed: %s", exc)
                self.send_error(400, str(exc))
                return
            self.send_response(303)
            self.send_header("Location", "/booth.html")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    host, bound = server.server_address
    url = f"http://{host}:{bound}/booth.html"
    import threading
    import webbrowser

    threading.Thread(target=server.serve_forever, daemon=True).start()
    if open_html_enabled():
        try:
            webbrowser.open(url)
        except Exception as exc:
            logger.debug("booth open skipped: %s", exc)
    return url
