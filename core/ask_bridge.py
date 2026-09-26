"""Toolkit-agnostic ask() bridge for Stage 1.

The worker thread calls ask_text(); the UI thread waits on wait_request() and
answers with submit(). No Qt import — the window is a consumer of this queue.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from core import process_state
from core.ask import Backend

# Exact prompt strings the terminal shows today (main.py / core/ui.py).
AUTH_PROMPT = "  Authenticity gate flagged this video. Render anyway? [y/N]: "
GROUND_PROMPT = "  Grounding gate flagged unsupported claims. Render anyway? [y/N]: "
THIN_PROMPT = "  Thin facts — render anyway and pay TTS? [y/N]: "
OVER_PROMPT = "  Over length for TTS — render anyway? [y/N]: "
METRICS_PROMPT = "  Start the next video anyway? [y/N]: "
PROCEED_PROMPT = "  Proceed? [y = render / + longer / - shorter / 1-4 length / N = stop]: "
FACT_PROMPT_NEEDLE = "empty when done"


_GATE_PROMPTS = {
    AUTH_PROMPT: "authenticity",
    GROUND_PROMPT: "grounding",
    THIN_PROMPT: "thin_facts",
    OVER_PROMPT: "over_length",
    METRICS_PROMPT: "metrics",
}

_CANCEL = object()


@dataclass(frozen=True)
class AskRequest:
    prompt: str
    kind: str
    gate: str | None = None


@dataclass
class ProgressTick:
    phase: str
    done: int | None = None
    total: int | None = None
    detail: str | None = None


def classify_prompt(prompt: str) -> tuple[str, str | None]:
    """Map a live ask() prompt to a window widget kind."""
    text = prompt or ""
    gate = _GATE_PROMPTS.get(text)
    if gate:
        return ("confirm", gate)
    if text == PROCEED_PROMPT or text.strip().startswith("Proceed?"):
        return ("proceed", None)
    if FACT_PROMPT_NEEDLE in text and "Fact " in text:
        return ("fact", None)
    stripped = text.strip()
    if stripped.startswith("Choose 1-5"):
        return ("choice", "angles")
    if stripped.startswith("Select 1-4"):
        return ("choice", "length")
    if stripped.startswith("Use a best bet?"):
        return ("choice", "best_bet")
    if "[y/N]" in text or "[Y/n]" in text:
        return ("confirm", None)
    return ("text", None)


def missing_pyside_message() -> str:
    return 'run-window requires PySide6 - pip install -e ".[app]"'


class AskBridge:
    """One pending ask at a time. Fact lines from the paste box skip the queue."""

    def __init__(self) -> None:
        self._requests: queue.Queue[AskRequest] = queue.Queue()
        self._answers: queue.Queue[object] = queue.Queue()
        self._fact_lines: list[str] = []
        self._auto_end_facts = False
        self._progress: ProgressTick | None = None
        self._progress_lock = threading.Lock()
        self._closed = False
        self._choices: list[str] = []
        self._choices_lock = threading.Lock()

    def set_choices(self, titles: list[str]) -> None:
        with self._choices_lock:
            self._choices = [str(t) for t in titles if str(t).strip()]

    def choices(self) -> list[str]:
        with self._choices_lock:
            return list(self._choices)

    def set_fact_lines(self, lines: list[str]) -> None:
        self._fact_lines = [str(ln).strip() for ln in lines if str(ln).strip()]
        self._auto_end_facts = bool(self._fact_lines)

    def set_progress(
        self,
        phase: str,
        done: int | None = None,
        total: int | None = None,
        detail: str | None = None,
    ) -> None:
        with self._progress_lock:
            self._progress = ProgressTick(phase=phase, done=done, total=total, detail=detail)

    def progress(self) -> ProgressTick | None:
        with self._progress_lock:
            return self._progress

    def ask_text(self, prompt: str = "") -> str:
        if self._closed:
            raise KeyboardInterrupt
        kind, gate = classify_prompt(prompt)
        if kind == "fact" and self._fact_lines:
            return self._fact_lines.pop(0)
        if kind == "fact" and self._auto_end_facts:
            return ""
        req = AskRequest(prompt=prompt, kind=kind, gate=gate)
        self._requests.put(req)
        answer = self._answers.get()
        if answer is _CANCEL:
            raise KeyboardInterrupt
        return str(answer)

    def wait_request(self, timeout: float | None = None) -> AskRequest | None:
        try:
            if timeout is None:
                return self._requests.get()
            return self._requests.get(timeout=timeout)
        except queue.Empty:
            return None

    def submit(self, answer: str) -> None:
        self._answers.put(answer)

    def cancel(self) -> None:
        self._closed = True
        self._answers.put(_CANCEL)


class BridgeBackend(Backend):
    """core.ask.Backend that blocks on AskBridge instead of input()."""

    def __init__(self, bridge: AskBridge) -> None:
        self.bridge = bridge

    def ask_text(self, prompt: str = "") -> str:
        return self.bridge.ask_text(prompt)


_current: AskBridge | None = None


def current_bridge() -> AskBridge | None:
    return _current


def set_current_bridge(bridge: AskBridge | None) -> None:
    global _current
    _current = bridge


process_state.register_reset("core.ask_bridge", lambda: set_current_bridge(None))  # #827
