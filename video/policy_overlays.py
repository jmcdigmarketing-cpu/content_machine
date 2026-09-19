"""#190 / #191. On-screen finance disclaimer bug and AI-disclosure lower-third."""

from __future__ import annotations

from video.lower_thirds import _ass_text, _ass_ts


def build_policy_overlays_ass(
    channel_id: str | None,
    words: list[dict] | None,
    *,
    duration: float = 8.0,
) -> str:
    del words  # timed to clip length, not spoken labels
    events: list[str] = []
    hold = min(4.0, max(1.5, float(duration) * 0.4))
    try:
        from core.description_extras import finance_disclaimer_line

        disclaimer = finance_disclaimer_line(channel_id or "")
    except Exception:
        disclaimer = ""
    if disclaimer:
        events.append(
            f"Dialogue: 0,{_ass_ts(0.0)},{_ass_ts(hold)},Disclaimer,,0,0,0,,"
            f"{_ass_text(disclaimer)}"
        )
    try:
        from core.description_extras import ai_disclosure_line

        disclosure = ai_disclosure_line(channel_id or "tapin")
    except Exception:
        disclosure = ""
    if disclosure:
        events.append(
            f"Dialogue: 0,{_ass_ts(0.0)},{_ass_ts(min(3.0, hold))},Disclosure,,0,0,0,,"
            f"{_ass_text(disclosure)}"
        )
    if not events:
        return ""
    # Disclosure is top-centre: bottom-centre at MarginV 280 sat on the karaoke captions
    # (bottom, MarginV 260) for the first 3 s once #783 restored them to full size.
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        "Style: Disclaimer,Arial,28,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,"
        "0,0,0,0,100,100,0,0,3,1,0,1,40,40,80,1\n"
        "Style: Disclosure,Arial,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,"
        "1,0,0,0,100,100,0,0,3,1,0,8,70,70,160,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(events)
        + "\n"
    )
