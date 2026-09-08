"""Stage 2 chrome: QSS + HTML CSS from #170 tokens. No Qt import."""

from __future__ import annotations

import os
import re
from pathlib import Path

from core.design_tokens import (
    channel_tokens,
    header_border_hex,
    load_tokens,
    look_grain,
    look_vignette,
    role_hex,
)


def _type_px(name: str, default: int) -> int:
    try:
        return int((load_tokens().get("type") or {}).get(name) or default)
    except (TypeError, ValueError):
        return default


def _space_px(name: str, default: int) -> int:
    try:
        return int((load_tokens().get("spacing") or {}).get(name) or default)
    except (TypeError, ValueError):
        return default


def empty_state_copy() -> str:
    return (
        "Idle. Type a topic, paste the article in Key facts, then Start video. "
        "This box is the run 73 paste — not a PowerShell one-liner."
    )


def error_state_copy(detail: str) -> str:
    text = (detail or "unknown error").strip()
    return f"Stopped: {text}"


def device_pixel_ratio(screen: object | None) -> float:
    """1.0 when there is no monitor (CI / offscreen). Real QScreen reports DPR."""
    if screen is None:
        return 1.0
    getter = getattr(screen, "devicePixelRatio", None)
    if not callable(getter):
        return 1.0
    try:
        value = float(getter())
    except (TypeError, ValueError):
        return 1.0
    return value if value > 0 else 1.0


def icon_svg(channel_id: str | None) -> str:
    ch = channel_tokens(channel_id)
    bg = str(ch.get("end_card_bg") or "#0B0F14")
    accent = str(ch.get("accent") or "#FFFFFF")
    border = header_border_hex(channel_id)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="12" fill="{bg}"/>'
        f'<rect x="6" y="6" width="52" height="52" rx="8" fill="none" '
        f'stroke="{border}" stroke-width="4"/>'
        f'<circle cx="32" cy="32" r="12" fill="{accent}"/>'
        "</svg>"
    )


def redact_operator_paths(text: str) -> str:
    """Strip vault path and username from operator dumps (§18: absence is not a leak)."""
    out = str(text or "")
    vault = (os.getenv("OBSIDIAN_VAULT_PATH") or "").strip()
    if vault:
        out = out.replace(vault, "[vault]")
        out = out.replace(vault.replace("\\", "/"), "[vault]")
    home = str(Path.home())
    if home and len(home) > 3:
        out = out.replace(home, "[home]")
        out = out.replace(home.replace("\\", "/"), "[home]")
    user = (os.getenv("USERNAME") or os.getenv("USER") or "").strip()
    if len(user) >= 3:
        out = re.sub(re.escape(user), "[user]", out, flags=re.I)
    return out


def build_qss(
    channel_id: str | None,
    *,
    reduced_chroma: bool = False,
    high_contrast: bool = False,
    reduced_motion: bool = False,
    colorblind: bool = False,
) -> str:
    """Per-channel stylesheet. Palette is tokens only — no second hex table."""
    ch = channel_tokens(channel_id)
    bg = str(ch.get("end_card_bg") or "#0B0F14")
    fg = str(ch.get("end_card_fg") or "#FFFFFF")
    border = header_border_hex(channel_id)
    accent = str(ch.get("accent") or fg)
    primary = role_hex("primary", colorblind=colorblind)
    success = role_hex("success", colorblind=colorblind)
    warn = role_hex("warn", colorblind=colorblind)
    error = role_hex("error", colorblind=colorblind)
    body = _type_px("body", 16)
    h1 = _type_px("h1", 20)
    caption = _type_px("caption", 18)
    page = _space_px("page", 20)
    header = _space_px("header", 16)
    serif = 'Georgia, "Times New Roman", serif'
    sans = '"Segoe UI", system-ui, sans-serif'
    family = serif if (channel_id or "").strip().lower() == "moneywise" else sans
    chroma = "saturate(0.45)" if reduced_chroma else "none"
    extra = ""
    if high_contrast:
        extra += "\n/* high-contrast */\n"
        bg = "#000000"
        fg = "#FFFFFF"
        border = "#FFFFFF"
    motion = ""
    if reduced_motion:
        motion = "* { animation-duration: 0ms; transition-duration: 0ms; }\n"
    return f"""
/* design_tokens.json */
QMainWindow, QWidget {{
  background: {bg};
  color: {fg};
  font-family: {family};
  font-size: {body}px;
  padding: {page}px;
}}
QLabel#empty_state, QLabel#error_state {{
  font-size: {caption}px;
  color: {accent};
  padding: {header}px;
}}
QLabel#title_brand {{
  font-size: {h1}px;
  font-weight: 700;
  color: {accent};
  border-bottom: 3px solid {border};
  padding-bottom: {header}px;
}}
QLineEdit, QPlainTextEdit, QComboBox, QListWidget {{
  background: {bg};
  color: {fg};
  border: 1px solid {border};
  border-radius: 6px;
  padding: 8px;
  font-size: {body}px;
  selection-background-color: {primary};
}}
QPushButton {{
  background: {border};
  color: {fg};
  border: none;
  border-radius: 6px;
  padding: 8px {header}px;
  font-size: {body}px;
  font-weight: 600;
}}
QPushButton:disabled {{
  background: {bg};
  color: {accent};
  border: 1px dashed {border};
}}
QPushButton#start_btn {{
  background: {primary};
  color: {bg};
}}
QLabel#facts_meter {{ color: {warn}; font-size: {body}px; }}
QLabel#progress {{ color: {success}; }}
QLabel#error_state {{ color: {error}; }}
QWidget {{ filter: {chroma}; }}
{motion}{extra}
"""


