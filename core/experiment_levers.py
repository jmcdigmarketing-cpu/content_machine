"""Testable levers — each knows its arms and how to apply an arm to generation.

A lever is the *one thing* an experiment varies while everything else is held
constant. Each arm maps to a short prompt directive that overrides the relevant
generation knob. Arms are chosen to be compatible with the base prompt's rules
(e.g. no "question" hook arm, since the prompt forbids opening on a question).

`kind` says where the directive applies: "script" levers ride the script
prompt (creative_brief); "thumbnail" levers append to the Flux thumbnail
prompt (`assets/flux_thumbnail`); the "post_time" lever moves the publish time
(`analytics/post_timing.planned_post_time`, #912) and its directive is only a
description. Consumers filter by kind so a running thumbnail experiment never
leaks visual directives into a script prompt.
"""

from __future__ import annotations

_LEVERS: dict[str, dict] = {
    "hook_style": {
        "description": "How the script's first line grabs attention",
        "kind": "script",
        "arms": {
            "bold_statement": (
                "HOOK EXPERIMENT: open with a bold declarative statement — a strong, "
                "specific claim — as the first sentence (not a number or a question)."
            ),
            "stat_number": (
                "HOOK EXPERIMENT: open with a specific number or stat as the very first "
                "sentence (e.g. a record, dollar figure, or count)."
            ),
        },
    },
    # #1502 (the operator, 2026-10-23: alternate): does the hook rewrite hold more viewers?
    # Overnight drafts take an arm; "off" keeps the first-draft opener (main.py always rewrites).
    "hook_rewrite": {
        "description": "Whether the hook rewrite runs on an overnight draft",
        "kind": "hook",
        "arms": {
            "on": "HOOK ARM: the rewrite runs.",
            "off": "HOOK ARM: the first-draft opener stays.",
        },
    },
    "cta_style": {
        "description": "How the script closes / calls for engagement",
        "kind": "script",
        "arms": {
            "question": "CTA EXPERIMENT: close on a sharp, specific question that invites a take.",
            "prediction": "CTA EXPERIMENT: close on a bold prediction the audience can argue with.",
        },
    },
    "thumbnail_style": {
        "description": "Flux thumbnail composition style (Phase S thumbnail A/B)",
        "kind": "thumbnail",
        "arms": {
            "close_up": (
                "extreme close-up on the single main subject, face or key action filling "
                "the frame, shallow depth of field, intense emotion"
            ),
            "wide_drama": (
                "wide dramatic composition, subject small against an epic environment, "
                "cinematic lighting, high-stakes atmosphere"
            ),
            "subject_scale": (
                "named slot — subject scale: the main subject occupies most of the "
                "frame, large enough to read at phone size, with a single clear focal point"
            ),
            "text_negative_space": (
                "named slot — negative space for text: keep the upper third or a side "
                "panel clear and unbusy so a short headline can sit there without covering "
                "the subject"
            ),
            "hard_light": (
                "named slot — lighting: hard directional light with a crisp rim, high "
                "contrast, no flat even fill"
            ),
        },
    },
    "post_time": {
        "description": "When the video goes public: the recommended slot or a few hours off it",
        "kind": "post_time",
        "arms": {
            "on_slot": "publish at the recommended slot",
            "off_slot": (
                "publish at a random whole hour within POST_TIME_WINDOW_HOURS (default 3) "
                "of the recommended slot"
            ),
        },
    },
    "thumbnail_format": {
        "description": "Operator-picked dual thumbnail layout",
        "kind": "thumbnail",
        "arms": {
            "text_on": (
                "high-contrast editorial composition with generous negative space "
                "for a large readable headline"
            ),
            "face_forward": (
                "single expressive face or subject filling most of the frame, "
                "strong eye line, no headline text"
            ),
        },
    },
    "thumbnail_text": {
        "description": "Short vs full headline on the same thumbnail layout (#509)",
        "kind": "thumbnail_text",
        "arms": {
            "text_short": "keep the painted headline to the first three title words",
            "text_full": "paint the title's first phrase, up to five words (#1544)",
        },
    },
    "voice_delivery": {
        "description": "ElevenLabs stability, style, and similarity",
        "kind": "voice",
        "arms": {
            "steady": "use the channel tts stability, style, and similarity_boost",
            "expressive": "stability 0.35, similarity_boost 0.80, style 0.45",
        },
    },
    "tts_model": {
        "description": "ElevenLabs model. The blind pick on three scripts is still open.",
        "kind": "tts_model",
        "arms": {
            "multilingual_v2": "eleven_multilingual_v2",
            "v3": "eleven_v3",
        },
    },
    "caption_tiktok": {
        "description": "Which existing sentence leads the TikTok caption (#1197)",
        "kind": "caption",
        "arms": {
            "caption": "CAPTION ARM: lead the TikTok caption with the title.",
            "first_line": "CAPTION ARM: lead the TikTok caption with the script's first sentence.",
        },
    },
    "caption_instagram": {
        "description": "Which existing sentence leads the Instagram caption (#1197)",
        "kind": "caption",
        "arms": {
            "caption": "CAPTION ARM: lead the Instagram caption with the title.",
            "first_line": (
                "CAPTION ARM: lead the Instagram caption with the script's first sentence."
            ),
        },
    },
}


def known(lever: str) -> bool:
    return lever in _LEVERS


def levers() -> list[str]:
    return list(_LEVERS)


def arms(lever: str) -> list[str]:
    return list(_LEVERS.get(lever, {}).get("arms", {}))


def directive(lever: str, arm: str) -> str:
    return _LEVERS.get(lever, {}).get("arms", {}).get(arm, "")


def is_directive(text: str) -> bool:
    """True when `text` is one of the levers' own prompt directives (#1142). A batch draft
    passes its experiment's directive where an interactive run passes the operator's typed
    thoughts, and only the second is a list of the operator's points."""
    wanted = " ".join(str(text or "").split())
    if not wanted:
        return False
    from core.facts.event_dates import PREVIEW_PREFIX

    if wanted.startswith(PREVIEW_PREFIX):  # #1169: a scheduled game's preview brief
        return True
    return any(
        " ".join(directive(lever, arm).split()) == wanted
        for lever in levers()
        for arm in arms(lever)
    )


def kind(lever: str) -> str:
    return _LEVERS.get(lever, {}).get("kind", "script")


def voice_delivery_overrides(arm: str) -> dict[str, float]:
    """Numbers the expressive arm sends. Steady keeps the channel block."""
    if arm != "expressive":
        return {}
    return {"stability": 0.35, "similarity_boost": 0.80, "style": 0.45}


def tts_model_for_arm(arm: str) -> str:
    """Model id for a tts_model arm. Empty when the arm is unknown.

    The operator's blind pick between these two, on three scripts, is still open.
    """
    return {
        "multilingual_v2": "eleven_multilingual_v2",
        "v3": "eleven_v3",
    }.get(arm, "")
