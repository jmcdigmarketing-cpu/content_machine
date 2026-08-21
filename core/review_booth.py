"""Last-run review booth + thumbnail lightbox + thin-facts abort screen.

Localhost HTML over the last render (play / grade / authenticity / cost /
Approve). Not FastAPI, not the full review room. Stdlib only.
"""

from __future__ import annotations

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
        "<p class='fail'><strong>Thin-facts abort</strong> — TTS skipped so the "
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
    rid = f"#{int(run_id)}" if run_id else "(last render)"
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
    return "<p class='redpill'>Escaped free-first LLM — this run landed on a paid slug.</p>"


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
) -> str:
    share = f"<p class='cost-sub'>{escape(cost_share)}</p>" if cost_share else ""
    if mp4_path and os.path.isfile(mp4_path):
        uri = _file_uri(mp4_path)
        vid = (
            f"<video id='player' controls src='{escape(uri)}'></video>"
            f"{share}<p>{escape(mp4_path)}</p>"
        )
    else:
        vid = (
            "<p id='player'>No last mp4 on disk. Render first, then reopen the booth.</p>"
            f"{share}"
        )
    thumb = ""
    if thumb_path and os.path.isfile(thumb_path):
        thumb = f"<img class='thumb' src='{escape(_file_uri(thumb_path))}' alt='thumb'>"
    rid = f"#{int(run_id)}" if run_id else "(last render)"
    cmd = approve_cmd or (
        f"py -m scripts.ops requeue-upload --run-id {int(run_id)}"
        if run_id
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
    body = (
        f"{thin_banner}{escaped_pill}"
        f"<div class='card'>{vid}{thumb}</div>"
        "<div class='card'>"
        f"<p><strong>Run</strong> {escape(rid)}</p>"
        f"<p><strong>Grade</strong> {escape(grade or 'n/a')}</p>"
        f"<p><strong>Authenticity</strong> {escape(authenticity or 'n/a')}</p>"
        f"<p><strong>Cost</strong> {escape(cost or 'n/a')}</p>"
        f"{extra_cost}"
        f"<p><strong>Blocking publish</strong> {escape(blocking or 'n/a')}</p>"
        f"{apify_pills}"
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
        "</div>"
    )
    quota_bits = [b for b in (uploads_left, elevenlabs_chars) if b]
    header_html = f"<div class='quota'>{escape(' · '.join(quota_bits))}</div>" if quota_bits else ""
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
    try:
        from core.video_grade import grade_from_parts

        if quality:
            g = grade_from_parts(quality=quality)
            grade = f"{g.letter} ({g.score:.0f})"
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

        for line in quota_chip_lines():
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
    }


def write_booth(channel_id: str | None = None, *, open_browser: bool = True) -> str:
    ctx = gather_booth_context(channel_id)
    path = write_html(booth_html(**ctx), filename="booth.html")
    if open_browser:
        open_local(path)
    return path


def serve_booth(channel_id: str | None = None, *, port: int = 0) -> str:
    """Tiny stdlib HTTP host for the booth (not FastAPI, not #141). Returns the URL."""
    html_path = write_booth(channel_id, open_browser=False)
    directory = os.path.dirname(html_path)

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

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
