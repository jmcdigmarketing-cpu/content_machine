"""Testable levers — each knows its arms and how to apply an arm to generation.

A lever is the *one thing* an experiment varies while everything else is held
constant. Each arm maps to a short prompt directive that overrides the relevant
generation knob. Arms are chosen to be compatible with the base prompt's rules
(e.g. no "question" hook arm, since the prompt forbids opening on a question).

`kind` says where the directive applies: "script" levers ride the script
prompt (creative_brief); "thumbnail" levers append to the Flux thumbnail
prompt (`assets/flux_thumbnail`). Consumers filter by kind so a running
thumbnail experiment never leaks visual directives into a script prompt.
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
}


def known(lever: str) -> bool:
    return lever in _LEVERS


def levers() -> list[str]:
    return list(_LEVERS)


def arms(lever: str) -> list[str]:
    return list(_LEVERS.get(lever, {}).get("arms", {}))


def directive(lever: str, arm: str) -> str:
    return _LEVERS.get(lever, {}).get("arms", {}).get(arm, "")


def kind(lever: str) -> str:
    return _LEVERS.get(lever, {}).get("kind", "script")
