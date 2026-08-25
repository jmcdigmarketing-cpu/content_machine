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

from core.html_report import escape, open_html_enabled, open_local, themed_page, write_html
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
) -> str:
    share = f"<p class='cost-sub'>{escape(cost_share)}</p>" if cost_share else ""
    if mp4_path and os.path.isfile(mp4_path):
        src = mp4_href or _file_uri(mp4_path)
        vid = (
            f"<video id='player' controls src='{escape(src)}'></video>"
            f"{share}<p>{escape(mp4_path)}</p>"
        )
    else:
        vid = (
            "<p id='player'>No last mp4 on disk. Render first, then reopen the booth.</p>"
            f"{share}"
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
    command_details = _details_html("FFmpeg commands", command_body)
    body = (
        f"{banners}"
        f"<div class='card'>{vid}{thumb}</div>"
        "<div class='card'>"
        f"<p><strong>Run</strong> {escape(rid)}</p>"
        f"<p><strong>Grade</strong> {escape(grade or 'n/a')}</p>"
        f"<p><strong>Authenticity</strong> {escape(authenticity or 'n/a')}</p>"
        f"<p><strong>Cost</strong> {escape(cost or 'n/a')}</p>"
        f"{extra_cost}"
        f"<p><strong>Blocking publish</strong> {escape(blocking or 'n/a')}</p>"
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
    grade = ""
    grade_obj = None
    try:
        from core.video_grade import grade_from_parts

        if quality:
            grade_obj = grade_from_parts(quality=quality)
            grade = f"{grade_obj.letter} ({grade_obj.score:.0f})"
    except Exception as exc:
        logger.debug("booth grade skipped: %s", exc)
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
    try:
        from core.run_trace import redact_trace_value

        if trace:
            trace_json = json.dumps(redact_trace_value(trace), indent=2, default=str)
            ffmpeg_command = _command_line(trace.get("ffmpeg_command"))
            ffmpeg_intro_command = _command_line(trace.get("ffmpeg_intro_command"))
    except Exception as exc:
        logger.debug("booth trace details skipped: %s", exc)

    return {
        "mp4_path": mp4,
        "thumb_path": thumb,
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
        "grade_breakdown": grade_breakdown,
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
    }


def write_booth(channel_id: str | None = None, *, open_browser: bool = True) -> str:
    ctx = gather_booth_context(channel_id)
    path = write_html(booth_html(**ctx), filename="booth.html")
    if open_browser:
        open_local(path)
    return path


def serve_booth(channel_id: str | None = None, *, port: int = 0) -> str:
    """Tiny stdlib HTTP host for the booth (not FastAPI, not #141). Returns the URL."""
    ctx = gather_booth_context(channel_id)
    mp4 = ctx.get("mp4_path")
    thumb = ctx.get("thumb_path")
    if mp4 and os.path.isfile(str(mp4)):
        ctx["mp4_href"] = "booth.mp4"
    thumb_name = ""
    if thumb and os.path.isfile(str(thumb)):
        ext = os.path.splitext(str(thumb))[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        thumb_name = f"booth{ext}"
        ctx["thumb_href"] = thumb_name
    html_path = write_html(booth_html(**ctx), filename="booth.html")
    directory = os.path.dirname(html_path)

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def translate_path(self, path: str) -> str:
            from urllib.parse import unquote, urlparse

            name = unquote(urlparse(path).path).rsplit("/", 1)[-1]
            if name == "booth.mp4" and mp4 and os.path.isfile(str(mp4)):
                return str(mp4)
            if thumb_name and name == thumb_name and thumb and os.path.isfile(str(thumb)):
                return str(thumb)
            return super().translate_path(path)

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("booth http: " + fmt, *args)

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
