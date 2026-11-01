"""#1775 (decision 89): where text may sit on a 9:16 frame - one zone for every app.

YouTube Shorts covers about the top 12% (search, camera) and the bottom 20% (title, channel,
Subscribe); TikTok covers the top ~10% (Following / For You) and the bottom ~20% (caption,
username, sound), and Instagram and Facebook Reels about the same. #502 drew these bands on
drafts, yet the captions sat inside the bottom one (their bottom edge at 86% of the height), the
hook card started at 6% and ran off both edges unwrapped, and the AI line at 8% sat under it.

Every overlay is placed from here, and `outside` names a style anchored in the chrome - the
render logs it.
"""

from __future__ import annotations

import math

HEIGHT = 1920  # the render's PlayResY

SAFE_TOP = 0.12
SAFE_BOTTOM = 0.20
# #1931 (decision 94): Instagram draws its caption, name and audio rows over the bottom of a Reel
# - estimates for organic Reels run 250-450 px - so the captions keep 450 px clear, 66 px above
# YouTube's 384, and one render serves every app.
CAPTION_BOTTOM_PX = 450
# The band the karaoke captions occupy (one or two lines above the bottom chrome) - where the
# #1268 scrim darkens and the contrast check samples: 230 px tall, ending 450 px up.
CAPTION_BAND = (
    round(1 - (CAPTION_BOTTOM_PX + 230) / HEIGHT, 4),
    round(1 - CAPTION_BOTTOM_PX / HEIGHT, 4),
)

# #1921 (decision 90): TikTok's like / comment / share column covers about the right 12% of the
# frame beside the captions; the captions keep this much clear on both sides, so they stay
# centred (84 of 466 recent cues had reached under the column).
SIDE_PX = 130

TOP_PX = math.ceil(HEIGHT * SAFE_TOP)  # 231
BOTTOM_PX = math.ceil(HEIGHT * SAFE_BOTTOM)  # 384

# The top of the frame, in the first seconds: the AI line (0-3 s), then the hook card (0-1 s,
# up to three lines), then - only when a bottom HUD sends them up - the captions.
DISCLOSURE_MARGIN = TOP_PX
HOOK_CARD_MARGIN = TOP_PX + 60
CAPTION_TOP_MARGIN = HOOK_CARD_MARGIN + 3 * 76
# Name tags and the MoneyWise disclaimer: above the caption band.
LOWER_MARGIN = CAPTION_BOTTOM_PX + 250


def caption_margin(anchor: str, margin: int | float | None) -> int:
    """The captions' MarginV: the skin's, but never inside the chrome or under the top cards."""
    floor = CAPTION_TOP_MARGIN if str(anchor).strip().lower() == "top" else CAPTION_BOTTOM_PX
    try:
        wanted = int(margin) if margin is not None else floor
    except (TypeError, ValueError):
        wanted = floor
    return max(wanted, floor)


def _section_rows(ass: str, section: str) -> list[str]:
    rows: list[str] = []
    inside = False
    for line in ass.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            inside = stripped.lower() == section.lower()
            continue
        if inside:
            rows.append(stripped)
    return rows


def outside(ass: str) -> list[str]:
    """Style names anchored inside the chrome: a top-aligned (7-9) style whose MarginV is above
    the safe top, a bottom-aligned (1-3) one whose MarginV is below the safe bottom - on the
    script's own PlayResY. Middle-aligned styles are not anchored to an edge."""
    play_y = HEIGHT
    for row in _section_rows(ass, "[Script Info]"):
        if row.lower().startswith("playresy:"):
            try:
                play_y = int(row.split(":", 1)[1].strip())
            except ValueError:
                play_y = HEIGHT
    fields: list[str] = []
    found: list[str] = []
    for row in _section_rows(ass, "[V4+ Styles]"):
        if row.startswith("Format:"):
            fields = [f.strip().lower() for f in row[len("Format:") :].split(",")]
        elif row.startswith("Style:") and fields:
            values = dict(zip(fields, (v.strip() for v in row[len("Style:") :].split(",")),
                              strict=False))  # fmt: skip
            try:
                alignment, margin = int(values["alignment"]), int(values["marginv"])
            except (KeyError, ValueError):
                continue
            share = margin / max(1, play_y)
            if (alignment >= 7 and share < SAFE_TOP - 1e-9) or (
                alignment <= 3 and share < SAFE_BOTTOM - 1e-9
            ):
                found.append(values.get("name", "?"))
    return found
