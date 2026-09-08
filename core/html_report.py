"""Themed HTML snapshots for operator dumps (reliability, economics, doctor, booth).

Zero new backend: wrap existing ASCII/gather output in a dark page, optionally
open it in the default browser. CONTENT_HTML_OPEN=false skips the open (the
test suite sets this). Nested-try fail-open so a dump cannot wipe a command.
"""

from __future__ import annotations

import html
import os
import tempfile
import time
from typing import Any

from core.logging import get_logger

logger = get_logger("core.html_report")

_CSS = """
:root { color-scheme: dark; }
html, body { margin: 0; padding: 0; background: #111318; color: #e8eaed;
  font-family: "Segoe UI", system-ui, sans-serif; font-size: 16px; line-height: 1.45; }
.skip { position: absolute; left: -999px; top: auto; width: 1px; height: 1px; overflow: hidden; }
.skip:focus { left: 1rem; top: 1rem; width: auto; height: auto; z-index: 20;
  background: #000; color: #fff; padding: 0.5rem 0.75rem; }
header { position: sticky; top: 0; z-index: 10; padding: 1rem 1.25rem;
  background: #1a1d24; border-bottom: 3px solid var(--header-border, #c62828); }
header h1 { margin: 0; font-size: 1.25rem; letter-spacing: 0.02em; }
header .sub { color: #9aa0a6; font-size: 1rem; margin-top: 0.25rem; }
header .quota, #quotabar { font-size: 16px; color: #e8eaed; margin-top: 0.35rem; }
.sticky-cost, #costbar { font-size: 16px; color: #fdd663; margin-top: 0.25rem; font-weight: 600; }
button, input, select, textarea { font-size: 16px; }
main { padding: 1.25rem; max-width: 960px; }
pre { background: #0d0f14; border: 1px solid #2a2f3a; padding: 1rem; overflow: auto;
  font-family: "JetBrains Mono", Consolas, monospace; font-size: 16px; white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%; font-size: 16px; }
th, td { text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid #2a2f3a; }
th { color: #9aa0a6; font-weight: 600; }
.ok { color: #81c995; } .fail { color: #f28b82; } .warn { color: #fdd663; }
.card { background: #1a1d24; border: 1px solid #2a2f3a; padding: 1rem; margin: 0.75rem 0; }
img.thumb { max-width: 100%; height: auto; cursor: zoom-in; border: 1px solid #2a2f3a; }
dialog { border: none; padding: 0; background: #000; max-width: 96vw; }
dialog img { max-width: 96vw; max-height: 96vh; }
video { width: 100%; max-height: 70vh; background: #000; object-fit: contain; }
.stage { position: relative; width: 100%; max-width: 420px; margin: 0 auto;
  background: #000; aspect-ratio: 9 / 16; display: flex; align-items: center;
  justify-content: center; overflow: hidden; }
.stage video { width: 100%; height: 100%; max-height: none; object-fit: contain; }
.stage .poster-chrome { position: absolute; inset: 0; background-size: cover;
  background-position: center; opacity: 0.22; pointer-events: none; }
.safe-area { display: none; position: absolute; inset: 0; pointer-events: none; }
.stage.safe-on .safe-area { display: block; }
.safe-area .yt-top { position: absolute; top: 0; left: 0; right: 0; height: 12%;
  border-bottom: 1px dashed #fdd663; }
.safe-area .yt-bottom { position: absolute; bottom: 0; left: 0; right: 0; height: 20%;
  border-top: 1px dashed #fdd663; }
body.channel-moneywise header h1 { font-family: Georgia, "Times New Roman", serif; }
.cost-sub { color: #fdd663; font-size: 16px; margin: 0.35rem 0 0; }
.redpill { color: #f28b82; font-weight: 700; }
.banner { background: #3c1f1f; border: 1px solid #f28b82; padding: 0.6rem 0.8rem; margin: 0.5rem 0; }
.pill { display: inline-block; border: 1px solid #2a2f3a; padding: 0.15rem 0.5rem;
  margin: 0.15rem; font-size: 16px; }
textarea.md { width: 100%; min-height: 7rem; background: #0d0f14; color: #e8eaed;
  border: 1px solid #2a2f3a; font-family: "JetBrains Mono", Consolas, monospace; font-size: 16px; }
a { color: #8ab4f8; }
.bar { height: 10px; background: #2a2f3a; border: 1px solid #2a2f3a; margin: 0.35rem 0 0.6rem; }
.bar > span { display: block; height: 100%; background: #fdd663; }
.dot { display: inline-block; width: 0.65rem; height: 0.65rem; border-radius: 50%;
  margin-right: 0.25rem; vertical-align: middle; }
.dot.ok { background: #81c995; } .dot.fail { background: #f28b82; }
.dot.warn { background: #fdd663; } .dot.skip { background: #5f6368; }
.breakdown { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0; list-style: none; }
.breakdown li { border: 1px solid #2a2f3a; padding: 0.2rem 0.5rem; font-size: 16px; }
.chip { display: inline-block; border: 1px solid #fdd663; color: #fdd663;
  padding: 0.1rem 0.45rem; margin: 0.15rem; font-size: 16px; }
.badge { display: inline-block; border: 1px solid #2a2f3a; padding: 0.1rem 0.45rem;
  margin-left: 0.35rem; font-size: 16px; }
.swatch { display: flex; height: 6px; margin: 0.35rem 0 0; gap: 0; }
.swatch span { flex: 1; display: block; min-height: 6px; }
button.rate { margin: 0.35rem 0.35rem 0 0; }
@media (prefers-contrast: more) {
  html, body { background: #000; color: #fff; }
  header { background: #000; border-bottom-color: #fff; }
  header .sub, th, .pill { color: #fff; }
  a { color: #fff; text-decoration: underline; }
  .cost-sub, .warn { color: #fff; }
  pre, .card, textarea.md { border-color: #fff; background: #000; }
}
@media (forced-colors: active) {
  header { border-bottom: 3px solid CanvasText; }
}
img.wordmark { height: 28px; width: auto; display: block; margin: 0.35rem 0 0; }
body.reduced-chroma { filter: saturate(0.45); }
@media print {
  header, .skip, .swatch, img.wordmark { display: none !important; }
  main { padding: 0; max-width: none; }
  pre { border: none; background: #fff; color: #000; }
}
"""

