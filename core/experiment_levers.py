"""Testable levers — each knows its arms and how to apply an arm to generation.

A lever is the *one thing* an experiment varies while everything else is held
constant. Each arm maps to a short prompt directive that overrides the relevant
generation knob. Arms are chosen to be compatible with the base prompt's rules
(e.g. no "question" hook arm, since the prompt forbids opening on a question).
"""

from __future__ import annotations

_LEVERS: dict[str, dict] = {
    "hook_style": {
        "description": "How the script's first line grabs attention",
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
        "arms": {
            "question": "CTA EXPERIMENT: close on a sharp, specific question that invites a take.",
            "prediction": "CTA EXPERIMENT: close on a bold prediction the audience can argue with.",
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