def themed_css(
    channel_id: str | None = "",
    *,
    grain: bool = False,
    vignette: bool = False,
    colorblind: bool = False,
) -> str:
    """Shared HTML chrome for every operator dump (#172)."""
    ch = channel_tokens(channel_id or "tapin")
    bg = str(ch.get("end_card_bg") or "#0B0F14")
    fg = str(ch.get("end_card_fg") or "#FFFFFF")
    border = header_border_hex(channel_id or "tapin")
    success = role_hex("success", colorblind=colorblind)
    warn = role_hex("warn", colorblind=colorblind)
    error = role_hex("error", colorblind=colorblind)
    primary = role_hex("primary", colorblind=colorblind)
    body = _type_px("body", 16)
    h1 = _type_px("h1", 20)
    page = _space_px("page", 20)
    header = _space_px("header", 16)
    g_amt = look_grain(channel_id or "tapin")
    v_amt = look_vignette(channel_id or "tapin")
    extras = ""
    if grain:
        extras += (
            f"body.grain::before {{ content: ''; pointer-events: none; "
            f"position: fixed; inset: 0; opacity: {min(0.35, 0.04 * max(g_amt, 1)):.2f}; "
            "background-image: repeating-linear-gradient(0deg, #000 0 1px, transparent 1px 3px); "
            "mix-blend-mode: overlay; z-index: 40; }}\n"
        )
    if vignette:
        extras += f"body.vignette {{ box-shadow: inset 0 0 {int(80 + v_amt * 200)}px #000; }}\n"
    moneywise_type = ""
    if (channel_id or "").strip().lower() == "moneywise":
        moneywise_type = (
            'body.channel-moneywise header h1 { font-family: Georgia, "Times New Roman", serif; }\n'
        )
    return f"""
/* design_tokens.json */
:root {{ color-scheme: dark; }}
html, body {{ margin: 0; padding: 0; background: {bg}; color: {fg};
  font-family: "Segoe UI", system-ui, sans-serif; font-size: {body}px; line-height: 1.45; }}
.skip {{ position: absolute; left: -999px; top: auto; width: 1px; height: 1px; overflow: hidden; }}
.skip:focus {{ left: 1rem; top: 1rem; width: auto; height: auto; z-index: 20;
  background: {bg}; color: {fg}; padding: 0.5rem 0.75rem; }}
header {{ position: sticky; top: 0; z-index: 10; padding: {header}px {page}px;
  background: {bg}; border-bottom: 3px solid var(--header-border, {border}); }}
header h1 {{ margin: 0; font-size: {h1}px; letter-spacing: 0.02em; }}
header .sub {{ color: {fg}; opacity: 0.7; font-size: {body}px; margin-top: 0.25rem; }}
button, input, select, textarea {{ font-size: {body}px; }}
main {{ padding: {page}px; max-width: 960px; }}
pre {{ background: {bg}; border: 1px solid {border}; padding: 1rem; overflow: auto;
  font-family: "JetBrains Mono", Consolas, monospace; font-size: {body}px; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; font-size: {body}px; }}
th, td {{ text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid {border}; }}
.ok {{ color: {success}; }} .fail {{ color: {error}; }} .warn {{ color: {warn}; }}
.card {{ background: {bg}; border: 1px solid {border}; padding: 1rem; margin: 0.75rem 0; }}
a {{ color: {primary}; }}
body.reduced-chroma {{ filter: saturate(0.45); }}
{moneywise_type}{extras}
@media print {{
  header, .skip, .swatch, img.wordmark {{ display: none !important; }}
  main {{ padding: 0; max-width: none; }}
  pre {{ border: none; background: #fff; color: #000; }}
}}
"""


def look_flags() -> dict[str, bool]:
    def _on(name: str) -> bool:
        return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")

    return {
        "reduced_chroma": _on("CONTENT_UI_REDUCED_CHROMA"),
        "high_contrast": _on("CONTENT_UI_HIGH_CONTRAST"),
        "reduced_motion": _on("CONTENT_UI_REDUCED_MOTION"),
        "colorblind": _on("CONTENT_UI_COLORBLIND"),
        "grain": _on("CONTENT_UI_GRAIN"),
        "vignette": _on("CONTENT_UI_VIGNETTE"),
    }
