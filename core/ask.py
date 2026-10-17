"""Stage 0 ask() seam: pluggable text / choice / confirm backends.

TerminalBackend is input(). ScriptedBackend replays queued answers for tests.
Stage 1 installs BridgeBackend (core.ask_bridge) so the worker blocks on a queue.
"""

from __future__ import annotations

import builtins
import os
import re
import sys
from collections.abc import Sequence

from core import process_state

_GATE_BELL = re.compile(r"Select |Proceed\?|Choose |Sign in|Set aside", re.I)


def gate_bell(prompt: str, *, tty: bool, no_color: bool) -> str:
    """One BEL when a gate is waiting on a TTY. A fact line, a pipe, and NO_COLOR stay quiet."""
    if not tty or no_color:
        return ""
    if not _GATE_BELL.search(prompt or ""):
        return ""
    return "\a"


def _stdout_is_tty() -> bool:
    try:
        return bool(sys.stdout) and sys.stdout.isatty()
    except Exception:
        return False


class Backend:
    # `payload` is what the app's backend shows beside the question (the angle step's
    # discovery read, 3ef604d). A console has nowhere to show it - it is ignored there, never
    # refused: refusing it crashed `py main.py` at the angle step (2026-10-17).
    def ask_text(self, prompt: str = "", *, payload: object = None) -> str:
        raise NotImplementedError


class TerminalBackend(Backend):
    def ask_text(self, prompt: str = "", *, payload: object = None) -> str:
        del payload
        bell = gate_bell(
            prompt,
            tty=_stdout_is_tty(),
            no_color=bool(os.getenv("NO_COLOR", "").strip()),
        )
        if bell:
            sys.stdout.write(bell)
            sys.stdout.flush()
        return builtins.input(prompt)


class ScriptedBackend(Backend):
    def __init__(self, answers: Sequence[str]) -> None:
        self._answers = list(answers)

    def ask_text(self, prompt: str = "", *, payload: object = None) -> str:
        del prompt, payload
        if not self._answers:
            raise EOFError("scripted ask() ran out of answers")
        return self._answers.pop(0)


_backend: Backend = TerminalBackend()


def set_backend(backend: Backend) -> None:
    global _backend
    _backend = backend


def reset_backend() -> None:
    set_backend(TerminalBackend())


def ask_text(prompt: str = "", *, payload: object = None) -> str:
    if payload is None:
        return _backend.ask_text(prompt)
    return _backend.ask_text(prompt, payload=payload)


def ask_confirm(prompt: str, *, default: bool = False) -> bool:
    """Empty Enter uses default. 'y'/'yes' is True; anything else is False."""
    raw = ask_text(prompt).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def ask_choice(prompt: str, *, payload: object = None) -> str:
    """Raw choice string; caller interprets digits / empty / 0."""
    return ask_text(prompt, payload=payload).strip()


process_state.register_reset("core.ask", reset_backend)  # #827