_ASCII_REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
    "\u2026": "...",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2192": "->",
}


def ascii_safe(text: Any) -> str:
    """Strip emoji / smart punctuation so dumps survive cp1252 consoles."""
    out: list[str] = []
    for ch in str(text if text is not None else ""):
        if ch in _ASCII_REPLACEMENTS:
            out.append(_ASCII_REPLACEMENTS[ch])
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("?")
    return "".join(out)


def html_dir() -> str:
    override = (os.getenv("CONTENT_HTML_DIR") or "").strip()
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    path = os.path.join(tempfile.gettempdir(), "content_os_html")
    os.makedirs(path, exist_ok=True)
    return path


def open_html_enabled() -> bool:
    return os.getenv("CONTENT_HTML_OPEN", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def escape(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def themed_page(
    title: str,
    body_html: str,
    *,
    subtitle: str = "",
    skip_href: str = "#main",
    header_html: str = "",
    channel_id: str = "",
) -> str:
    sub = ascii_safe(subtitle or "Content OS operator snapshot")
    safe_title = ascii_safe(title)
    skip = f"<a class='skip' href='{escape(skip_href)}'>Skip to content</a>" if skip_href else ""
    extra = header_html or ""
    mark = ""
    try:
        from core.wordmark import wordmark_html

        mark = wordmark_html()
    except Exception as exc:
        logger.debug("wordmark skipped: %s", exc)
    swatch = ""
    cid = (channel_id or "").strip().lower()
    if cid:
        try:
            from config.channels import get_channel_profile

            card = get_channel_profile(cid).end_card or {}
            bg = str(card.get("bg") or "").strip()
            fg = str(card.get("fg") or "").strip()
            if bg:
                swatch = (
                    "<div class='swatch' aria-hidden='true'>"
                    f"<span style='background:{escape(bg)}'></span>"
                    f"<span style='background:{escape(fg or '#FFFFFF')}'></span>"
                    "</div>"
                )
        except Exception as exc:
            logger.debug("channel swatch skipped: %s", exc)
    icon = '<link rel="icon" href="favicon.svg" type="image/svg+xml">'
    classes: list[str] = []
    if cid:
        classes.append(f"channel-{escape(cid)}")
    if os.getenv("CONTENT_UI_REDUCED_CHROMA", "").strip().lower() in ("1", "true", "yes", "on"):
        classes.append("reduced-chroma")
    from core.chrome import look_flags, redact_operator_paths, themed_css

    flags = look_flags()
    if flags["grain"]:
        classes.append("grain")
    if flags["vignette"]:
        classes.append("vignette")
    css = themed_css(
        cid,
        grain=flags["grain"],
        vignette=flags["vignette"],
        colorblind=flags["colorblind"],
    )
    body_html = redact_operator_paths(body_html)
    safe_title = redact_operator_paths(safe_title)
    sub = redact_operator_paths(sub)
    extra = redact_operator_paths(extra)
    body_class = f" class='{' '.join(classes)}'" if classes else ""
    body_style = ""
    if cid:
        try:
            from core.design_tokens import header_border_hex

            body_style = f" style='--header-border:{escape(header_border_hex(cid))}'"
        except Exception as exc:
            logger.debug("header border token skipped: %s", exc)
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"{icon}"
        # `_CSS` first, token CSS second. Both redeclare `html, body`, `header`,
        # `pre`, `table`, `.card` and `a` at equal specificity, so the later block
        # wins -- and with the token CSS first, every visible colour was still the
        # legacy palette while #172 claimed dumps shared the generated one.
        # `_CSS` stays as the structural/layout base; tokens override the colours.
        f"<title>{escape(safe_title)}</title><style>{_CSS}{css}</style></head>"
        f"<body{body_class}{body_style}>"
        f"{skip}<header><h1>{escape(safe_title)}</h1>"
        f"<div class='sub'>{escape(sub)}</div>{mark}{swatch}{extra}</header>"
        f"<main id='main'>{body_html}</main></body></html>"
    )


def pre_body(text: str) -> str:
    return f"<pre>{escape(ascii_safe(text))}</pre>"


def write_html(html_text: str, *, filename: str) -> str:
    """Write UTF-8 HTML under html_dir(); returns the path."""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    if not safe.lower().endswith(".html"):
        safe += ".html"
    path = os.path.join(html_dir(), safe)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return path


def open_local(path: str) -> bool:
    """Open a local file in the default app. Fail-open; never raises."""
    if not open_html_enabled():
        return False
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
            return True
        import webbrowser

        return bool(webbrowser.open(path))
    except Exception as exc:
        logger.debug("open_local skipped: %s", exc)
        return False


def dump_pre(
    title: str,
    text: str,
    *,
    filename: str | None = None,
    open_browser: bool = True,
    channel_id: str = "",
) -> str:
    """Themed <pre> snapshot. Returns the written path."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = filename or f"{title.lower().replace(' ', '_')}_{stamp}.html"
    path = write_html(themed_page(title, pre_body(text), channel_id=channel_id), filename=name)
    if open_browser:
        open_local(path)
    return path
