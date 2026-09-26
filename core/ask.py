"""Stage 0 ask() seam: pluggable text / choice / confirm backends.

TerminalBackend is input(). ScriptedBackend replays queued answers for tests.
Stage 1 installs BridgeBackend (core.ask_bridge) so the worker blocks on a queue.
"""

from __future__ import annotations

import builtins
from collections.abc import Sequence

from core import process_state


class Backend:
    def ask_text(self, prompt: str = "") -> str:
        raise NotImplementedError


class TerminalBackend(Backend):
    def ask_text(self, prompt: str = "") -> str:
        return builtins.input(prompt)


class ScriptedBackend(Backend):
    def __init__(self, answers: Sequence[str]) -> None:
        self._answers = list(answers)

    def ask_text(self, prompt: str = "") -> str:
        del prompt
        if not self._answers:
            raise EOFError("scripted ask() ran out of answers")
        return self._answers.pop(0)


_backend: Backend = TerminalBackend()


def set_backend(backend: Backend) -> None:
    global _backend
    _backend = backend


def reset_backend() -> None:
    set_backend(TerminalBackend())


def ask_text(prompt: str = "") -> str:
    return _backend.ask_text(prompt)


def ask_confirm(prompt: str, *, default: bool = False) -> bool:
    """Empty Enter uses default. 'y'/'yes' is True; anything else is False."""
    raw = ask_text(prompt).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def ask_choice(prompt: str) -> str:
    """Raw choice string; caller interprets digits / empty / 0."""
    return ask_text(prompt).strip()


process_state.register_reset("core.ask", reset_backend)  # #827
